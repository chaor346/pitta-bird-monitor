# -*- coding: utf-8 -*-
"""
PYNQ-Z2 板端推理：TFLite + OpenCV，不依赖 ultralytics/onnxruntime。
用法：
    python3 infer_board.py --model best.tflite --image test.jpg
    python3 infer_board.py --model best.tflite --image test.jpg --conf 0.5
"""
import argparse
import os
import time

import cv2
import numpy as np
from tflite_runtime.interpreter import Interpreter

CLASS_NAME = "fairy_pitta"
IMG_SIZE = 320


def preprocess(img):
    """BGR -> RGB, resize 320x320, normalize 0~1, NHWC float32 (TFLite标准)."""
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    resized = cv2.resize(rgb, (IMG_SIZE, IMG_SIZE))
    arr = resized.astype(np.float32) / 255.0  # HWC
    return np.expand_dims(arr, axis=0)  # NHWC


def postprocess(output, orig_w, orig_h, conf_thres=0.52, iou_thres=0.45):
    """YOLOv8 输出 [1, 5, 2100] -> 框列表。"""
    output = output[0]  # [5, 2100]
    boxes = output[:4, :]   # cx, cy, w, h (320尺度)
    scores = output[4, :]   # 置信度

    # 过滤低置信
    mask = scores > conf_thres
    boxes = boxes[:, mask]
    scores = scores[mask]

    if len(scores) == 0:
        return []

    # cxcywh -> xyxy, 缩放到原图尺寸
    x1 = (boxes[0] - boxes[2] / 2) * orig_w / IMG_SIZE
    y1 = (boxes[1] - boxes[3] / 2) * orig_h / IMG_SIZE
    x2 = (boxes[0] + boxes[2] / 2) * orig_w / IMG_SIZE
    y2 = (boxes[1] + boxes[3] / 2) * orig_h / IMG_SIZE
    xyxy = np.stack([x1, y1, x2, y2], axis=1)

    # NMS
    indices = cv2.dnn.NMSBoxes(
        xyxy.tolist(), scores.tolist(), conf_thres, iou_thres)
    if len(indices) == 0:
        return []
    indices = indices.flatten()

    results = []
    for i in indices:
        results.append({
            "cls": CLASS_NAME,
            "conf": float(scores[i]),
            "box": [float(xyxy[i][0]), float(xyxy[i][1]),
                    float(xyxy[i][2]), float(xyxy[i][3])],
        })
    return results


def draw(img, results):
    for r in results:
        x1, y1, x2, y2 = [int(v) for v in r["box"]]
        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        label = "%s %.2f" % (r["cls"], r["conf"])
        cv2.putText(img, label, (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="best.tflite")
    ap.add_argument("--image", required=True)
    ap.add_argument("--conf", type=float, default=0.52)
    ap.add_argument("--output", default="result_board.jpg")
    args = ap.parse_args()

    # 读图（兼容中文路径）
    data = np.fromfile(args.image, dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        print("无法读取图片:", args.image)
        return
    orig_h, orig_w = img.shape[:2]

    # 加载模型
    interpreter = Interpreter(model_path=args.model)
    interpreter.allocate_tensors()
    input_details = interpreter.get_input_details()
    output_details = interpreter.get_output_details()

    # 推理
    x = preprocess(img)
    interpreter.set_tensor(input_details[0]["index"], x)
    t0 = time.time()
    interpreter.invoke()
    elapsed = time.time() - t0
    output = interpreter.get_tensor(output_details[0]["index"])

    # 后处理
    results = postprocess(output, orig_w, orig_h, args.conf)

    print("推理耗时: %.1f ms" % (elapsed * 1000))
    print("检测到 %d 个目标:" % len(results))
    for r in results:
        print("  %s  conf=%.2f  box=%s" % (r["cls"], r["conf"],
              [round(v, 1) for v in r["box"]]))

    # 画框保存
    vis = draw(img.copy(), results)
    ext = os.path.splitext(args.output)[1] or ".jpg"
    ok, buf = cv2.imencode(ext, vis)
    if ok:
        buf.tofile(args.output)
        print("结果图已存:", args.output)


if __name__ == "__main__":
    main()
