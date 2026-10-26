# -*- coding: utf-8 -*-
"""
01c 自动预标注：用 COCO 预训练的 YOLOv8n 检测"鸟"，把框写成 YOLO 格式标注。
跑之前需要: pip install ultralytics
跑完后: 用 LabelImg 打开 data/raw_pitta 逐张检查/修正框（比从零框快得多）。

输出: 每张图旁边一个同名 .txt，每行:  cls_id  cx  cy  w  h  (归一化到 0~1)
没检测到鸟的图不会生成 .txt —— 这些图之后训练时天然当背景。
"""
import glob
import os

import cv2
from ultralytics import YOLO

ROOT = os.path.dirname(os.path.abspath(__file__))
IMG_DIR = os.path.join(ROOT, "data", "raw_pitta")
COCO_BIRD_ID = 14   # YOLOv8 在 COCO 上只有 1 个"鸟"类，正好
CONF = 0.25


def main():
    model = YOLO("yolov8n.pt")  # 首次运行自动下载 ~6MB
    files = sorted(glob.glob(os.path.join(IMG_DIR, "*.jpg")))
    labeled = 0
    empty = 0
    multi = 0

    for i, img_path in enumerate(files, 1):
        res = model(img_path, conf=CONF, classes=[COCO_BIRD_ID],
                    imgsz=640, verbose=False)[0]
        h, w = res.orig_shape[:2]
        lines = []
        for b in res.boxes:
            x1, y1, x2, y2 = b.xyxy[0].tolist()
            cx = min(max((x1 + x2) / 2 / w, 0.0), 1.0)
            cy = min(max((y1 + y2) / 2 / h, 0.0), 1.0)
            bw = min(max((x2 - x1) / w, 0.0), 1.0)
            bh = min(max((y2 - y1) / h, 0.0), 1.0)
            lines.append("0 %.6f %.6f %.6f %.6f" % (cx, cy, bw, bh))
        if not lines:
            empty += 1
        else:
            if len(lines) > 1:
                multi += 1
            txt_path = os.path.splitext(img_path)[0] + ".txt"
            with open(txt_path, "w", encoding="utf-8") as f:
                f.write("\n".join(lines))
            labeled += 1
        if i % 100 == 0:
            print("进度 %d/%d  已标注 %d  未检到鸟 %d" % (i, len(files), labeled, empty))

    print("完成: 共 %d 张，其中 %d 张已自动标注，%d 张未检到鸟(当背景)，%d 张多框需人工确认"
          % (len(files), labeled, empty, multi))
    print("下一步: pip install labelImg && labelImg，打开 %s 逐张修正" % IMG_DIR)


if __name__ == "__main__":
    main()
