# -*- coding: utf-8 -*-
"""在独立验证集上评测图像检测模型（ONNX，CPU，纯 numpy 后处理）。

数据口径：
- 图像来源：`data/images/val`（划分训练/验证时留出的 260 张，未参与权重更新）
- 真值：`data/labels/val/*.txt`（YOLO 格式，类别 0 = 仙八色鸫）
- 有标注的图按"至少 1 个 GT 框"计入召回/mAP；无标注文件的图单独统计，不计入召回

注意：导出的 ONNX 输出 (1, 4+nc, N) 已经在图内做过 sigmoid，
分数列直接就是 0–1 的概率，不要再套一次 sigmoid（`postprocess.py` 里套了会有偏差）。

用法：
    python eval_val_onnx.py --onnx "D:/嵌赛/Bird image recognition/best.onnx" \
        --images "D:/嵌赛/Bird image recognition/data/images/val" \
        --labels "D:/嵌赛/Bird image recognition/data/labels/val" \
        --out "D:/嵌赛/pitta_bird_monitor/data/test_images/eval_val"
"""
import argparse
import csv
import glob
import json
import os

import cv2
import numpy as np
import onnxruntime as ort

IMGSZ = 320
PAD_VALUE = 114


def letterbox(img, size=IMGSZ):
    """等比缩放 + 居中填充，返回 (canvas, pad_w, pad_h, scale)。"""
    h, w = img.shape[:2]
    scale = min(size / float(w), size / float(h))
    nw, nh = int(round(w * scale)), int(round(h * scale))
    canvas = np.full((size, size, 3), PAD_VALUE, dtype=np.uint8)
    pad_w, pad_h = (size - nw) // 2, (size - nh) // 2
    canvas[pad_h:pad_h + nh, pad_w:pad_w + nw] = cv2.resize(img, (nw, nh))
    return canvas, pad_w, pad_h, scale


def nms(boxes, scores, iou_thres=0.45):
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1 + 1e-6) * (y2 - y1 + 1e-6)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
        if rest.size == 0:
            break
        xx1 = np.maximum(x1[i], x1[rest])
        yy1 = np.maximum(y1[i], y1[rest])
        xx2 = np.minimum(x2[i], x2[rest])
        yy2 = np.minimum(y2[i], y2[rest])
        w = np.clip(xx2 - xx1, 0, None)
        h = np.clip(yy2 - yy1, 0, None)
        inter = w * h
        iou = inter / (areas[i] + areas[rest] - inter + 1e-6)
        order = rest[iou <= iou_thres]
    return np.array(keep, dtype=int)


def decode(out, orig_wh, pad_w, pad_h, scale, conf, iou):
    """out: (1, 4+nc, N)；先验已在图内 sigmoid，坐标是 letterbox 输入像素。"""
    preds = out[0].T
    boxes = preds[:, :4]
    scores = preds[:, 4:].max(axis=1)
    mask = scores >= conf
    if not mask.any():
        return np.zeros((0, 5), dtype=np.float32)
    boxes, scores = boxes[mask], scores[mask]
    xyxy = np.stack([boxes[:, 0] - boxes[:, 2] / 2, boxes[:, 1] - boxes[:, 3] / 2,
                     boxes[:, 0] + boxes[:, 2] / 2, boxes[:, 1] + boxes[:, 3] / 2], axis=1)
    ow, oh = orig_wh
    xyxy[:, [0, 2]] = np.clip((xyxy[:, [0, 2]] - pad_w) / scale, 0, ow)
    xyxy[:, [1, 3]] = np.clip((xyxy[:, [1, 3]] - pad_h) / scale, 0, oh)
    keep = nms(xyxy, scores, iou)
    return np.concatenate([xyxy[keep], scores[keep, None]], axis=1)


def iou_one(box, gt):
    x1 = max(box[0], gt[0]); y1 = max(box[1], gt[1])
    x2 = min(box[2], gt[2]); y2 = min(box[3], gt[3])
    iw = max(0.0, x2 - x1); ih = max(0.0, y2 - y1)
    inter = iw * ih
    a = (box[2] - box[0]) * (box[3] - box[1])
    b = (gt[2] - gt[0]) * (gt[3] - gt[1])
    return inter / (a + b - inter + 1e-9)


def load_gt(label_path, w, h):
    gts = []
    if not os.path.exists(label_path):
        return gts
    with open(label_path, encoding="utf-8", errors="ignore") as f:
        for line in f:
            t = line.split()
            if len(t) < 5:
                continue
            cx, cy, bw, bh = [float(x) for x in t[1:5]]
            gts.append([(cx - bw / 2) * w, (cy - bh / 2) * h,
                        (cx + bw / 2) * w, (cy + bh / 2) * h])
    return gts


def run_one(sess, iname, path, args):
    """单图推理，返回 (dets, w, h)。"""
    img = cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return np.zeros((0, 5), dtype=np.float32), 0, 0
    h, w = img.shape[:2]
    canvas, pw, ph, sc = letterbox(img, args.imgsz)
    x = canvas[:, :, ::-1].transpose(2, 0, 1)[None].astype(np.float32) / 255.0
    out = sess.run(None, {iname: x})[0]
    return decode(out, (w, h), pw, ph, sc, args.conf, args.iou), w, h


def average_precision(tps, total_gt):
    """tps 按置信度降序的 0/1 序列 → AP（全点插值）。"""
    if total_gt == 0 or len(tps) == 0:
        return 0.0
    tp = np.cumsum(tps)
    fp = np.cumsum(1 - tps)
    rec = tp / total_gt
    prec = tp / np.maximum(tp + fp, 1e-9)
    mrec = np.concatenate([[0.0], rec, [1.0]])
    mpre = np.concatenate([[1.0], prec, [0.0]])
    for i in range(len(mpre) - 2, -1, -1):
        mpre[i] = max(mpre[i], mpre[i + 1])
    idx = np.where(mrec[1:] != mrec[:-1])[0]
    return float(np.sum((mrec[idx + 1] - mrec[idx]) * mpre[idx + 1]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--onnx", required=True)
    ap.add_argument("--images", required=True)
    ap.add_argument("--labels", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--conf", type=float, default=0.52)
    ap.add_argument("--iou", type=float, default=0.45)
    ap.add_argument("--imgsz", type=int, default=IMGSZ)
    ap.add_argument("--seen-positive", default="", help="训练池里出现过的正样本目录（对照用）")
    ap.add_argument("--seen-negative", default="", help="训练池里出现过的负样本目录（对照用）")
    args = ap.parse_args()

    sess = ort.InferenceSession(args.onnx, providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name

    paths = [p for p in glob.glob(os.path.join(args.images, "*.*"))
             if p.lower().endswith((".jpg", ".jpeg", ".png"))]
    paths.sort()
    rows = []
    dets_for_map = []   # (score, img_idx, box)
    gts_by_img = {}

    for idx, p in enumerate(paths):
        stem = os.path.splitext(os.path.basename(p))[0]
        dets, w, h = run_one(sess, iname, p, args)
        if w == 0:
            continue

        lab = os.path.join(args.labels, stem + ".txt")
        gts = load_gt(lab, w, h)
        has_label = os.path.exists(lab)
        gts_by_img[idx] = gts
        for d in dets:
            dets_for_map.append((float(d[4]), idx, d[:4].tolist()))

        rows.append({
            "image": os.path.basename(p),
            "width": w, "height": h,
            "has_label_file": int(has_label),
            "gt_boxes": len(gts),
            "detections": len(dets),
            "max_score": round(float(dets[:, 4].max()), 4) if len(dets) else 0.0,
            "detected": int(len(dets) > 0),
        })

    # mAP@0.5（单类，仅在有 GT 的图上算）
    dets_for_map.sort(key=lambda t: -t[0])
    matched = {i: np.zeros(len(g), dtype=bool) for i, g in gts_by_img.items() if g}
    tps = []
    for score, idx, box in dets_for_map:
        g = gts_by_img.get(idx) or []
        best_iou, best_j = 0.0, -1
        for j, gt in enumerate(g):
            if matched[idx][j]:
                continue
            v = iou_one(box, gt)
            if v > best_iou:
                best_iou, best_j = v, j
        if best_j >= 0 and best_iou >= 0.5:
            matched[idx][best_j] = True
            tps.append(1)
        else:
            tps.append(0)
    total_gt = sum(len(g) for g in gts_by_img.values())
    mAP = average_precision(np.array(tps), total_gt)

    labeled = [r for r in rows if r["gt_boxes"] > 0]
    hit = [r for r in labeled if r["detected"]]
    unlabeled = [r for r in rows if r["gt_boxes"] == 0]
    unlabeled_hit = [r for r in unlabeled if r["detected"]]

    summary = {
        "model": os.path.basename(args.onnx),
        "conf": args.conf, "iou": args.iou, "imgsz": args.imgsz,
        "images_total": len(rows),
        "images_with_gt": len(labeled),
        "gt_boxes": total_gt,
        "detected_images": len(hit),
        "image_level_recall": round(len(hit) / len(labeled), 4) if labeled else 0.0,
        "detections_total": len(dets_for_map),
        "mAP50": round(mAP, 4),
        "images_without_gt": len(unlabeled),
        "images_without_gt_detected": len(unlabeled_hit),
        "images_without_gt_note": "这些图没有标注文件、但目视含鸟，不能当负样本，故不计入误报率",
    }

    # 对照：训练池里出现过的演示图（知其标签），用于展示"见过 vs 没见过"的差距
    if args.seen_positive:
        files = [p for p in glob.glob(os.path.join(args.seen_positive, "**", "*.*"), recursive=True)
                 if p.lower().endswith((".jpg", ".jpeg", ".png"))]
        hit_n = 0
        for p in files:
            d, _, _ = run_one(sess, iname, p, args)
            if len(d) > 0:
                hit_n += 1
        summary["seen_positive_images"] = len(files)
        summary["seen_positive_detected"] = hit_n
        summary["seen_positive_rate"] = round(hit_n / len(files), 4) if files else None

    if args.seen_negative:
        files = [p for p in glob.glob(os.path.join(args.seen_negative, "**", "*.*"), recursive=True)
                 if p.lower().endswith((".jpg", ".jpeg", ".png"))]
        fp_n = 0
        for p in files:
            d, _, _ = run_one(sess, iname, p, args)
            if len(d) > 0:
                fp_n += 1
        summary["seen_negative_images"] = len(files)
        summary["seen_negative_detected"] = fp_n
        summary["seen_negative_fp_rate"] = round(fp_n / len(files), 4) if files else None

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "metrics.json"), "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    with open(os.path.join(args.out, "per_image.csv"), "w", encoding="utf-8", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        wr.writeheader()
        wr.writerows(rows)
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
