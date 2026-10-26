#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INMP441 连续录音（分包模式，MMIO 轮询，不依赖中断）
i2s_mems_rx 输出连续 AXI-Stream、TLAST 恒为 0；本脚本把 S2MM 的 buffer 长度设为
PKT_BEATS=2048 个 32bit 样本，DMA 收满一个 buffer 即置完成标志，软件据此分"包"读取。
用 MMIO 直接操作 DMA 寄存器、轮询状态寄存器判断每个 buffer 完成，不创建 pynq DMA
驱动，避免中断绑定报错。自动选择有声音的声道(L/R)，并额外保存左右声道文件供核对。

用法:
    sudo python3 inmp441_record.py --overlay inmp441.bit --seconds 5 --wav out.wav
"""
import argparse, os, time, wave
import numpy as np

PKT_BEATS = 2048     # 软件侧 S2MM buffer 长度（个 32bit 样本）；硬件 TLAST 恒0，无此参数
FS = 32000
BEATS_PER_FRAME = 2  # 硬件输出 [L, R]，每帧 2 个 32bit

# ---- AXI DMA S2MM 寄存器偏移 ----
S2MM_CR, S2MM_SR = 0x30, 0x34
S2MM_DA_L, S2MM_DA_H, S2MM_LEN = 0x48, 0x4C, 0x58
CR_RS, CR_RESET = 0x1, 0x4
SR_ERRBITS = 0x70          # bit4/5/6: 内部/从机/译码错误
SR_IOC = 0x1000            # bit12: 完成标志


def reset_dma(mmio):
    mmio.write(S2MM_CR, CR_RESET)
    end = time.monotonic() + 2.0
    while mmio.read(S2MM_CR) & CR_RESET:
        if time.monotonic() >= end:
            raise RuntimeError("DMA 软复位未完成")
        time.sleep(0.001)


def recv_packet(mmio, buf, n_bytes):
    reset_dma(mmio)
    mmio.write(S2MM_SR, 0x7000)   # W1C 清除旧状态
    buf.flush()
    mmio.write(S2MM_CR, CR_RS)    # Run，不使能中断
    end = time.monotonic() + 2.0
    while mmio.read(S2MM_SR) & 0x1:  # 等 Halted 清零
        if time.monotonic() >= end:
            break
        time.sleep(0.001)
    pa = int(buf.physical_address)
    mmio.write(S2MM_DA_L, pa & 0xffffffff)
    mmio.write(S2MM_DA_H, (pa >> 32) & 0xffffffff)
    mmio.write(S2MM_LEN, n_bytes)
    end = time.monotonic() + 2.0
    while True:
        sr = mmio.read(S2MM_SR)
        if sr & SR_ERRBITS:
            raise RuntimeError("DMA 错误 SR=0x%08x" % sr)
        if sr & SR_IOC:
            return mmio.read(S2MM_LEN) & 0x007fffff   # 实际写入字节数
        if time.monotonic() >= end:
            raise RuntimeError("DMA 超时 SR=0x%08x" % sr)
        time.sleep(0.002)


def save_mono_wav(path, ch32):
    # 硬件: 24bit 符号扩展到32bit(数值不变，不是左移)，归一化后转16bit WAV
    f = ch32.astype(np.float64) / float(2 ** 23)
    pcm = np.clip(np.rint(f * 32768.0), -32768, 32767).astype('<i2')
    with wave.open(path, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(FS)
        w.writeframes(pcm.tobytes())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", default="inmp441.bit")
    ap.add_argument("--seconds", type=float, default=5.0)
    ap.add_argument("--wav", default="inmp441.wav")
    ap.add_argument("--dma-name", default="axi_dma_0")
    args = ap.parse_args()

    from pynq import Overlay, allocate, MMIO
    from pynq.ps import Clocks

    ol = Overlay(os.path.abspath(args.overlay))
    if args.dma_name not in ol.ip_dict:
        raise RuntimeError("未找到 %s；IP 列表: %s" %
                           (args.dma_name, list(ol.ip_dict)))
    info = ol.ip_dict[args.dma_name]
    mmio = MMIO(info['phys_addr'], info['addr_range'])

    # 硬件按 100MHz 设计，下载后显式设置
    Clocks.fclk0_mhz = 100.0
    time.sleep(0.1)

    total_frames = int(FS * args.seconds)
    need_beats = total_frames * BEATS_PER_FRAME
    # 缓冲区向上取整到 PKT_BEATS 整数倍，保证每个包都是完整对齐的包
    total_beats = int(np.ceil(need_beats / float(PKT_BEATS))) * PKT_BEATS
    n_packets = total_beats // PKT_BEATS

    buf = allocate(shape=(PKT_BEATS,), dtype=np.int32)
    chunks = []
    got_beats = 0
    print("开始录音 %.1f 秒，共 %d 个数据包（每包%d beats）..." %
          (args.seconds, n_packets, PKT_BEATS))
    t0 = time.time()
    for _ in range(n_packets):
        actual_bytes = recv_packet(mmio, buf, PKT_BEATS * 4)
        buf.invalidate()
        actual_words = actual_bytes // 4
        chunks.append(buf[:actual_words].copy())
        got_beats += actual_words
    print("录音完成，实际耗时 %.2fs，收到 %d beats" %
          (time.time() - t0, got_beats))

    raw = np.concatenate(chunks).astype(np.int32)
    audio = raw.reshape(-1, BEATS_PER_FRAME)
    audio = audio[:total_frames]          # 截断到所需时长
    left, right = audio[:, 0], audio[:, 1]

    l_rms = float(np.sqrt(np.mean(left.astype(np.float64) ** 2)))
    r_rms = float(np.sqrt(np.mean(right.astype(np.float64) ** 2)))
    sel = left if l_rms >= r_rms else right
    print("声道 RMS: L=%.1f  R=%.1f  -> 选择 %s 声道" %
          (l_rms, r_rms, "左" if l_rms >= r_rms else "右"))

    save_mono_wav(args.wav, sel)
    print("已保存主录音: %s (%d 帧, %.2fs)" %
          (args.wav, len(sel), len(sel) / float(FS)))

    base = os.path.splitext(args.wav)[0]
    save_mono_wav(base + "_left.wav", left)
    save_mono_wav(base + "_right.wav", right)
    print("另存 %s_left.wav / %s_right.wav 供核对" % (base, base))


if __name__ == "__main__":
    main()
