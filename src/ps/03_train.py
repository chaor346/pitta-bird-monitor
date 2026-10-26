# -*- coding: utf-8 -*-
"""
03 训练 YOLOv8n（PC 上跑，首次运行会自动下载预训练权重 yolov8n.pt）
用法:
    python 03_train.py
    python 03_train.py --epochs 150 --imgsz 320
训练产物: runs/pitta/weights/best.pt
"""
import argparse

from ultralytics import YOLO


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="pitta.yaml")
    ap.add_argument("--epochs", type=int, default=100)
    ap.add_argument("--imgsz", type=int, default=320)
    ap.add_argument("--batch", type=int, default=8)
    args = ap.parse_args()

    model = YOLO("yolov8n.pt")  # nano 版，最轻量，适合后面搬到 PYNQ-Z2
    model.train(
        data=args.data,
        epochs=args.epochs,
        imgsz=args.imgsz,
        batch=args.batch,
        project="runs",
        name="pitta",
        patience=20,          # 20 轮不提升就早停
        augment=True,
        # 图片少时建议开 mosaic/flip 等增强，ultralytics 默认已开
    )

    metrics = model.val()
    print("训练完成。mAP50 =", round(metrics.box.map50, 3))
    print("权重: runs/pitta/weights/best.pt")
    print("下一步: python infer_pc.py --source 某张测试图.jpg")


if __name__ == "__main__":
    main()
