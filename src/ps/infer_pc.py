# -*- coding: utf-8 -*-
"""
PC 端快速推理（直接用 ultralytics，最省事，用来验证训练效果）
用法:
    python infer_pc.py --source 测试图.jpg
    python infer_pc.py --source 0               # 本机摄像头
    python infer_pc.py --source 某文件夹/        # 整批跑
结果画框图存在 runtime/infer_out/，同时把框打印出来。
"""
import argparse
import os

import cv2
from ultralytics import YOLO

from config import CONF_THRES, IOU_THRES, IMG_SIZE, NAMES


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--weights", default="best.pt")
    ap.add_argument("--source", required=True, help="图片/文件夹路径；0 表示本机摄像头")
    args = ap.parse_args()

    model = YOLO(args.weights)
    src = 0 if args.source == "0" else args.source
    os.makedirs("runtime/infer_out", exist_ok=True)

    counter = 0
    results = model(source=src, conf=CONF_THRES, iou=IOU_THRES,
                    imgsz=IMG_SIZE, stream=True, verbose=False)
    is_cam = (src == 0)
    rec = None          # cv2.VideoWriter
    rec_until = 0       # 录制截止时间戳
    CLIP_SEC = 3        # 检测到鸟后再录几秒
    import time
    for r in results:
        counter += 1
        vis = r.plot()  # BGR，已画好框和标签
        now = time.time()
        bird = len(r.boxes) > 0
        if bird:
            rec_until = now + CLIP_SEC   # 持续检测就一直续
        if is_cam:
            cv2.imshow("pitta - press q to quit", vis)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
        for b in r.boxes:
            print("检测到 %s  conf=%.2f  box=%s" % (
                NAMES[int(b.cls)], float(b.conf),
                [round(float(v), 1) for v in b.xyxy[0]]))
        if bird:
            out_path = os.path.join("runtime/infer_out", "result_%04d.jpg" % counter)
            cv2.imwrite(out_path, vis)
            print("画框图已存: %s" % out_path)
        # 录制逻辑：刚检测到时开文件，超时关文件
        if is_cam:
            if rec is None and bird:
                h, w = vis.shape[:2]
                fourcc = cv2.VideoWriter_fourcc(*"mp4v")
                rec = cv2.VideoWriter("runtime/infer_out/clip_%d.mp4" % counter,
                                      fourcc, 20.0, (w, h))
                print("开始录视频...")
            if rec is not None:
                rec.write(vis)
                if now >= rec_until:
                    rec.release()
                    rec = None
                    print("视频已存: runtime/infer_out/clip_%d.mp4" % counter)
    if rec is not None:
        rec.release()
    if is_cam:
        cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
