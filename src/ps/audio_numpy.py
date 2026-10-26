# -*- coding: utf-8 -*-
"""
板端音频推理：纯 numpy 实现，不依赖 torch / librosa。
加载 export_audio_model.py 生成的 audio_model.npz，
对 2 秒 32kHz 单声道音频输出仙八色鸫鸣声分数。

在 PC 上可直接用 test_audio_numpy.py 验证与 torch 结果一致。
"""
import numpy as np


class NumpyBirdCNN:
    def __init__(self, npz_path):
        d = np.load(npz_path, allow_pickle=True)
        self.sr = int(d["sr"])
        self.n_fft = int(d["n_fft"])
        self.hop = int(d["hop_length"])
        self.n_mels = int(d["n_mels"])
        self.power = float(d["power"])
        self.top_db = float(d["top_db"])
        self.pad_mode = str(d["pad_mode"])
        self.mel_fb = d["mel_fb"]
        self.window = d["window"]
        self.mean = float(d["mean"])
        self.std = float(d["std"])
        self.threshold = float(d["threshold"])

        self.conv1_w = d["conv1_w"]; self.bn1_w = d["bn1_w"]; self.bn1_b = d["bn1_b"]
        self.bn1_mean = d["bn1_mean"]; self.bn1_var = d["bn1_var"]
        self.conv2_w = d["conv2_w"]; self.bn2_w = d["bn2_w"]; self.bn2_b = d["bn2_b"]
        self.bn2_mean = d["bn2_mean"]; self.bn2_var = d["bn2_var"]
        self.conv3_w = d["conv3_w"]; self.bn3_w = d["bn3_w"]; self.bn3_b = d["bn3_b"]
        self.bn3_mean = d["bn3_mean"]; self.bn3_var = d["bn3_var"]
        self.fc_w = d["fc_w"]; self.fc_b = d["fc_b"]

    # ---------- 特征提取 ----------
    def _stft(self, y):
        """center=True 的 STFT（power 谱），输出 (n_fft//2+1, n_frames)。"""
        n_fft = self.n_fft
        pad = n_fft // 2
        # librosa center=True: pad_mode='constant' 即前后补零
        y = np.pad(y, pad, mode="constant")
        n_frames = 1 + (len(y) - n_fft) // self.hop
        # 用 stride 取窗（不复制数据）
        shape = (n_frames, n_fft)
        strides = (y.strides[0] * self.hop, y.strides[0])
        frames = np.lib.stride_tricks.as_strided(
            y, shape=shape, strides=strides, writeable=False
        )
        frames = frames * self.window
        spec = np.fft.rfft(frames, n=n_fft, axis=1)
        mag = (spec.real ** 2 + spec.imag ** 2) ** (self.power / 2.0)
        return mag.T.astype(np.float32)  # (freq, time)

    def _power_to_db(self, S):
        amin = 1e-10
        ref = np.max(S)
        log_spec = 10.0 * np.log10(np.maximum(amin, S))
        log_spec -= 10.0 * np.log10(np.maximum(amin, ref))
        if self.top_db is not None:
            log_spec = np.maximum(log_spec, log_spec.max() - self.top_db)
        return log_spec.astype(np.float32)

    def feature(self, y):
        """y: 2 秒 32kHz float32，返回 (n_mels, n_frames) 的 log-mel。"""
        S = self._stft(np.ascontiguousarray(y, dtype=np.float32))
        mel = self.mel_fb @ S
        return self._power_to_db(mel)

    # ---------- 卷积前向 ----------
    @staticmethod
    def _conv2d(x, w, pad=1):
        """x:(C,H,W) w:(outC,inC,3,3), same padding, stride 1。"""
        xp = np.pad(x, ((0, 0), (pad, pad), (pad, pad)), mode="constant")
        out_c, in_c, kh, kw = w.shape
        H, W = x.shape[1], x.shape[2]
        out = np.zeros((out_c, H, W), dtype=np.float32)
        for i in range(kh):
            for j in range(kw):
                # x patch: (in_c, H, W)
                patch = xp[:, i:i + H, j:j + W]
                # 卷积核该位置: (out_c, in_c)
                out += np.einsum("oc,chw->ohw", w[:, :, i, j], patch)
        return out

    @staticmethod
    def _batchnorm(x, gamma, beta, mean, var, eps=1e-5):
        # x: (C, H, W)
        scale = gamma / np.sqrt(var + eps)
        shift = beta - mean * scale
        return x * scale[:, None, None] + shift[:, None, None]

    @staticmethod
    def _maxpool2(x):
        """2x2 stride 2。"""
        C, H, W = x.shape
        H2, W2 = H // 2, W // 2
        x = x[:, :H2 * 2, :W2 * 2]
        return x.reshape(C, H2, 2, W2, 2).max(axis=(2, 4))

    @staticmethod
    def _adaptive_avg_pool(x, out_h, out_w):
        """PyTorch AdaptiveAvgPool2d 通用实现。"""
        C, H, W = x.shape
        out = np.zeros((C, out_h, out_w), dtype=np.float32)
        for i in range(out_h):
            hs = i * H // out_h
            he = (i + 1) * H // out_h
            for j in range(out_w):
                ws = j * W // out_w
                we = (j + 1) * W // out_w
                out[:, i, j] = x[:, hs:he, ws:we].mean(axis=(1, 2))
        return out

    def _forward(self, x):
        # x: (1, n_mels, n_frames)
        x = self._conv2d(x, self.conv1_w)
        x = self._batchnorm(x, self.bn1_w, self.bn1_b, self.bn1_mean, self.bn1_var)
        x = np.maximum(x, 0)
        x = self._maxpool2(x)

        x = self._conv2d(x, self.conv2_w)
        x = self._batchnorm(x, self.bn2_w, self.bn2_b, self.bn2_mean, self.bn2_var)
        x = np.maximum(x, 0)
        x = self._maxpool2(x)

        x = self._conv2d(x, self.conv3_w)
        x = self._batchnorm(x, self.bn3_w, self.bn3_b, self.bn3_mean, self.bn3_var)
        x = np.maximum(x, 0)
        x = self._maxpool2(x)

        x = self._adaptive_avg_pool(x, 4, 1)
        x = x.reshape(-1)
        logit = (self.fc_w @ x + self.fc_b).reshape(-1)[0]
        return float(logit)

    @staticmethod
    def _sigmoid(z):
        return 1.0 / (1.0 + np.exp(-z))

    def predict(self, y):
        """y: 2 秒 32kHz 单声道音频，返回 0~1 目标分数。"""
        feat = self.feature(y)
        feat = (feat - self.mean) / self.std
        x = feat[None, :, :]
        return self._sigmoid(self._forward(x))
