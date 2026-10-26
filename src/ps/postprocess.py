# -*- coding: utf-8 -*-
"""
YOLOv8 输出后处理（纯 numpy，无 PyTorch / ultralytics 依赖）。
这份代码将来原样搬到 PYNQ-Z2 上板——板子上 Python 3.6 装不了 ultralytics，
只能靠它解析模型输出。PC 上也可以先用它验证后处理逻辑对不对。

导出模型的原始输出形状: (1, 4+nc, num_anchors)
    前 4 列 : 框坐标 xywh，单位是【letterbox 后的输入图】像素
    后 nc 列: 类别分数

注意（2026-10-25 核验）：ultralytics 导出的 ONNX（本项目 best.onnx）
输出分数列**已经在图内做过 sigmoid**（实测范围 0–0.93），直接与阈值比较即可；
只有拿到"未 sigmoid 的 logits"输出时才需要本模块里的 `_sigmoid`。
本项目 ONNX 评测脚本 `eval_val_onnx.py` 采用"直接取分"的做法；板端 `infer_ncnn.cpp`
同样直接取分，二者一致。
"""
import numpy as np


def _sigmoid(x):
    return 1.0 / (1.0 + np.exp(-x))


def nms(boxes, scores, iou_thres):
    """boxes: (N,4) xyxy；返回保留下来的下标。"""
    x1, y1, x2, y2 = boxes[:, 0], boxes[:, 1], boxes[:, 2], boxes[:, 3]
    areas = (x2 - x1 + 1e-6) * (y2 - y1 + 1e-6)
    order = scores.argsort()[::-1]
    keep = []
    while order.size:
        i = int(order[0])
        keep.append(i)
        rest = order[1:]
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


def postprocess(raw_out, nc, conf_thres, iou_thres, in_size, orig_wh, pad):
    """
    raw_out : (1, 4+nc, N) 模型原始输出
    nc      : 类别数
    orig_wh : 原图 (宽, 高)
    pad     : letterbox 加的边距 (pad_w, pad_h)
    返回     : (M, 6) = [x1, y1, x2, y2, conf, cls_id]，坐标系已还原到原图
    """
    preds = raw_out[0].T                                   # (N, 4+nc)
    boxes_xywh = preds[:, :4]
    cls_scores = _sigmoid(preds[:, 4:])                    # (N, nc)
    cls_ids = cls_scores.argmax(axis=1)
    confs = cls_scores.max(axis=1)

    mask = confs >= conf_thres
    boxes_xywh = boxes_xywh[mask]
    confs = confs[mask]
    cls_ids = cls_ids[mask]
    if boxes_xywh.shape[0] == 0:
        return np.zeros((0, 6))

    # xywh(中心点+宽高) -> xyxy
    cx, cy, w, h = boxes_xywh[:, 0], boxes_xywh[:, 1], boxes_xywh[:, 2], boxes_xywh[:, 3]
    xyxy = np.stack([cx - w / 2, cy - h / 2, cx + w / 2, cy + h / 2], axis=1)

    # 反 letterbox：去掉 padding、按缩放比还原回原图坐标
    pad_w, pad_h = pad
    ow, oh = orig_wh
    scale = min(in_size / ow, in_size / oh)
    xyxy[:, [0, 2]] = (xyxy[:, [0, 2]] - pad_w) / scale
    xyxy[:, [1, 3]] = (xyxy[:, [1, 3]] - pad_h) / scale
    xyxy[:, [0, 2]] = np.clip(xyxy[:, [0, 2]], 0, ow)
    xyxy[:, [1, 3]] = np.clip(xyxy[:, [1, 3]], 0, oh)

    keep = nms(xyxy, confs, iou_thres)
    return np.concatenate(
        [xyxy[keep], confs[keep, None], cls_ids[keep, None]], axis=1
    )
