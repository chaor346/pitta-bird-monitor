# -*- coding: utf-8 -*-
"""
01 采集仙八色鸫图片（iNaturalist 公开科研级数据）
用法:
    python 01_collect_images.py --out data/raw_pitta --max 400

说明:
    - 按学名 Pitta nympha 搜索 research 级观察，下载其中的照片，自动去重分页。
    - 国内网络打不开 iNaturalist 时的备选：
        1) 到 Macaulay Library（https://macaulaylibrary.org，搜 Pitta nympha）手动批量下载；
        2) 到懂鸟 / 中国观鸟记录中心找仙八色鸫照片；
        3) 把手动下载的图直接扔进 --out 目录，脚本只负责补缺口。
    - 除了正样本（仙八色鸫），务必再攒等量的"负样本"：树叶、树枝、其他鸟、空景，
      存到 data/neg/ 目录（不标注，作为背景图一起训练，能大幅降误报）。
"""
import argparse
import hashlib
import os
import ssl
import time
import urllib.parse
import urllib.request

TAXON = "Pitta nympha"
API = "https://api.inaturalist.org/v1/observations"
HEADERS = {"User-Agent": "pitta-vision/1.0 (student competition project)"}
CTX = ssl.create_default_context()


def fetch_page(page: int, per_page: int = 200):
    """请求一页观察记录，返回观察列表。"""
    q = urllib.parse.urlencode({
        "taxon_name": TAXON,
        "photos": "true",
        "quality_grade": "research",
        "per_page": per_page,
        "page": page,
    })
    url = "%s?%s" % (API, q)
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        import json
        return json.loads(r.read().decode("utf-8"))


def download_image(url: str, save_path: str, retries: int = 2):
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
                data = r.read()
            with open(save_path, "wb") as f:
                f.write(data)
            return True
        except Exception as e:  # noqa: BLE001 - 网络错误跳过即可
            if attempt == retries:
                print("  [失败] %s (%s)" % (url, e))
                return False
            time.sleep(2)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/raw_pitta")
    ap.add_argument("--max", type=int, default=400, help="最多下载多少张图")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    seen = set()
    count = 0
    page = 1
    while count < args.max:
        try:
            data = fetch_page(page)
        except Exception as e:  # noqa: BLE001
            print("接口请求失败: %s" % e)
            print("如果是网络问题，请改用 README 里说的手动下载方案，把图放进 %s 后直接跳到标注步骤。" % args.out)
            break
        results = data.get("results", [])
        if not results:
            break
        for obs in results:
            for photo in obs.get("photos", []):
                url = photo.get("url", "")
                if not url:
                    continue
                # iNaturalist 给的是 square/medium，把结尾换成 original 拿大图
                url = url.replace("/square.", "/medium.")
                digest = hashlib.md5(url.encode()).hexdigest()
                if digest in seen:
                    continue
                seen.add(digest)
                ext = ".jpg"
                save_path = os.path.join(args.out, "pitta_%s%s" % (digest[:12], ext))
                if os.path.exists(save_path):
                    count += 1
                    continue
                if download_image(url, save_path):
                    count += 1
                    print("[%d/%d] %s" % (count, args.max, os.path.basename(save_path)))
                if count >= args.max:
                    break
            if count >= args.max:
                break
        page += 1
        time.sleep(1)  # 对 iNaturalist 友好一点

    print("完成：共 %d 张图在 %s" % (count, args.out))
    print("下一步：按 02_label_howto.md 做标注。")


if __name__ == "__main__":
    main()
