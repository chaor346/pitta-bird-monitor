#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
生成音频事件真值核对页面（data/test_audio/positive/truth_draft/review_events.html）

输入（都已存在）：
  - truth_draft/events_truth_draft.csv          能量候选事件（待人工判定）
  - positive/<stem>_predictions.csv             逐窗 score / rms_dbfs（2 s 窗、0.5 s 跳）
  - ../manifest.csv                             每段时长

输出：
  - truth_draft/review_events.html              单文件、离线可开、无外部依赖
    页面里听音 → 判定保留/删除/补漏 → 导出 events_truth.csv

用法：
  python src/ps/build_truth_review.py
"""
import csv
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
POS = os.path.join(ROOT, "data", "test_audio", "positive")
DRAFT = os.path.join(POS, "truth_draft")
OUT = os.path.join(DRAFT, "review_events.html")


def read_csv(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def main():
    durations = {}
    manifest = os.path.join(ROOT, "data", "test_audio", "manifest.csv")
    if os.path.exists(manifest):
        for r in read_csv(manifest):
            name = os.path.basename(r["relative_path"])
            durations[name] = float(r["duration_sec"])

    draft = read_csv(os.path.join(DRAFT, "events_truth_draft.csv"))
    clips = []
    index = {}
    for r in draft:
        audio = r["audio"]
        if audio not in index:
            stem = os.path.splitext(audio)[0]
            pred = os.path.join(POS, stem + "_predictions.csv")
            wins = []
            if os.path.exists(pred):
                for w in read_csv(pred):
                    wins.append([float(w["start_sec"]),
                                 float(w["score"]),
                                 float(w["rms_dbfs"])])
            index[audio] = dict(file=audio, dur=durations.get(audio, 0.0),
                                wins=wins, events=[])
            clips.append(index[audio])
        index[audio]["events"].append(dict(s=float(r["start_sec"]),
                                           e=float(r["end_sec"]),
                                           st="keep"))

    if not clips:
        raise SystemExit("events_truth_draft.csv 里没有事件")

    for c in clips:
        if not c["dur"]:
            c["dur"] = max([w[0] for w in c["wins"]] + [e["e"] for e in c["events"]]) + 2.0
        c["events"].sort(key=lambda e: e["s"])
        # 保留一位小数即可，减小页面体积
        c["wins"] = [[round(t, 2), round(sc, 4), round(db, 1)] for t, sc, db in c["wins"]]

    payload = dict(version=sum(len(c["events"]) for c in clips) * 100 + len(clips),
                   clips=clips)
    data_js = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))

    with open(os.path.join(DRAFT, "review_template.html"), encoding="utf-8") as f:
        tpl = f.read()
    html = tpl.replace("__DATA__", data_js)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(html)

    total = sum(len(c["events"]) for c in clips)
    print("已生成: %s" % OUT)
    print("  录音 %d 段 / 候选事件 %d 个 / 总时长 %.1f s"
          % (len(clips), total, sum(c["dur"] for c in clips)))


if __name__ == "__main__":
    main()
