#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PYNQ-Z2 板端声音检测主程序
录音(arecord) -> 梅尔频谱(numpy) -> ncnn推理 -> 超阈值写触发文件
用法: python3 sound_board.py [--threshold 0.985] [--cooldown 3]
"""
import argparse, json, os, struct, subprocess, sys, tempfile, time
import numpy as np

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ============ 配置 ============
with open(os.path.join(BASE_DIR, "sound_config.json")) as f:
    CFG = json.load(f)

SR = CFG["sr"]              # 32000
N_FFT = CFG["n_fft"]        # 1024
HOP = CFG["hop_length"]     # 320
N_MELS = CFG["n_mels"]      # 64
CLIP_SEC = CFG["clip_sec"]  # 2.0
CLIP_SAMPLES = int(SR * CLIP_SEC)
NORM_MEAN = CFG["norm_mean"]
NORM_STD = CFG["norm_std"]
THRESHOLD = CFG["threshold"]

# 梅尔滤波器组（PC上预计算）
MEL_BASIS = np.load(os.path.join(BASE_DIR, "mel_basis.npy"))  # [64, 513]

# 触发文件路径（和图像端约定，都在项目根目录的 runtime/trigger/）
TRIGGER_DIR = os.path.join(BASE_DIR, "runtime", "trigger")
TRIGGER_FILE = "pitta.trigger"

# ncnn 推理程序
INFER_BIN = os.path.join(BASE_DIR, "sound_infer_ncnn")

# ============ 梅尔频谱（numpy，与 librosa 一致）============
def mel_spec(y):
    y = np.pad(y, N_FFT // 2, mode="constant")
    n_frames = 1 + (len(y) - N_FFT) // HOP
    window = np.hanning(N_FFT + 1)[:N_FFT].astype(np.float32)
    stft = np.zeros((N_FFT // 2 + 1, n_frames), dtype=np.complex64)
    for i in range(n_frames):
        frame = y[i * HOP : i * HOP + N_FFT] * window
        stft[:, i] = np.fft.rfft(frame)
    power = np.abs(stft) ** 2.0
    mel = np.dot(MEL_BASIS, power)
    mel = np.maximum(mel, 1e-10)
    db = 10.0 * np.log10(mel / np.max(mel))
    db = np.maximum(db, np.max(db) - 80.0)
    return db.astype(np.float32)

# ============ WAV 读取（不用 soundfile/librosa）============
def read_wav(path):
    """读取 16bit PCM WAV，返回 float32 数组 [-1, 1]。"""
    with open(path, "rb") as f:
        data = f.read()
    # 找 data chunk
    idx = data.find(b"data")
    if idx < 0:
        raise ValueError("不是有效WAV文件")
    audio_start = idx + 8
    raw = data[audio_start:]
    # 16bit signed little-endian
    n_samples = len(raw) // 2
    pcm = np.frombuffer(raw[:n_samples * 2], dtype=np.int16).astype(np.float32)
    return pcm / 32768.0

# ============ 录音（多方式自动适配）============
_rec_method = None
_rec_device = None

def _detect_audio_device():
    """从 /proc/asound/cards 找USB音频设备(摄像头麦克风)，返回 plughw:X,0"""
    try:
        with open("/proc/asound/cards") as f:
            cards = f.read()
        # 找包含 USB/UVC/Camera/Mic 的声卡
        for line in cards.splitlines():
            line = line.strip()
            if line and line[0].isdigit():
                idx = line[0]
                low = line.lower()
                if any(k in low for k in ["usb", "uvc", "camera", "mic", "audio"]):
                    return "plughw:%s,0" % idx
        # 没找到USB的，返回第一个非HDMI声卡
        for line in cards.splitlines():
            line = line.strip()
            if line and line[0].isdigit() and "hdmi" not in line.lower():
                return "plughw:%s,0" % line[0]
    except:
        pass
    return "plughw:1,0"  # 默认

def record_clip(seconds, wav_path):
    """自动选择录音方式: arecord -> ffmpeg -> sounddevice -> alsaaudio"""
    global _rec_method, _rec_device
    if _rec_device is None:
        _rec_device = _detect_audio_device()
        print("音频设备: %s" % _rec_device)

    # 方式1: arecord
    if _rec_method in (None, "arecord"):
        try:
            cmd = ["arecord", "-D", _rec_device, "-f", "S16_LE",
                   "-r", str(SR), "-c", "1", "-d", str(seconds),
                   "-t", "wav", "-q", wav_path]
            ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if ret.returncode == 0:
                _rec_method = "arecord"
                return read_wav(wav_path)
        except FileNotFoundError:
            pass

    # 方式2: ffmpeg
    if _rec_method in (None, "ffmpeg"):
        try:
            cmd = ["ffmpeg", "-y", "-f", "alsa", "-i", _rec_device,
                   "-t", str(seconds), "-ar", str(SR), "-ac", "1",
                   "-f", "wav", wav_path]
            ret = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            if ret.returncode == 0:
                _rec_method = "ffmpeg"
                return read_wav(wav_path)
        except FileNotFoundError:
            pass

    # 方式3: Python sounddevice
    if _rec_method in (None, "sounddevice"):
        try:
            import sounddevice as sd
            y = sd.rec(int(seconds * SR), samplerate=SR, channels=1, dtype="int16")
            sd.wait()
            _rec_method = "sounddevice"
            return y.flatten().astype(np.float32) / 32768.0
        except ImportError:
            pass

    # 方式4: pyalsaaudio
    if _rec_method in (None, "alsaaudio"):
        try:
            import alsaaudio
            inp = alsaaudio.PCM(alsaaudio.PCM_CAPTURE, device=_rec_device)
            inp.setchannels(1)
            inp.setrate(SR)
            inp.setformat(alsaaudio.PCM_FORMAT_S16_LE)
            frames = []
            total = int(seconds * SR)
            while sum(len(f) for f in frames) < total:
                l, data = inp.read()
                if l > 0:
                    frames.append(data)
            raw = b"".join(frames)[:total * 2]
            pcm = np.frombuffer(raw, dtype=np.int16).astype(np.float32)
            _rec_method = "alsaaudio"
            return pcm / 32768.0
        except ImportError:
            pass

    # 方式5: ctypes 直接调用 libasound.so (PYNQ自带,无需安装)
    if _rec_method in (None, "libasound"):
        try:
            import ctypes
            import ctypes.util
            lib_path = ctypes.util.find_library("asound") or "libasound.so.2"
            asound = ctypes.CDLL(lib_path)

            SND_PCM_STREAM_CAPTURE = 1
            SND_PCM_FORMAT_S16_LE = 2
            SND_PCM_ACCESS_RW_INTERLEAVED = 3

            handle = ctypes.c_void_p()
            dev_name = _rec_device.encode("utf-8")
            rc = asound.snd_pcm_open(ctypes.byref(handle), dev_name,
                                       SND_PCM_STREAM_CAPTURE, 0)
            if rc < 0:
                raise RuntimeError("snd_pcm_open failed: %d" % rc)

            # set_params: format, access, channels, rate, soft_resample, latency
            rc = asound.snd_pcm_set_params(handle, SND_PCM_FORMAT_S16_LE,
                                             SND_PCM_ACCESS_RW_INTERLEAVED,
                                             1, SR, 1, 500000)
            if rc < 0:
                asound.snd_pcm_close(handle)
                raise RuntimeError("snd_pcm_set_params failed: %d" % rc)

            asound.snd_pcm_prepare(handle)

            # 读 N 帧 (16bit mono = 2 bytes/frame)
            total_frames = int(seconds * SR)
            buf = ctypes.create_string_buffer(total_frames * 2)
            read_frames = 0
            while read_frames < total_frames:
                n = asound.snd_pcm_readi(handle, ctypes.byref(buf, read_frames * 2),
                                           total_frames - read_frames)
                if n < 0:
                    asound.snd_pcm_prepare(handle)
                    continue
                read_frames += n

            asound.snd_pcm_close(handle)
            pcm = np.frombuffer(buf.raw[:read_frames * 2], dtype=np.int16).astype(np.float32)
            _rec_method = "libasound"
            return pcm / 32768.0
        except Exception as e:
            if _rec_method is None:
                print("libasound方式失败: %s" % str(e))

    raise RuntimeError("没有可用的录音工具(arecord/ffmpeg/sounddevice/alsaaudio/libasound都没有)")

# ============ 推理 ============
def infer(mel_data):
    """梅尔频谱 -> ncnn -> 概率。"""
    # 归一化
    mel_norm = ((mel_data - NORM_MEAN) / NORM_STD).astype(np.float32)
    # 写临时原始文件
    tmp = tempfile.NamedTemporaryFile(suffix=".raw", delete=False)
    tmp.close()
    try:
        mel_norm.tofile(tmp.name)
        ret = subprocess.run(
            [INFER_BIN, BASE_DIR, tmp.name],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
        prob = float(ret.stdout.decode("utf-8").strip())
        return prob
    finally:
        os.unlink(tmp.name)

# ============ 主循环 ============
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--threshold", type=float, default=THRESHOLD)
    ap.add_argument("--cooldown", type=float, default=3.0)
    ap.add_argument("--once", action="store_true", help="只跑一次（测试用）")
    args = ap.parse_args()

    os.makedirs(TRIGGER_DIR, exist_ok=True)
    tmp_wav = os.path.join(tempfile.gettempdir(), "pitta_clip.wav")

    print("声音检测启动")
    print("阈值: %.4f, 冷却: %.1fs, 采样率: %d" % (args.threshold, args.cooldown, SR))
    print("触发文件: %s" % os.path.join(TRIGGER_DIR, TRIGGER_FILE))
    print("按 Ctrl+C 退出")

    last_trigger = 0
    try:
        while True:
            t0 = time.time()
            # 录音 2 秒
            y = record_clip(CLIP_SEC, tmp_wav)
            # 梅尔频谱
            mel = mel_spec(y)
            # 推理
            prob = infer(mel)
            dt = time.time() - t0

            status = "🔴" if prob >= args.threshold else "  "
            print("%s [%.1fs] 概率=%.4f 阈值=%.4f" % (status, dt, prob, args.threshold))

            # 超阈值且过了冷却期 -> 写触发
            if prob >= args.threshold and (time.time() - last_trigger) > args.cooldown:
                trigger_path = os.path.join(TRIGGER_DIR, TRIGGER_FILE)
                with open(trigger_path, "w") as f:
                    f.write("sound trigger prob=%.4f time=%d" % (prob, int(time.time())))
                last_trigger = time.time()
                print(">>> 已写触发文件!")

            if args.once:
                break
    except KeyboardInterrupt:
        print("\n已停止")

if __name__ == "__main__":
    main()
