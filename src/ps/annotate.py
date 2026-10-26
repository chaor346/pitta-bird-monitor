# -*- coding: utf-8 -*-
"""
迷你 YOLO 标注器（纯 OpenCV，不依赖 PyQt/labelImg，绝不闪退）

用法:
    D:\\python\\python.exe annotate.py "要标注的图片文件夹" "标签输出文件夹"

操作:
    鼠标左键拖框    —— 画一个 fairy_pitta 框
    多个框          —— 一张图可以画多个
    u               —— 撤销最后一个框
    s / 空格        —— 保存 + 下一张
    d               —— 不保存直接下一张（这张图就当作"没鸟"的背景）
    q / Esc         —— 退出

标签直接存成 YOLO 格式 .txt，和数据集里现有标签同格式。
"""
import os
import sys
import glob
import cv2
import numpy as np

CLASS_NAME = "fairy_pitta"
CLASS_ID = 0
WIN = "annotate"

drawing = False
ix, iy = -1, -1
boxes = []          # 当前图上的框 [(x1,y1,x2,y2), ...]
img_display = None
img_raw = None


def imread_u(path):
    return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)


def draw():
    global img_display
    img_display = img_raw.copy()
    for (x1, y1, x2, y2) in boxes:
        cv2.rectangle(img_display, (x1, y1), (x2, y2), (255, 0, 0), 2)
        cv2.putText(img_display, CLASS_NAME, (x1, max(0, y1 - 6)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 0), 2)
    cv2.imshow(WIN, img_display)


def on_mouse(event, x, y, flags, param):
    global drawing, ix, iy
    if event == cv2.EVENT_LBUTTONDOWN:
        drawing = True
        ix, iy = x, y
    elif event == cv2.EVENT_MOUSEMOVE and drawing:
        tmp = img_raw.copy()
        cv2.rectangle(tmp, (ix, iy), (x, y), (0, 255, 0), 2)
        cv2.imshow(WIN, tmp)
    elif event == cv2.EVENT_LBUTTONUP:
        drawing = False
        x1, y1 = min(ix, x), min(iy, y)
        x2, y2 = max(ix, x), max(iy, y)
        if x2 - x1 > 5 and y2 - y1 > 5:
            boxes.append((x1, y1, x2, y2))
        draw()


def save_txt(out_dir, stem, w, h):
    txt_path = os.path.join(out_dir, stem + ".txt")
    with open(txt_path, "w", encoding="utf-8") as f:
        for (x1, y1, x2, y2) in boxes:
            cx = ((x1 + x2) / 2) / w
            cy = ((y1 + y2) / 2) / h
            bw = (x2 - x1) / w
            bh = (y2 - y1) / h
            f.write("%d %.6f %.6f %.6f %.6f\n" % (CLASS_ID, cx, cy, bw, bh))


def load_existing(out_dir, stem, w, h):
    """启动时读已有 YOLO 标签，转成像素框作为初始框（支持核对/微调）。"""
    txt = os.path.join(out_dir, stem + ".txt")
    boxes = []
    if not os.path.exists(txt):
        return boxes
    with open(txt, encoding="utf-8", errors="ignore") as f:
        for line in f:
            t = line.split()
            if len(t) < 5:
                continue
            try:
                cx, cy, bw, bh = [float(x) for x in t[1:5]]
            except ValueError:
                continue
            x1 = int((cx - bw / 2) * w); y1 = int((cy - bh / 2) * h)
            x2 = int((cx + bw / 2) * w); y2 = int((cy + bh / 2) * h)
            boxes.append((x1, y1, x2, y2))
    return boxes


def main():
    img_dir = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)
    files = sorted(glob.glob(os.path.join(img_dir, "*.jpg")) +
                   glob.glob(os.path.join(img_dir, "*.jpeg")) +
                   glob.glob(os.path.join(img_dir, "*.png")))
    print("共 %d 张" % len(files))
    cv2.namedWindow(WIN, cv2.WINDOW_NORMAL)
    cv2.setMouseCallback(WIN, on_mouse)

    i = 0
    while i < len(files):
        path = files[i]
        stem = os.path.splitext(os.path.basename(path))[0]
        global img_raw, boxes
        img_raw = imread_u(path)
        if img_raw is None:
            i += 1
            continue
        boxes = load_existing(out_dir, stem, img_raw.shape[1], img_raw.shape[0])
        h, w = img_raw.shape[:2]
        print("[%d/%d] %s  (已加载 %d 个框)" % (i + 1, len(files), os.path.basename(path), len(boxes)))
        draw()
        while True:
            key = cv2.waitKey(0) & 0xFF
            if key in (ord('s'), ord(' ')):
                save_txt(out_dir, stem, w, h)
                print("  已保存 %d 个框 -> %s.txt" % (len(boxes), stem))
                i += 1
                break
            elif key == ord('d'):
                i += 1
                break
            elif key == ord('u') and boxes:
                boxes.pop()
                draw()
            elif key in (ord('q'), 27):
                cv2.destroyAllWindows()
                return
    cv2.destroyAllWindows()
    print("全部标完！")


if __name__ == "__main__":
    main()
