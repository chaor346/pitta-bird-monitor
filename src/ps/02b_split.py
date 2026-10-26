# -*- coding: utf-8 -*-
"""
把标注好的 data/raw_pitta 按 8:2 划分为 YOLO 训练目录：
    data/images/train  data/images/val
    data/labels/train  data/labels/val
用法:
    python 02b_split.py --src data/raw_pitta --ratio 0.2
负样本目录 data/neg 里的图片（没有 .txt 标注文件）会自动全部进 train，作为背景图。
"""
import argparse
import glob
import os
import random
import shutil

IMG_EXT = (".jpg", ".jpeg", ".png", ".bmp")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default="data/raw_pitta", help="已标注的正样本目录（图片+同名.txt）")
    ap.add_argument("--neg", default="data/neg", help="负样本目录（纯图片，无标注）")
    ap.add_argument("--root", default="data", help="数据集根目录")
    ap.add_argument("--ratio", type=float, default=0.2, help="验证集比例")
    args = ap.parse_args()

    for sub in ("images/train", "images/val", "labels/train", "labels/val"):
        os.makedirs(os.path.join(args.root, sub), exist_ok=True)

    imgs = sorted(g for g in glob.glob(os.path.join(args.src, "*")) if g.lower().endswith(IMG_EXT))
    random.seed(42)
    random.shuffle(imgs)
    n_val = max(1, int(len(imgs) * args.ratio))
    splits = {"val": imgs[:n_val], "train": imgs[n_val:]}

    for split, files in splits.items():
        for img in files:
            stem = os.path.splitext(os.path.basename(img))[0]
            shutil.copy(img, os.path.join(args.root, "images", split, os.path.basename(img)))
            txt = os.path.join(args.src, stem + ".txt")
            if os.path.exists(txt):
                shutil.copy(txt, os.path.join(args.root, "labels", split, stem + ".txt"))

    # 负样本全部进 train，只拷图片，不拷标签（YOLO 把无标签图当纯背景）
    if os.path.isdir(args.neg):
        for img in glob.glob(os.path.join(args.neg, "*")):
            if img.lower().endswith(IMG_EXT):
                shutil.copy(img, os.path.join(args.root, "images/train", "neg_" + os.path.basename(img)))

    n_train = len(glob.glob(os.path.join(args.root, "images/train", "*")))
    n_val = len(glob.glob(os.path.join(args.root, "images/val", "*")))
    print("划分完成: train=%d  val=%d" % (n_train, n_val))
    print("下一步: python 03_train.py")


if __name__ == "__main__":
    main()
