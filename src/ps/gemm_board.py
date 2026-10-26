#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PYNQ-Z2 GEMM 加速器板级驱动（最终版：寄存器轮询 / ap_done 权威完成）
=====================================================================
数据通路:  DDR(A.bin) --dma_A--> [s_axis_A  gemm_top  m_axis_C] --dma_C--> DDR(C)
           DDR(B.bin) --dma_B--> [s_axis_B ]
控制通路:  PS M_AXI_GP0 -> gemm_top s_axi，写 M/K/N 后置 ap_start

本驱动对新/旧两种比特流都能工作：
  * 新 bit：c_sg_length_width=23（单次可传 8MB，解除 16KB 上限）；
            HLS 末拍 TLAST 已修正（S2MM 正常收到 TLAST 并置 IOC）；
            中断 NUM_F2P=1 已接对。
  * 旧 bit：仍保留“清中断描述 + ap_done 判据 + S2MM 缺 TLAST 时复位”的兼容。

用法（板子上，与 gemm_soc.bit/gemm_soc.hwh 及各 .bin 同目录）：
    sudo python3 gemm_board.py --small     # 小数据 M=32 快速验证
    sudo python3 gemm_board.py             # 全量 M=12864
    sudo python3 gemm_board.py --cpu       # 额外打印 PS CPU(numpy) 参考耗时/加速比
"""
import os
import time
import argparse
import numpy as np

# 个别 PYNQ 版本支持该变量禁用 DMA 中断；驱动里还会显式清空未连接中断描述。
os.environ["PYNQ_DISABLE_DMA_INTERRUPT"] = "1"

K, N = 9, 16
TOL = 0.02          # 与 C 仿真一致的判定容差
Q12 = 4096.0        # ap_fixed<16,4> 小数位=12，1 个最低位 = 1/4096

# 版本指纹：板上启动时若打印的不是这行，说明文件没更新成功
DRIVER_VERSION = "2026-10-25 TLAST+DMA23 最终版"
# 已知版本的 MD5（同一份工程重新综合一次，.bit 的 MD5 就会变，所以这里列"可接受集合"）：
#   2026-10-25 版：板端跑出 0.997878 / 6.7 ms 实测数据的那一版
#   2026-10-26 版：用 build/build_gemm.tcl 重建、随仓库提交的版本（功能相同，需重跑一次确认）
EXPECT_MD5 = {
    "gemm_soc.bit": {
        "81714b8306646bbe102e41236a0a3054": "2026-10-25 板端实测版",
        "8240f2dc546fd9cb45e3e0adf65dc5c6": "2026-10-26 仓库重建版",
    },
    "gemm_soc.hwh": {
        "3b54a09cd5a5fb3fecfc17ae96796475": "2026-10-25 板端实测版",
        "509b0336b112d0969d65c7757f621515": "2026-10-26 仓库重建版",
    },
}

# GEMM 控制寄存器偏移（来自 xgemm_top_hw.h）
AP_CTRL = 0x00      # bit0 ap_start, bit1 ap_done, bit2 ap_idle
REG_M   = 0x10
REG_K   = 0x18
REG_N   = 0x20

# AXI DMA 通道状态寄存器 DMASR 偏移
DMA_DMASR   = 0x04
DMA_HALTED  = 1 << 0
DMA_IDLE    = 1 << 1
DMA_ERRBITS = (1 << 4) | (1 << 5) | (1 << 6)   # DMAIntErr / DMASlvErr / DMADecErr
DMA_IOC_IRQ = 1 << 12


def dma_stat(chan):
    return chan._mmio.read(DMA_DMASR)


def wait_mm2s_idle(chan, timeout=60.0):
    """等待 MM2S(发送) 通道跑完（Idle=1 或 IOC 置位）。输入正常时应很快完成。"""
    t0 = time.time()
    seen_busy = False
    while time.time() - t0 < timeout:
        s = dma_stat(chan)
        if s & DMA_ERRBITS:
            raise RuntimeError("MM2S DMA error, DMASR=0x%04x" % s)
        if (s & DMA_IDLE) == 0:
            seen_busy = True
        if (s & DMA_IOC_IRQ) or (seen_busy and (s & DMA_IDLE)):
            return
        time.sleep(0.0005)
    raise RuntimeError("MM2S DMA timeout, DMASR=0x%04x" % dma_stat(chan))


def wait_ap_done(gemm, timeout=120.0):
    """以 HLS 核 ap_done(bit1) 作为计算完成的权威判据。返回耗时。"""
    t0 = time.time()
    while time.time() - t0 < timeout:
        if gemm.read(AP_CTRL) & 0x2:
            return time.time() - t0
        time.sleep(0.0005)
    raise RuntimeError("GEMM ap_done timeout, ap_ctrl=0x%x" % gemm.read(AP_CTRL))


def s2mm_normal_completed(chan):
    """S2MM 是否正常收到 TLAST 并置 IOC。"""
    s = dma_stat(chan)
    return (s & DMA_IOC_IRQ) != 0, s


def reset_s2mm(chan):
    """旧 bit 缺 TLAST 时，数据已在缓冲但通道仍 Running，stop/start 复位以便复用。"""
    try:
        chan.stop()
        time.sleep(0.002)
        chan.start()
    except Exception as e:
        print("[WARN] 复位 S2MM 通道异常（可忽略）:", e)


def sync_to_device(buf):
    if hasattr(buf, "sync_to_device"):
        buf.sync_to_device()
    elif hasattr(buf, "flush"):
        buf.flush()


def sync_from_device(buf):
    if hasattr(buf, "sync_from_device"):
        buf.sync_from_device()
    elif hasattr(buf, "invalidate"):
        buf.invalidate()


def find_file(here, name):
    """兼容 bin 放在脚本同目录或 data/ 子目录。"""
    for p in (os.path.join(here, name), os.path.join(here, "data", name)):
        if os.path.exists(p):
            return p
    return os.path.join(here, name)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", default="gemm_soc.bit")
    ap.add_argument("--small", action="store_true", help="小数据 M=32 快速验证")
    ap.add_argument("--cpu", action="store_true", help="打印 PS CPU(numpy) 参考耗时/加速比")
    args = ap.parse_args()

    M = 32 if args.small else 12864
    tag = "_small" if args.small else ""
    here = os.path.dirname(os.path.abspath(__file__))

    from pynq import Overlay, allocate
    from pynq.ps import Clocks

    ol = Overlay(os.path.join(here, args.overlay))
    print("Overlay 加载完成，IP 列表:", list(ol.ip_dict.keys()))
    Clocks.fclk0_mhz = 100.0          # 设计时钟 100MHz，显式设置避免继承默认频率

    # 兼容旧 bit：实例化 IP 驱动前清空未连接/不规范的中断描述，让 DMA 走轮询路径。
    # 新 bit 中断接对后该操作也不影响功能（本驱动本就用寄存器轮询）。
    for _n, _d in ol.ip_dict.items():
        if _d.get("interrupts"):
            _d["interrupts"] = {}

    dmaA = ol.dma_A                   # MM2S：内存 -> 流（A）
    dmaB = ol.dma_B                   # MM2S：内存 -> 流（B）
    dmaC = ol.dma_C                   # S2MM：流 -> 内存（C）
    gemm = ol.gemm_top_0

    # ---- 启动自检：版本指纹 + bit/hwh 的 MD5 + hwh 长度位（防止“以为替换了”） ----
    bit_path = os.path.join(here, args.overlay)
    hwh_path = os.path.splitext(bit_path)[0] + ".hwh"
    print("=" * 64)
    print("GEMM 板端驱动版本：%s" % DRIVER_VERSION)
    print("（若看不到这一行，说明板上 gemm_board.py 还是旧版，没更新成功）")
    print("=" * 64)

    def _md5(p):
        try:
            import hashlib
            h = hashlib.md5()
            with open(p, "rb") as f:
                for blk in iter(lambda: f.read(1 << 20), b""):
                    h.update(blk)
            return h.hexdigest(), os.path.getsize(p)
        except Exception as e:
            return "读不到(%s)" % e, -1

    for fn in ("gemm_soc.bit", "gemm_soc.hwh"):
        m, sz = _md5(os.path.join(here, fn))
        known = EXPECT_MD5.get(fn, {})
        if m in known:
            verdict = "OK 已知版本：%s" % known[m]
        else:
            verdict = "**未知版本！请核对是否覆盖成功**（已知：%s）" % "、".join(known.values())
        print("[MD5 ] %-13s %s  %d 字节  %s" % (fn, m, sz, verdict))

    try:
        with open(hwh_path, "r", errors="ignore") as _f:
            _hwh = _f.read()
        import re as _re
        _lw = sorted(set(_re.findall(r"C_SG_LENGTH_WIDTH[^>]*VALUE=\"(\d+)\"", _hwh)))
        _sg = sorted(set(_re.findall(r"C_INCLUDE_SG[^>]*VALUE=\"(\d+)\"", _hwh)))
    except Exception as _e:
        _lw, _sg = ["读不到:%s" % _e], []
    print("[BIT ] 加载文件:", bit_path)
    print("[BIT ] hwh 内 C_SG_LENGTH_WIDTH=%s  C_INCLUDE_SG=%s（新bit应为 23 / 0）" % (_lw, _sg))
    try:
        print("[DMA ] PYNQ 单次上限: A=%d B=%d C=%d 字节"
              % (dmaA.sendchannel._size, dmaB.sendchannel._size,
                 dmaC.recvchannel._size))
    except Exception as _e:
        print("[DMA ] 读取上限失败:", _e)

    # ---- 连续物理内存缓冲（int16，与 AXIS 16 位流对齐） ----
    bufA = allocate(shape=(M * K,), dtype=np.int16)
    bufB = allocate(shape=(K * N,), dtype=np.int16)
    bufC = allocate(shape=(M * N,), dtype=np.int16)
    print("[INFO] 缓冲(字节) A=%d B=%d C=%d" % (bufA.nbytes, bufB.nbytes, bufC.nbytes))

    # 若板上仍是旧 16KB hwh，提前给出明确、可操作的报错（而不是让 PYNQ 在 transfer 里抛）
    need = max(bufA.nbytes, bufB.nbytes, bufC.nbytes)
    cap = dmaC.recvchannel._size
    if cap < need:
        print("\n[FATAL] 板上仍是旧 bit/hwh：DMA 单次上限=%d，但需要 %d 字节。" % (cap, need))
        print("[FATAL] 请在电脑上重新把新生成的 gemm_soc.bit 和 gemm_soc.hwh 覆盖到 /home/xilinx/board：")
        print("[FATAL]   scp D:\\qiansai\\gemm_vivado_doubao\\board\\gemm_soc.bit  xilinx@192.168.2.99:/home/xilinx/board/")
        print("[FATAL]   scp D:\\qiansai\\gemm_vivado_doubao\\board\\gemm_soc.hwh  xilinx@192.168.2.99:/home/xilinx/board/")
        print("[FATAL] 覆盖后务必【断电重启板子或重开 Python】，再运行本脚本。")
        raise SystemExit(2)

    # ---- 装入输入数据 ----
    A = np.fromfile(find_file(here, "a%s.bin" % tag), dtype=np.int16)
    B = np.fromfile(find_file(here, "b%s.bin" % tag), dtype=np.int16)
    Cref = np.fromfile(find_file(here, "c_ref%s.bin" % tag), dtype=np.float32)
    assert A.size == M * K and B.size == K * N and Cref.size == M * N, "数据数量不匹配"
    bufA[:] = A
    bufB[:] = B
    sync_to_device(bufA)
    sync_to_device(bufB)

    # ---- 写维度参数并回读确认 ----
    gemm.write(REG_M, M)
    gemm.write(REG_K, K)
    gemm.write(REG_N, N)
    print("[DEBUG] READ_BACK M=%s K=%s N=%s  启动前 ap_ctrl=0x%x" %
          (gemm.read(REG_M), gemm.read(REG_K), gemm.read(REG_N), gemm.read(AP_CTRL)))

    # ---- 启动顺序：先武装 C 接收，再发 A/B，最后 ap_start=1（不写 0） ----
    dmaC.recvchannel.transfer(bufC)
    dmaA.sendchannel.transfer(bufA)
    dmaB.sendchannel.transfer(bufB)
    gemm.write(AP_CTRL, 0x1)

    # ---- 等待输入发完 + 计算完成（ap_done 权威） ----
    wait_mm2s_idle(dmaA.sendchannel)
    wait_mm2s_idle(dmaB.sendchannel)
    hw_dt = wait_ap_done(gemm)

    # ---- 检查 S2MM：新 bit 应正常收到 TLAST（IOC=1） ----
    ok, s = s2mm_normal_completed(dmaC.recvchannel)
    if ok:
        print("[DEBUG] S2MM 正常收到 TLAST，DMASR=0x%04x" % s)
    else:
        print("[WARN] S2MM 未置 IOC（DMASR=0x%04x，旧 bit 缺 TLAST）；数据已在缓冲，复位通道以复用。" % s)
        reset_s2mm(dmaC.recvchannel)

    print("[DEBUG] ap_ctrl=0x%x  硬件耗时 %.4f s" % (gemm.read(AP_CTRL), hw_dt))

    sync_from_device(bufC)
    Chw = bufC.astype(np.float32) / Q12

    # ---- 与金标准比对 ----
    diff = np.abs(Chw - Cref)
    max_diff = float(diff.max())
    err_cnt = int((diff > TOL).sum())
    print("前 8 个 hw :", np.round(Chw[:8], 6))
    print("前 8 个 ref:", np.round(Cref[:8], 6))
    print("末 8 个 hw :", np.round(Chw[-8:], 6))
    print("末 8 个 ref:", np.round(Cref[-8:], 6))
    print("max_diff = %.6f  超容差(%g)点数 = %d / %d" % (max_diff, TOL, err_cnt, M * N))

    # ---- 可选：PS CPU(numpy) 参考耗时与加速比 ----
    if args.cpu:
        Af = A.astype(np.float32) / Q12
        Bf = B.astype(np.float32).reshape(K, N) / Q12
        # 预热一次
        _ = np.dot(Af.reshape(M, K), Bf)
        t0 = time.time()
        for _ in range(3):
            Ccpu = np.dot(Af.reshape(M, K), Bf)
        cpu_dt = (time.time() - t0) / 3.0
        print("[BENCH] PS CPU(numpy) 耗时 %.4f s，硬件 %.4f s，加速比 %.2fx" %
              (cpu_dt, hw_dt, cpu_dt / hw_dt if hw_dt > 0 else float("nan")))

    if err_cnt == 0:
        print("==== 板级 GEMM 验证 PASS ====")
    else:
        print("==== 板级 GEMM 验证 FAIL ====")

    Chw.tofile(os.path.join(here, "c_hw%s.bin" % tag))
    return err_cnt


if __name__ == "__main__":
    raise SystemExit(main())
