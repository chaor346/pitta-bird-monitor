#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
板端音频监听：sounddevice 采集 + 纯 numpy 音频模型。
不依赖 torch / librosa。
"""
import queue
import threading
import time

import numpy as np
import sounddevice as sd

from audio_numpy import NumpyBirdCNN


class AudioListener:
    def __init__(self, model_npz, threshold=0.5, min_hits=2, cooldown_sec=30,
                 device=None, channel=1, on_trigger=None, on_score=None):
        self.model = NumpyBirdCNN(model_npz)
        self.threshold = threshold
        self.min_hits = min_hits
        self.cooldown_sec = cooldown_sec
        self.device_idx = device
        self.channel = channel
        self.on_trigger = on_trigger
        self.on_score = on_score

        self.target_sr = self.model.sr
        self.win_size = self.target_sr * 2
        self.win_hop = int(self.target_sr * 0.5)

        self._running = False
        self._q = queue.Queue(maxsize=200)
        self._hits = 0
        self._last_trig = 0

    def _cb(self, indata, frames, timing, status):
        if status:
            print("[AUDIO] 状态:", status)
        try:
            self._q.put_nowait(indata[:, self.channel - 1].copy())
        except queue.Full:
            pass

    def _find_device(self):
        devices = sd.query_devices()
        cands = []
        if self.device_idx is not None:
            cands.append(self.device_idx)
        else:
            d = sd.default.device[0]
            if d is not None:
                cands.append(d)
        # 同名回退
        for i, d in enumerate(devices):
            if d["max_input_channels"] > 0 and i not in cands and "bth" not in d["name"].lower():
                cands.append(i)
        for i in cands:
            try:
                info = sd.query_devices(i, "input")
                rate = int(round(info["default_samplerate"]))
                sd.check_input_settings(device=i, channels=self.channel,
                                        dtype="float32", samplerate=rate)
                return i, rate
            except Exception:
                continue
        return None, None

    def _run(self):
        # 仅用于重采样；板子没装 librosa 时用内置线性重采样
        try:
            import librosa
            has_librosa = True
        except ImportError:
            has_librosa = False

        dev, rate = self._find_device()
        if dev is None:
            print("[AUDIO] 打不开任何输入设备")
            return
        print(f"[AUDIO] 设备[{dev}] {sd.query_devices(dev,'input')['name']} @ {rate}Hz")

        cap_win = rate * 2
        cap_hop = int(rate * 0.5)
        buf = np.empty(0, dtype=np.float32)

        with sd.InputStream(device=dev, channels=self.channel, samplerate=rate,
                            dtype="float32", blocksize=rate // 10,
                            callback=self._cb) as st:
            st.start()
            print("[AUDIO] 开始监听，等待仙八色鸫鸣声...")
            while self._running:
                try:
                    block = self._q.get(timeout=2)
                except queue.Empty:
                    continue
                buf = np.concatenate([buf, block])
                while len(buf) >= cap_win:
                    seg = buf[:cap_win].copy()
                    buf = buf[cap_hop:]
                    if rate != self.target_sr:
                        if has_librosa:
                            seg = librosa.resample(seg, orig_sr=rate,
                                                   target_sr=self.target_sr,
                                                   res_type="soxr_hq")
                        else:
                            seg = self._linear_resample(seg, rate, self.target_sr)
                    if len(seg) != self.win_size:
                        continue
                    score = self.model.predict(seg.astype(np.float32))
                    rms = 20 * np.log10(max(
                        float(np.sqrt(np.mean(seg.astype(np.float64) ** 2))), 1e-12))
                    if self.on_score:
                        self.on_score(score, rms)
                    now = time.time()
                    if score >= self.threshold:
                        self._hits += 1
                        if (self._hits >= self.min_hits and
                                now - self._last_trig > self.cooldown_sec):
                            self._last_trig = now
                            self._hits = 0
                            print(f"\n[AUDIO] ★ 检测到仙八色鸫鸣声 score={score:.3f}")
                            if self.on_trigger:
                                self.on_trigger(score)
                    else:
                        self._hits = 0

    @staticmethod
    def _linear_resample(y, sr_in, sr_out):
        n = int(round(len(y) * sr_out / sr_in))
        idx = np.linspace(0, len(y) - 1, n)
        lo = np.floor(idx).astype(int)
        frac = (idx - lo).astype(np.float32)
        hi = np.minimum(lo + 1, len(y) - 1)
        return (y[lo] * (1 - frac) + y[hi] * frac).astype(np.float32)

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
