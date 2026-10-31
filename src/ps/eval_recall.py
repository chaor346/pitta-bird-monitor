#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
=====================================================================
 闊抽浜嬩欢绾у彫鍥炵巼璇勪及
=====================================================================
 杈撳叆锛?   1) 浜哄伐鐪熷€?events_truth.csv锛堢敱 label_audio_events.py 鑽夌鏍稿寰楀埌锛?        瀛楁锛歛udio,event_id,start_sec,end_sec
   2) 姣忔褰曢煶鐨?*_predictions.csv锛堥€愮獥妯″瀷鍒嗘暟锛屽凡瀛樺湪锛?        瀛楁锛歴tart_sec,end_sec,score,...

 杈撳嚭锛?   - 浜嬩欢绾у彫鍥烇細姣忎釜鐪熷€间簨浠讹紝鍙浜嬩欢鏈熼棿鏈変换鎰忕獥鍙?score鈮ラ槇鍊煎嵆绠楁鍑?   - 绐楀彛绾у彫鍥烇細鐪熷€煎尯闂村唴鐨勭獥鍙ｄ腑 score鈮ラ槇鍊肩殑姣斾緥锛堝弬鑰冿級
   - 鍦ㄤ袱涓槇鍊间笅鍒嗗埆鎶ュ憡锛?.5锛堣瘎浼板彛寰勶級銆?.985锛堟澘绔疄闄呴槇鍊硷級

 鐢ㄦ硶锛?   python eval_recall.py --positive <test_audio/positive> \
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
            print("  [璀﹀憡] 缂哄皯 predictions: %s" % audio)
            continue
        f_total, f_hit = len(events), 0
        for (s, e) in events:
            detected = any(overlap(s, e, ws, we) > 0 and sc >= threshold
                           for ws, we, sc in wins)
            f_hit += int(detected)
        # 绐楀彛绾э細绐楀彛涓績钀藉湪鐪熷€间簨浠跺唴
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
    for threshold in (0.5, 0.85):
        per, te, he, tw, hw = evaluate(truth, args.positive, threshold)
        er = 100.0 * he / te if te else 0.0
        wr = 100.0 * hw / tw if tw else 0.0
        print("\n===== 闃堝€?= %.3f =====" % threshold)
        print("浜嬩欢绾у彫鍥? %d/%d = %.1f%%" % (he, te, er))
        print("绐楀彛绾у彫鍥? %d/%d = %.1f%%锛堢湡鍊煎尯闂村唴绐楀彛锛? % (hw, tw, wr))
        for audio, ft, fh, wt, wh in per:
            print("  %-38s 浜嬩欢 %d/%d  绐楀彛 %d/%d"
                  % (audio, fh, ft, wh, wt))
            out_rows.append(dict(threshold=threshold, audio=audio,
                                 truth_events=ft, detected_events=fh,
                                 truth_windows=wt, detected_windows=wh,
                                 event_recall_pct=round(100.0 * fh / ft, 2) if ft else 0,
                                 window_recall_pct=round(100.0 * wh / wt, 2) if wt else 0))

    p = os.path.join(args.out, "recall_results.csv")
    if not out_rows:
        print("\n[绌虹粨鏋淽 鐪熷€?CSV 閲屾病鏈夊彲鐢ㄤ簨浠讹紙鎴栧搴斿綍闊崇己 *_predictions.csv锛夛紝涓嶅啓 CSV銆?)
        return
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(out_rows[0].keys()))
        w.writeheader()
        w.writerows(out_rows)
    print("\n鏄庣粏: %s" % p)


if __name__ == "__main__":
    main()
