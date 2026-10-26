#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 仙八色鸫识别 —— conv1 走 GEMM 硬件加速器 + 其余层 numpy 的板端端到端
=====================================================================
  数据流：
    wav -> STFT/mel/归一化(numpy) -> im2col -> 量化Q12
        -> [GEMM 硬件做 conv1（融合BN + bias + ReLU）]
        -> maxpool/conv2/conv3/avgpool/FC/sigmoid (numpy)
        -> 鸣声分数

  说明：
    - 硬件 GEMM 固定 K=9(3×3×1)、N=16(conv1 输出通道)；conv1 输出
      (16,64,201)，M=12864。bias 已烘焙进 bit（bias.h），这里只送 A/B。
    - 兼容旧 bit（S2MM 缺 TLAST）：每次调用后按 ap_done 判定并复位通道，
      可反复调用，不影响结果。
    - 纯 numpy 路径仅用于和硬件结果对比，验证端到端正确性。

  用法（在板子 /home/xilinx/gemm 下，需有 gemm_soc.bit/.hwh、
        audio_model.npz、bird_sample.wav）：
    sudo python3 e2e_board.py                    # 硬件 conv1 + 鸟样例，对比 numpy
    sudo python3 e2e_board.py --cpu-only         # 只用 numpy（不加载 bit，便于先测环境）
    python3 e2e_board.py --wav other.wav         # 换任意 32kHz 单声道 wav
=====================================================================
"""
import os
import time
import argparse
import numpy as np

# ---- 固定参数（与 HLS / 模型一致） ----
K, N = 9, 16
Q12 = 4096.0
AP_CTRL = 0x00
REG_M, REG_K, REG_N = 0x10, 0x18, 0x20
DMA_DMASR = 0x04
DMA_IDLE, DMA_IOC = 1 << 1, 1 << 12
DMA_ERRBITS = (1 << 4) | (1 << 5) | (1 << 6)


# ============================ 音频 / 模型（numpy） ============================
def read_wav(path):
    """读取单声道 wav；支持 32bit float(tag=3) 和 16bit PCM(tag=1)，返回 float32。"""
    raw = open(path, "rb").read()
    assert raw[:4] == b"RIFF" and raw[8:12] == b"WAVE", "不是 wav: %s" % path
    pos, fmt, data = 12, None, None
    while pos + 8 <= len(raw):
        cid = raw[pos:pos+4]
        csize = int.from_bytes(raw[pos+4:pos+8], "little")
        body = raw[pos+8:pos+8+csize]
        if cid == b"fmt ":
            fmt = body
        elif cid == b"data":
            data = body
        pos += 8 + csize + (csize & 1)
    tag = int.from_bytes(fmt[0:2], "little")
    ch = int.from_bytes(fmt[2:4], "little")
    sr = int.from_bytes(fmt[4:8], "little")
    sw = int.from_bytes(fmt[14:16], "little")
    if tag == 3 and sw == 32:
        y = np.frombuffer(data, dtype="<f4").astype(np.float32)
    elif tag == 1 and sw == 16:
        y = (np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0)
    elif tag == 1 and sw == 24:
        b = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
        i = (b[:, 0].astype(np.int32) | (b[:, 1].astype(np.int32) << 8) |
             (b[:, 2].astype(np.int32) << 16))
        i = np.where(i & 0x800000, i - 0x1000000, i)
        y = (i / 8388608.0).astype(np.float32)
    else:
        raise RuntimeError("暂不支持 wav tag=%d sampwidth=%d" % (tag, sw))
    if ch == 2:
        y = y.reshape(-1, 2)[:, 0]
    return sr, np.ascontiguousarray(y)


class BirdModel:
    def __init__(self, npz_path):
        d = np.load(npz_path, allow_pickle=True)
        self.sr = int(d["sr"]); self.n_fft = int(d["n_fft"]); self.hop = int(d["hop_length"])
        self.n_mels = int(d["n_mels"]); self.power = float(d["power"])
        self.top_db = float(d["top_db"]); self.mel_fb = d["mel_fb"]; self.window = d["window"]
        self.mean = float(d["mean"]); self.std = float(d["std"]); self.threshold = float(d["threshold"])
        self.d = d

    def feature(self, y):
        n_fft = self.n_fft
        y = np.pad(y, n_fft // 2, mode="constant")
        n_frames = 1 + (len(y) - n_fft) // self.hop
        frames = np.lib.stride_tricks.as_strided(
            y, (n_frames, n_fft),
            (y.strides[0] * self.hop, y.strides[0]), writeable=False) * self.window
        spec = np.fft.rfft(frames, n=n_fft, axis=1)
        mag = (spec.real ** 2 + spec.imag ** 2) ** (self.power / 2.0)
        S = mag.T.astype(np.float32)
        mel = self.mel_fb @ S
        amin = 1e-10
        lg = 10.0 * np.log10(np.maximum(amin, mel))
        lg -= 10.0 * np.log10(np.maximum(amin, np.max(mel)))
        lg = np.maximum(lg, lg.max() - self.top_db)
        return ((lg - self.mean) / self.std).astype(np.float32)   # (n_mels, n_frames)

    @staticmethod
    def fuse_conv_bn(w, gamma, beta, mean, var, eps=1e-5):
        oc = w.shape[0]
        scale = gamma / np.sqrt(var + eps)
        wf = w * scale.reshape(oc, 1, 1, 1)
        bf = (-mean) * scale + beta
        return wf.astype(np.float32), bf.astype(np.float32)

    @staticmethod
    def im2col(x, kh=3, kw=3, pad=1, stride=1):
        C, Hin, Win = x.shape
        xp = np.pad(x, ((0, 0), (pad, pad), (pad, pad)), mode="constant")
        Hout = (Hin + 2 * pad - kh) // stride + 1
        Wout = (Win + 2 * pad - kw) // stride + 1
        A = np.zeros((Hout * Wout, kh * kw * C), np.float32)
        m = 0
        for oh in range(Hout):
            for ow in range(Wout):
                A[m] = xp[:, oh*stride:oh*stride+kh, ow*stride:ow*stride+kw].reshape(-1)
                m += 1
        return A, Hout, Wout

    def conv1_gemm_inputs(self, feat):
        """归一化特征 -> im2col A(M,K)、融合权重 B(K,N)、bias(N)。"""
        d = self.d
        wf, bf = self.fuse_conv_bn(d["conv1_w"], d["bn1_w"], d["bn1_b"],
                                   d["bn1_mean"], d["bn1_var"])
        x = feat[None, :, :]
        A, H, W = self.im2col(x)
        B = wf.reshape(16, K).T          # (K,N)
        return A, B, bf, H, W

    def rest_forward(self, conv1_mn, H, W):
        """conv1 输出(M,N,浮点) -> maxpool/conv2/conv3/avgpool/FC -> 分数。"""
        d = self.d
        c = conv1_mn.reshape(H, W, 16).transpose(2, 0, 1)
        c = c[:, :H//2*2, :W//2*2].reshape(16, H//2, 2, W//2, 2).max(axis=(2, 4))
        for name in ("conv2", "conv3"):
            tag = "bn" + name[-1]
            wf, bf = self.fuse_conv_bn(d[name+"_w"], d[tag+"_w"], d[tag+"_b"],
                                       d[tag+"_mean"], d[tag+"_var"])
            A2, H2, W2 = self.im2col(c)
            B2 = wf.reshape(wf.shape[0], -1).T
            c = np.maximum(A2 @ B2 + bf[np.newaxis, :], 0)
            c = c.reshape(H2, W2, -1).transpose(2, 0, 1)
            c = c[:, :H2//2*2, :W2//2*2].reshape(c.shape[0], H2//2, 2, W2//2, 2).max(axis=(2, 4))
        Hc, Wc = c.shape[1], c.shape[2]
        oh, ow = 4, 1
        pool = np.zeros((c.shape[0], oh, ow), np.float32)
        for i in range(oh):
            hs, he = i*Hc//oh, (i+1)*Hc//oh
            for j in range(ow):
                ws, we = j*Wc//ow, (j+1)*Wc//ow
                pool[:, i, j] = c[:, hs:he, ws:we].mean(axis=(1, 2))
        logit = float((d["fc_w"] @ pool.reshape(-1) + d["fc_b"]).reshape(-1)[0])
        return 1.0 / (1.0 + np.exp(-logit))

    @staticmethod
    def q12(x):
        return np.clip(np.round(x * 4096.0), -32768, 32767).astype(np.int16)


# ============================ GEMM 硬件封装（可重复调用） ============================
class GemmConv1:
    def __init__(self, here, overlay="gemm_soc.bit", M=12864):
        from pynq import Overlay, allocate
        from pynq.ps import Clocks
        os.environ["PYNQ_DISABLE_DMA_INTERRUPT"] = "1"
        self.M, self.allocate = M, allocate
        ol = Overlay(os.path.join(here, overlay))
        Clocks.fclk0_mhz = 100.0
        for _n, _desc in ol.ip_dict.items():
            if _desc.get("interrupts"):
                _desc["interrupts"] = {}
        self.dmaA, self.dmaB, self.dmaC = ol.dma_A, ol.dma_B, ol.dma_C
        self.gemm = ol.gemm_top_0
        self.bufA = allocate(shape=(M*K,), dtype=np.int16)
        self.bufB = allocate(shape=(K*N,), dtype=np.int16)
        self.bufC = allocate(shape=(M*N,), dtype=np.int16)
        self.gemm.write(REG_M, M); self.gemm.write(REG_K, K); self.gemm.write(REG_N, N)
        print("[HW] GEMM overlay 就绪：M=%d K=%d N=%d，DMA C 上限=%d 字节"
              % (M, K, N, self.dmaC.recvchannel._size))

    def _stat(self, chan):
        return chan._mmio.read(DMA_DMASR)

    def _sync(self, buf, to_dev):
        m = getattr(buf, "sync_to_device" if to_dev else "sync_from_device", None)
        if m is None:
            m = getattr(buf, "flush" if to_dev else "invalidate", None)
        if m:
            m()

    def _ensure_s2mm_idle(self):
        ch = self.dmaC.recvchannel
        s = self._stat(ch)
        if s & DMA_IOC:
            try: ch._mmio.write(DMA_DMASR, DMA_IOC)
            except Exception: pass
        if not (s & DMA_IDLE):
            try:
                ch.stop(); time.sleep(0.002); ch.start()
            except Exception:
                pass

    def _wait_mm2s(self, ch):
        t0 = time.time(); busy = False
        while time.time() - t0 < 60:
            s = self._stat(ch)
            if s & DMA_ERRBITS:
                raise RuntimeError("MM2S error 0x%04x" % s)
            if not (s & DMA_IDLE):
                busy = True
            if (s & DMA_IOC) or (busy and (s & DMA_IDLE)):
                return
            time.sleep(0.0005)
        raise RuntimeError("MM2S timeout")

    def _wait_ap_done(self, t0):
        """从写 ap_start 那一刻起算，等到 ap_done 置位；返回经过的秒数。"""
        while time.time() - t0 < 120:
            if self.gemm.read(AP_CTRL) & 0x2:
                return time.time() - t0
            time.sleep(0.0002)
        raise RuntimeError("ap_done timeout")

    def run(self, Aq, Bq):
        """Aq:int16(M,K)  Bq:int16(K,N)；返回 (C float32(M,N), 核时间, 端到端时间)。

        端到端时间覆盖：填 buf → cache flush → 三路 DMA 搬运 + GEMM 计算
        → cache invalidate → 反量化；不含 Q12 量化（由调用方按需计入）。
        核时间从"写下 ap_start"开始计时（含 DMA 与计算的重叠），到观测到 ap_done 为止。
        """
        t_tot = time.time()
        assert Aq.size == self.M*K and Bq.size == K*N
        self._ensure_s2mm_idle()
        self.bufA[:] = Aq.reshape(-1)
        self.bufB[:] = Bq.reshape(-1)
        self._sync(self.bufA, True); self._sync(self.bufB, True)

        self.dmaC.recvchannel.transfer(self.bufC)
        self.dmaA.sendchannel.transfer(self.bufA)
        self.dmaB.sendchannel.transfer(self.bufB)
        t_start = time.time()                 # 计时起点提前到 ap_start 之前
        self.gemm.write(AP_CTRL, 0x1)

        self._wait_mm2s(self.dmaA.sendchannel)
        self._wait_mm2s(self.dmaB.sendchannel)
        dt = self._wait_ap_done(t_start)

        s = self._stat(self.dmaC.recvchannel)
        if not (s & DMA_IOC):          # 旧 bit 缺 TLAST：复位以复用
            self._ensure_s2mm_idle()
        self._sync(self.bufC, False)
        C = self.bufC.astype(np.float32).reshape(self.M, N) / Q12
        return C, dt, time.time() - t_tot


# ============================ 主流程 ============================
def main():
    ap = argparse.ArgumentParser()
    here = os.path.dirname(os.path.abspath(__file__))
    ap.add_argument("--wav", default=os.path.join(here, "bird_sample.wav"))
    ap.add_argument("--model", default=os.path.join(here, "audio_model.npz"))
    ap.add_argument("--overlay", default="gemm_soc.bit")
    ap.add_argument("--cpu-only", action="store_true", help="只用 numpy，不加载 bit")
    ap.add_argument("--repeat", type=int, default=1, help="硬件 conv1 重复次数（验证可反复调用）")
    ap.add_argument("--bench", type=int, default=0,
                    help="公平加速比计时：硬件 conv1(含量化+DMA搬运) vs numpy conv1 各跑 N 次，取中位数")
    args = ap.parse_args()

    model = BirdModel(args.model)
    sr, y = read_wav(args.wav)
    y = y[:sr*2]
    if len(y) < sr*2:
        y = np.pad(y, (0, sr*2 - len(y)))
    print("[音频] %s  sr=%d  采样点=%d" % (os.path.basename(args.wav), sr, len(y)))

    feat = model.feature(y)
    A_fp, B_fp, bias_fp, H, W = model.conv1_gemm_inputs(feat)
    M = H * W
    Aq, Bq = model.q12(A_fp), model.q12(B_fp)
    print("[GEMM] M=%d K=%d N=%d  特征图=%d×%d" % (M, K, N, H, W))

    # ---- 纯 numpy 浮点参考（端到端） ----
    t0 = time.time()
    C_fp = np.maximum(A_fp @ B_fp + bias_fp[np.newaxis, :], 0).astype(np.float32)
    score_cpu = model.rest_forward(C_fp, H, W)
    t_cpu = time.time() - t0

    if args.cpu_only:
        print("[结果] numpy 端到端分数 = %.6f  耗时 %.3fs" % (score_cpu, t_cpu))
        print("判定:", "仙八色鸫" if score_cpu >= model.threshold else "非目标")
        return

    # ---- 硬件 conv1 ----
    hw = GemmConv1(here, args.overlay, M=M)

    # ============ 公平加速比计时 ============
    if args.bench > 0:
        def np_conv1():
            return np.maximum(A_fp @ B_fp + bias_fp[np.newaxis, :], 0).astype(np.float32)

        # warmup（首次含 cache/分配/懒初始化，不计入）
        C_hw, _, _ = hw.run(Aq, Bq)
        np_conv1()
        n = args.bench
        t_hw, t_np, t_core = [], [], []
        for _ in range(n):
            t0 = time.time()
            Aq_i, Bq_i = model.q12(A_fp), model.q12(B_fp)   # Q12 量化计入硬件路径
            _, dt_core, _ = hw.run(Aq_i, Bq_i)
            t_hw.append(time.time() - t0)
            t_core.append(dt_core)
            t0 = time.time()
            np_conv1()
            t_np.append(time.time() - t0)
        t_hw.sort(); t_np.sort(); t_core.sort()
        med = lambda a: a[len(a)//2]
        m_hw, m_np, m_core = med(t_hw), med(t_np), med(t_core)
        print("\n======== 公平加速比（板端，各 %d 次，中位数）========" % n)
        print("硬件 conv1 端到端（Q12量化+DMA搬运+GEMM+反量化） = %.4f s" % m_hw)
        print("  其中 HLS 核 ap_start→ap_done 纯计算            = %.4f s" % m_core)
        print("numpy conv1 单独（A@B+bias+ReLU）               = %.4f s" % m_np)
        print("公平加速比 = %.2fx（端到端口径）" % (m_np / m_hw))
        print("纯核加速比 = %.2fx（仅核计算，不含搬运）" % (m_np / m_core))
        print("最小/最大 硬件端到端 = %.4f / %.4f s" % (t_hw[0], t_hw[-1]))
        print("==================================================")
        return

    # ---- 常规验证 ----
    C_hw = None
    dt_list = []
    t_tot_list = []
    for i in range(args.repeat):
        C_hw, dt_core, dt_tot = hw.run(Aq, Bq)
        dt_list.append(dt_core)
        t_tot_list.append(dt_tot)
    score_hw = model.rest_forward(C_hw, H, W)

    # 硬件 conv1 与浮点 conv1 的差异
    cd = np.abs(C_hw - C_fp)
    print("\n================ 端到端结果 ================")
    print("numpy 全浮点  分数 = %.6f" % score_cpu)
    print("硬件 conv1    分数 = %.6f" % score_hw)
    print("conv1 最大误差 = %.6f（容差 0.02，点数 %d/%d）"
          % (float(cd.max()), int((cd > 0.02).sum()), M*N))
    if len(dt_list) > 1:
        dts = sorted(dt_list)
        mid = dts[len(dts)//2]
        print("GEMM 硬件 conv1 核耗时 = %d 次：最小 %.4fs  中位 %.4fs  最大 %.4fs（ap_start→ap_done）"
              % (len(dts), dts[0], mid, dts[-1]))
        print("端到端含搬运/反量化 = 中位 %.4fs" % sorted(t_tot_list)[len(t_tot_list)//2])
    else:
        print("GEMM 硬件 conv1 核耗时 = %.4fs（单次；用 --repeat 5 起可给最小/中位/最大）" % dt_list[0])
    print("numpy 整网(含conv1) %.3fs" % t_cpu)
    print("公平加速比请用 --bench 20")
    ok = abs(score_hw - score_cpu) < 0.01
    print("判定:", "仙八色鸫" if score_hw >= model.threshold else "非目标",
          " 阈值=%.4f" % model.threshold)
    print("==========================================")
    print("==== 硬件 conv1 端到端 %s ====" % ("PASS（与浮点一致）" if ok else "FAIL"))


if __name__ == "__main__":
    main()
