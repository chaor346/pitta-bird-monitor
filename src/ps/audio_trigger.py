#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
INMP441 鸟鸣触发器（PYNQ-Z2）
DMA录音(滑动窗口2s/0.5s) -> NumpyBirdCNN -> 超阈值写 runtime/trigger/pitta.trigger
用法: sudo python3 audio_trigger.py [--threshold 0.985] [--cooldown 3] [--seconds 0]
"""
import os
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
os.environ.setdefault("OMP_NUM_THREADS", "1")
import argparse, time
import numpy as np
from pynq import Overlay, allocate, MMIO
from pynq.ps import Clocks
import inmp441_record as driver
from audio_numpy import NumpyBirdCNN

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TRIGGER_DIR = os.path.join(BASE_DIR, "runtime", "trigger")
TRIGGER_FILE = "pitta.trigger"

FS = 32000
WINDOW = 64000  # 2秒


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--overlay", default="inmp441.bit")
    ap.add_argument("--model", default=os.path.join(BASE_DIR, "audio_model.npz"))
    ap.add_argument("--threshold", type=float, default=None)
    ap.add_argument("--cooldown", type=float, default=3.0)
    ap.add_argument("--hop", type=float, default=0.5)
    ap.add_argument("--channel", type=int, default=0, choices=[0, 1])
    ap.add_argument("--seconds", type=float, default=0, help="0=无限")
    ap.add_argument("--min-hits", type=int, default=2)
    args = ap.parse_args()

    os.makedirs(TRIGGER_DIR, exist_ok=True)

    model = NumpyBirdCNN(args.model)
    threshold = args.threshold if args.threshold is not None else model.threshold
    print("[AUDIO] 模型: sr=%d 阈值=%.4f 窗口=2s hop=%.1fs min_hits=%d"
          % (model.sr, threshold, args.hop, args.min_hits))

    # 加载 overlay
    ol = Overlay(os.path.abspath(args.overlay))
    info = ol.ip_dict["axi_dma_0"]
    mmio = MMIO(info["phys_addr"], info["addr_range"])
    Clocks.fclk0_mhz = 100.0
    time.sleep(0.1)
    print("[AUDIO] DMA @ 0x%08x  FCLK0=%.1fMHz" % (info["phys_addr"], Clocks.fclk0_mhz))

    buf = allocate(shape=(driver.PKT_BEATS,), dtype=np.int32)
    hop_samples = int(round(args.hop * FS))

    # 预热
    warm = model.predict(np.zeros(WINDOW, np.float32))
    print("[AUDIO] 预热完成, 静音概率=%.4f" % warm)

    pending = np.empty(0, np.float32)
    hits = 0
    last_trigger = 0
    start_time = time.monotonic()
    window_count = 0

    print("[AUDIO] 开始监听 (Ctrl+C 退出)...")
    try:
        while True:
            if args.seconds > 0 and time.monotonic() - start_time >= args.seconds:
                break

            # 收一个 DMA 包
            count = driver.recv_packet(mmio, buf, driver.PKT_BEATS * 4)
            if count <= 0 or count > driver.PKT_BEATS * 4 or count % 8:
                print("[AUDIO] 警告: 异常包 bytes=%d" % count)
                continue
            buf.invalidate()
            raw = buf[:count // 4].copy().reshape(-1, 2)

            # 解码 right24（和 inmp441_predict.py 一致）
            u = raw[:, args.channel].astype(np.int64) & 0xffffff
            signed = np.where(u & 0x800000, u - 0x1000000, u)
            pcm16 = np.clip(np.rint(signed / 256.0), -32768, 32767).astype(np.float32)
            pcm = pcm16 / 32768.0

            pending = np.concatenate((pending, pcm))

            # 滑动窗口推理
            while len(pending) >= WINDOW:
                y = pending[:WINDOW].copy()
                pending = pending[hop_samples:]
                window_count += 1

                t0 = time.monotonic()
                score = model.predict(np.ascontiguousarray(y, dtype=np.float32))
                infer_s = time.monotonic() - t0

                rms = 20 * np.log10(max(float(np.sqrt(np.mean(y ** 2))), 1e-12))

                if score >= threshold:
                    hits += 1
                else:
                    hits = 0

                now = time.time()
                triggered = hits >= args.min_hits and (now - last_trigger) >= args.cooldown

                flag = "*** 触发!" if triggered else ("  +" if hits > 0 else "   ")
                print("[AUDIO] #%d score=%.4f rms=%.1fdB hits=%d infer=%.3fs%s"
                      % (window_count, score, rms, hits, infer_s, flag))

                if triggered:
                    tp = os.path.join(TRIGGER_DIR, TRIGGER_FILE)
                    with open(tp, "w") as f:
                        f.write("sound trigger score=%.4f time=%d" % (score, int(now)))
                    last_trigger = now
                    hits = 0
                    print(">>> [AUDIO] 检测到鸟鸣! 已写触发文件: %s" % tp)

    except KeyboardInterrupt:
        print("\n[AUDIO] 已停止")
    finally:
        try:
            driver.reset_dma(mmio)
        except Exception:
            pass
        try:
            buf.freebuffer()
        except Exception:
            pass


if __name__ == "__main__":
    main()
