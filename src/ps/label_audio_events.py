#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 正样本鸟鸣事件 —— 半自动真值标注辅助
=====================================================================
 目的：为"事件级召回率"准备【人工真值】。

 为什么需要它：
   召回率 = 被检出的真值事件 / 全部真值事件。必须先知道每段录音里
   鸟到底在第几秒叫，这是真值，不能用模型自己的高分窗口当真值
   （否则是循环论证，召回率必然虚高）。

 本脚本做什么：
   用一个【独立于模型的信号】——RMS 能量（鸟叫明显比背景响）——
   自动检测有声段，生成候选事件，导出：
     1) events_truth_draft.csv  —— 待你核对/修正的真值草稿
     2) 每段录音一张 PNG        —— 能量包络 + 候选区间 + 模型分数(仅参考)
   你要做的：
     - 听一遍每段录音（9 段共约 12 分钟），对照 PNG；
     - 在 CSV 里删掉误判、补上漏判、修正起止秒；
     - 另存为 events_truth.csv，再用 eval_recall.py 算召回率。

 用法（在装有 librosa/soundfile/matplotlib 的 PC 上）：
   python label_audio_events.py --positive <test_audio/positive> --out truth_draft
=====================================================================
"""
import os
import argparse
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import librosa

SR = 32000
FRAME = 320            # 10 ms 帧
HOP = 320
DB_BELOW = 20.0        # 能量阈值 = 峰值 - 20 dB
MERGE_GAP = 0.30       # 相邻有声段间隔小于 0.30s 则合并
MIN_LEN = 0.15         # 短于 0.15s 的丢弃（多半是噪声）


def rms_envelope(y):
    n = 1 + (len(y) - FRAME) // HOP
    rms = np.zeros(n, np.float32)
    for i in range(n):
        seg = y[i * HOP:i * HOP + FRAME]
        rms[i] = np.sqrt(np.mean(seg.astype(np.float64) ** 2) + 1e-12)
    t = (np.arange(n) * HOP + FRAME / 2) / SR
    return t, rms


def detect_events(t, rms):
    ref = max(rms.max(), 1e-8)
    thr = ref * (10.0 ** (-DB_BELOW / 20.0))
    active = rms >= thr
    events = []
    i, n = 0, len(active)
    while i < n:
        if active[i]:
            j = i
            while j + 1 < n and active[j + 1]:
                j += 1
            events.append([t[i], t[j]])
            i = j + 1
        else:
            i += 1
    # 合并间隔小的
    merged = []
    for s, e in events:
        if merged and s - merged[-1][1] <= MERGE_GAP:
            merged[-1][1] = e
        else:
            merged.append([s, e])
    # 丢弃过短
    return [(s, e) for s, e in merged if e - s >= MIN_LEN]


def load_model_scores(positive, stem):
    """若有模型 predictions.csv，读其 (时间, 分数) 仅用于图上参考。"""
    p = os.path.join(positive, stem + "_predictions.csv")
    if not os.path.exists(p):
        return None
    import csv
    tt, ss = [], []
    with open(p, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            tt.append(float(r["end_sec"]))
            ss.append(float(r["score"]))
    return np.array(tt), np.array(ss)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--positive", required=True)
    ap.add_argument("--out", default="truth_draft")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    audio = [f for f in os.listdir(args.positive)
             if f.lower().endswith((".wav", ".mp3"))]
    audio.sort()
    draft_lines = ["audio,event_id,start_sec,end_sec"]
    total = 0
    for f in audio:
        stem = os.path.splitext(f)[0]
        y, _ = librosa.load(os.path.join(args.positive, f), sr=SR, mono=True)
        t, rms = rms_envelope(y)
        ev = detect_events(t, rms)
        total += len(ev)
        for k, (s, e) in enumerate(ev, 1):
            draft_lines.append("%s,%d,%.2f,%.2f" % (f, k, s, e))

        fig, ax = plt.subplots(figsize=(14, 3.6))
        db = 20 * np.log10(rms + 1e-8)
        ax.plot(t, db, lw=0.8, color="tab:blue", label="RMS energy (dB)")
        for k, (s, e) in enumerate(ev, 1):
            ax.axvspan(s, e, color="tab:green", alpha=0.25,
                       label="candidate truth" if k == 1 else None)
            ax.text((s + e) / 2, db.max() - 1, str(k), ha="center",
                    va="top", fontsize=8, color="tab:green")
        ref = load_model_scores(args.positive, stem)
        if ref is not None:
            tt, ss = ref
            ax.plot(tt, np.clip(ss, 1e-4, 1) * (db.max() - db.min()) + db.min(),
                    lw=0.7, ls="--", color="tab:gray",
                    label="model score (reference only)")
        ax.set_xlim(0, len(y) / SR)
        ax.set_xlabel("time (s)")
        ax.set_title(f + "  — green=proposed truth, verify by ear")
        ax.legend(loc="lower right", fontsize=8)
        fig.tight_layout()
        fig.savefig(os.path.join(args.out, stem + "_draft.png"), dpi=130)
        plt.close(fig)
        print("%-40s 候选事件 %d 个" % (f, len(ev)))

    draft_path = os.path.join(args.out, "events_truth_draft.csv")
    with open(draft_path, "w", encoding="utf-8") as f:
        f.write("\n".join(draft_lines) + "\n")
    print("\n共生成 %d 个候选事件。" % total)
    print("草稿: %s" % draft_path)
    print("请听录音核对后另存为 events_truth.csv，再运行 eval_recall.py")


if __name__ == "__main__":
    main()
