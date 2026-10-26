# -*- coding: utf-8 -*-
from ultralytics import YOLO
import glob, os

os.chdir(os.path.dirname(os.path.abspath(__file__)))
files = sorted(glob.glob('data/images/val/*.jpg'))
m = YOLO('best.pt')
for idx in (75, 81):  # result_0076 / result_0082 对应 val 排序第 76 / 82 张
    p = files[idx]
    r = list(m(p, conf=0.2, verbose=False))[0]
    print(os.path.basename(p))
    if len(r.boxes) == 0:
        print('   0.2 阈值下仍无框')
    for b in r.boxes:
        print('   conf=%.3f  box=%s' % (float(b.conf), [round(float(v)) for v in b.xyxy[0]]))
