#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 音频事件级召回率评估
=====================================================================
 输入：
   1) 人工真值 events_truth.csv（由 label_audio_events.py 草稿核对得到）
        字段：audio,event_id,start_sec,end_sec
   2) 每段录音的 *_predictions.csv（逐窗模型分数，已存在）
        字段：start_sec,end_sec,score,...

 输出：
   - 事件级召回：每个真值事件，只要事件期间有任意窗口 score≥阈值即算检出
   - 窗口级召回：真值区间内的窗口中 score≥阈值的比例（参考）
   - 在两个阈值下分别报告：0.5（评估口径）、0.985（板端实际阈值）

 用法：
   python eval_recall.py --positive <test_audio/positive> \
       --truth <events_truth.csv> --out recall_results
=====================================================================
"""
import os
import csv
import argparse
from collections import defaultdict


def read_truth(path):
    truth = defaultdict(list)
    with open(path, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            truth[r["audio"]].append(
                (float(r["start_sec"]), float(r["end_sec"])))
    return truth


def read_predictions(positive, audio):
    stem = os.path.splitext(audio)[0]
    p = os.path.join(positive, stem + "_predictions.csv")
    if not os.path.exists(p):
        return None
    wins = []
    with open(p, newline="", encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            wins.append((float(r["start_sec"]), float(r["end_sec"]),
                         float(r["score"])))
    return wins


def overlap(a0, a1, b0, b1):
    return max(0.0, min(a1, b1) - max(a0, b0))


def evaluate(truth, positive, threshold):
    total_ev, hit_ev = 0, 0
    total_win, hit_win = 0, 0
    per_file = []
    for audio, events in truth.items():
        wins = read_predictions(positive, audio)
        if wins is None:
            print("  [警告] 缺少 predictions: %s" % audio)
            continue
        f_total, f_hit = len(events), 0
        for (s, e) in events:
            detected = any(overlap(s, e, ws, we) > 0 and sc >= threshold
                           for ws, we, sc in wins)
            f_hit += int(detected)
        # 窗口级：窗口中心落在真值事件内
        w_total, w_hit = 0, 0
        for ws, we, sc in wins:
            c = (ws + we) / 2
            if any(s <= c <= e for s, e in events):
                w_total += 1
                w_hit += int(sc >= threshold)
        total_ev += f_total
        hit_ev += f_hit
        total_win += w_total
        hit_win += w_hit
        per_file.append((audio, f_total, f_hit, w_total, w_hit))
    return per_file, total_ev, hit_ev, total_win, hit_win


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--positive", required=True)
    ap.add_argument("--truth", required=True)
    ap.add_argument("--out", default="recall_results")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    truth = read_truth(args.truth)
    out_rows = []
    for threshold in (0.5, 0.985):
        per, te, he, tw, hw = evaluate(truth, args.positive, threshold)
        er = 100.0 * he / te if te else 0.0
        wr = 100.0 * hw / tw if tw else 0.0
        print("\n===== 阈值 = %.3f =====" % threshold)
        print("事件级召回: %d/%d = %.1f%%" % (he, te, er))
        print("窗口级召回: %d/%d = %.1f%%（真值区间内窗口）" % (hw, tw, wr))
        for audio, ft, fh, wt, wh in per:
            print("  %-38s 事件 %d/%d  窗口 %d/%d"
                  % (audio, fh, ft, wh, wt))
            out_rows.append(dict(threshold=threshold, audio=audio,
                                 truth_events=ft, detected_events=fh,
                                 truth_windows=wt, detected_windows=wh,
                                 event_recall_pct=round(100.0 * fh / ft, 2) if ft else 0,
                                 window_recall_pct=round(100.0 * wh / wt, 2) if wt else 0))

    p = os.path.join(args.out, "recall_results.csv")
    if not out_rows:
        print("\n[空结果] 真值 CSV 里没有可用事件（或对应录音缺 *_predictions.csv），不写 CSV。")
        return
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print("\n明细: %s" % p)


if __name__ == "__main__":
    main()
