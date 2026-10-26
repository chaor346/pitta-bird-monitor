# -*- coding: utf-8 -*-
"""抽查 4 张自动标注结果：把 .txt 里的框画到图上，存到 runtime/label_preview/ 供肉眼检查。"""
import glob
import os
import random

import cv2
import numpy as np

ROOT = os.path.dirname(os.path.abspath(__file__))


def imread_u(path):
    """支持中文路径的读图。"""
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def imwrite_u(path, img):
    ext = os.path.splitext(path)[1]
    cv2.imencode(ext, img)[1].tofile(path)
IMG_DIR = os.path.join(ROOT, "data", "raw_pitta")
OUT = os.path.join(ROOT, "runtime", "label_preview")


def main():
    os.makedirs(OUT, exist_ok=True)
    txts = sorted(glob.glob(os.path.join(IMG_DIR, "*.txt")))
    random.seed(7)
    samples = random.sample(txts, 4)
    for txt in samples:
        img_path = os.path.splitext(txt)[0] + ".jpg"
        img = imread_u(img_path)
        h, w = img.shape[:2]
        with open(txt, encoding="utf-8") as f:
            lines = [l.split() for l in f.read().strip().splitlines()]
        for parts in lines:
            cx, cy, bw, bh = map(float, parts[1:5])
            x1 = int((cx - bw / 2) * w)
            y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w)
            y2 = int((cy + bh / 2) * h)
            cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
        name = os.path.basename(img_path)
        out_path = os.path.join(OUT, "preview_" + name)
        imwrite_u(out_path, img)
        print("preview:", os.path.join(OUT, "preview_" + name), " boxes=", len(lines))


if __name__ == "__main__":
    main()
