# -*- coding: utf-8 -*-
"""下载背景负样本（树林/落叶/灌木丛），放进 data/neg/ 作背景图降误报。"""
import os
import ssl
import urllib.request

URLS = [
    "https://aka.doubaocdn.com/s/tML7mbt5NV",
    "https://aka.doubaocdn.com/s/77YfjU20u6",
    "https://aka.doubaocdn.com/s/GyE0k0KwUy",
    "https://aka.doubaocdn.com/s/AbHVSwEpr5",
    "https://aka.doubaocdn.com/s/Nm6mxGJW9F",
    "https://aka.doubaocdn.com/s/jvPcsR8Ewa",
    "https://aka.doubaocdn.com/s/QNcenR09W4",
    "https://aka.doubaocdn.com/s/NrhgiDf7Uc",
    "https://aka.doubaocdn.com/s/cwYel3JysK",
    "https://aka.doubaocdn.com/s/Epypoz6J8W",
    "https://aka.doubaocdn.com/s/YWrSTRtH1v",
    "https://aka.doubaocdn.com/s/NukxHGIhlX",
    "https://aka.doubaocdn.com/s/rOr1ViEk6S",
    "https://aka.doubaocdn.com/s/Wd7tr0Wl5F",
    "https://aka.doubaocdn.com/s/ValkugIXXa",
    "https://aka.doubaocdn.com/s/JMxRBcZrnY",
    "https://aka.doubaocdn.com/s/UodLWdhp5d",
    "https://aka.doubaocdn.com/s/UokmNswmEM",
    "https://aka.doubaocdn.com/s/8mmaKwE5vc",
    "https://aka.doubaocdn.com/s/cAkkITzU8Z",
    "https://aka.doubaocdn.com/s/13K0TBuDiS",
    "https://aka.doubaocdn.com/s/8TF8Kdxlkh",
    "https://aka.doubaocdn.com/s/uISJN6gEnQ",
    "https://aka.doubaocdn.com/s/pRTesgp9Ja",
    "https://aka.doubaocdn.com/s/m8H5TkzCfX",
    "https://aka.doubaocdn.com/s/h89DYEE28g",
    "https://aka.doubaocdn.com/s/MefVwUKy2O",
    "https://aka.doubaocdn.com/s/Va6DfoUOjE",
    "https://aka.doubaocdn.com/s/GlJ6dv0PIm",
    "https://aka.doubaocdn.com/s/nL63F8Eo6j",
    "https://aka.doubaocdn.com/s/0wdazKVVHt",
    "https://aka.doubaocdn.com/s/hTTPvvVI7I",
    "https://aka.doubaocdn.com/s/1m7q8ufqiG",
    "https://aka.doubaocdn.com/s/b4SRx1gAu6",
    "https://aka.doubaocdn.com/s/rNK7QAs86A",
    "https://aka.doubaocdn.com/s/KWmqcW8DNs",
    "https://aka.doubaocdn.com/s/dVcvpZ5Xsp",
    "https://aka.doubaocdn.com/s/mgxaiiBGco",
    "https://aka.doubaocdn.com/s/QP9kGhaCFc",
    "https://aka.doubaocdn.com/s/fC7iEBhzVW",
    "https://aka.doubaocdn.com/s/6nVQ9qwD2p",
    "https://aka.doubaocdn.com/s/fwtLsfAjmM",
    "https://aka.doubaocdn.com/s/OyVa4UoOa8",
    "https://aka.doubaocdn.com/s/raBEulh1Po",
    "https://aka.doubaocdn.com/s/UqGCQNxszm",
    "https://aka.doubaocdn.com/s/ZMNFIxba4b",
    "https://aka.doubaocdn.com/s/6ODN6Vy2sr",
    "https://aka.doubaocdn.com/s/ZyFVYs6Uxv",
    "https://aka.doubaocdn.com/s/XgOYxkVbV3",
    "https://aka.doubaocdn.com/s/fmXfgOBJfK",
    "https://aka.doubaocdn.com/s/POBgapRnAi",
    "https://aka.doubaocdn.com/s/zQZrDPuSnf",
    "https://aka.doubaocdn.com/s/M3hs58VIu8",
    "https://aka.doubaocdn.com/s/Dx2oHfSaVv",
    "https://aka.doubaocdn.com/s/RHzztelEfl",
    "https://aka.doubaocdn.com/s/cTKqm8aMEB",
    "https://aka.doubaocdn.com/s/DTMUrE1iV4",
    "https://aka.doubaocdn.com/s/r2LEEkT6XX",
    "https://aka.doubaocdn.com/s/1Wk1fZotCm",
    "https://aka.doubaocdn.com/s/Vm2dHD736U",
]

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "neg")
CTX = ssl.create_default_context()


def main():
    os.makedirs(OUT, exist_ok=True)
    ok = 0
    for i, url in enumerate(URLS, 1):
        path = os.path.join(OUT, "neg_%03d.jpg" % i)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "pitta-vision/1.0"})
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                data = r.read()
            if len(data) < 2000:
                print("  [%02d] too small, skip" % i)
                continue
            with open(path, "wb") as f:
                f.write(data)
            ok += 1
            print("[%02d/%d] ok  %s" % (i, len(URLS), os.path.basename(path)))
        except Exception as e:  # noqa: BLE001
            print("  [%02d] fail: %s" % (i, e))
    print("完成：%d 张负样本在 %s" % (ok, OUT))


if __name__ == "__main__":
    main()
