# -*- coding: utf-8 -*-
"""
考一考模型：拿训练时没见过的鸟，看它会不会误认成仙八色鸫。
做法：下载 30 张红耳鹎（训练集里没有这个种），跑推理，数有多少张被框。
被框的比例 = 误报率，越低越好。
"""
import os, ssl, time, json, hashlib, urllib.parse, urllib.request
os.chdir(os.path.dirname(os.path.abspath(__file__)))

TAXON = "Pycnonotus jocosus"   # 红耳鹎：训练集没出现过
OUT = "runtime/other_bird_test"
os.makedirs(OUT, exist_ok=True)
HEADERS = {"User-Agent": "pitta-vision/1.0 (student competition project)"}
CTX = ssl.create_default_context()

# 下载 30 张
count = 0
for page in (1, 2):
    q = urllib.parse.urlencode({"taxon_name": TAXON, "photos": "true",
                               "quality_grade": "research", "per_page": 100, "page": page})
    req = urllib.request.Request("https://api.inaturalist.org/v1/observations?" + q, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        data = json.loads(r.read().decode("utf-8"))
    for obs in data.get("results", []):
        for photo in obs.get("photos", []):
            url = photo.get("url", "").replace("/square.", "/medium.")
            if not url: continue
            digest = hashlib.md5(url.encode()).hexdigest()[:12]
            path = os.path.join(OUT, "test_%s.jpg" % digest)
            if os.path.exists(path): continue
            try:
                req = urllib.request.Request(url, headers=HEADERS)
                with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                    open(path, "wb").write(r.read())
                count += 1
                print("download", count)
            except Exception:
                pass
            if count >= 30: break
        if count >= 30: break
    if count >= 30: break
    time.sleep(1)
print("共下载", count, "张")

# 跑推理
from ultralytics import YOLO
m = YOLO("best.pt")
import glob
imgs = sorted(glob.glob(OUT + "/*.jpg"))
fp = 0
for p in imgs:
    r = list(m(p, conf=0.52, verbose=False))[0]
    if len(r.boxes) > 0:
        fp += 1
        print("误报:", os.path.basename(p), " confs:", [round(float(b.conf),2) for b in r.boxes])
print("=" * 40)
print("别的鸟误报率: %d / %d = %.1f%%" % (fp, len(imgs), 100*fp/max(1,len(imgs))))
