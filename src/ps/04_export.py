# -*- coding: utf-8 -*-
"""
04 导出模型（PC 上跑）
- 现在：导出 ONNX，方便在 PC 上用 postprocess.py 验证后处理逻辑；
- 以后上 PYNQ-Z2：把 tflite 那行打开，量化成 INT8 再搬上去。
用法:
    python 04_export.py
产物: runs/pitta/weights/best.onnx
"""
from ultralytics import YOLO

MODEL = "best.pt"


def main():
    model = YOLO(MODEL)

    # ① PC 端验证用：ONNX
    model.export(format="onnx", imgsz=320, simplify=True, opset=12)
    print("已导出 ONNX: best.onnx（和 best.pt 在同一目录）")

    # ② 以后上板前再打开这行（需要装 tensorflow）：
    # model.export(format="tflite", int8=True, imgsz=320, data="pitta.yaml")
    # print("已导出 INT8 TFLite，这个才是以后放到 PYNQ-Z2 上跑的模型")


if __name__ == "__main__":
    main()
