# -*- coding: utf-8 -*-
"""
01e 采集"别的鸟"作为难负样本（防止把别的鸟误认成仙八色鸫）
用法:
    python 01e_collect_other_birds.py --out data/neg --max 100

下的是中国林地常见鸟：白头鹎、麻雀、鹊鸲、乌鸫、绣眼。
这些图不画框，直接当背景图训练，模型就学会"鸟不一定是仙八色鸫"。
"""
import argparse
import hashlib
import os
import ssl
import time
import urllib.parse
import urllib.request

# 中国南方林地常见、体型/生境和仙八色鸫有重叠的鸟
OTHER_BIRDS = [
    "Pycnonotus sinensis",   # 白头鹎
    "Passer montanus",       # 麻雀
    "Copsychus saularis",    # 鹊鸲
    "Turdus mandarinus",     # 乌鸫
    "Zosterops simplex",     # 绣眼
    "Pycnonotus jocosus",    # 红耳鹎
    "Parus cinereus",        # 大山雀
    "Pomatorhinus erythrocnemis",  # 棕颈钩嘴鹛
    "Phoenicurus auroreus",  # 北红尾鸲
    "Eophona migratoria",    # 黑尾蜡嘴雀
]
API = "https://api.inaturalist.org/v1/observations"
HEADERS = {"User-Agent": "pitta-vision/1.0 (student competition project)"}
CTX = ssl.create_default_context()


def fetch_page(taxon: str, page: int, per_page: int = 100):
    q = urllib.parse.urlencode({
        "taxon_name": taxon,
        "photos": "true",
        "quality_grade": "research",
        "per_page": per_page,
        "page": page,
    })
    req = urllib.request.Request("%s?%s" % (API, q), headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
        import json
        return json.loads(r.read().decode("utf-8"))


def download_image(url: str, save_path: str):
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=30, context=CTX) as r:
            data = r.read()
        with open(save_path, "wb") as f:
            f.write(data)
        return True
    except Exception as e:  # noqa: BLE001
        print("  [失败] %s" % e)
        return False


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="data/neg")
    ap.add_argument("--max", type=int, default=100)
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    per_species = args.max // len(OTHER_BIRDS)
    count = 0
    for taxon in OTHER_BIRDS:
        got = 0
        page = 1
        while got < per_species:
            try:
                data = fetch_page(taxon, page)
            except Exception as e:  # noqa: BLE001
                print("接口失败 %s: %s" % (taxon, e))
                break
            results = data.get("results", [])
            if not results:
                break
            for obs in results:
                for photo in obs.get("photos", []):
                    url = photo.get("url", "").replace("/square.", "/medium.")
                    if not url:
                        continue
                    digest = hashlib.md5(url.encode()).hexdigest()[:12]
                    save_path = os.path.join(args.out, "negbird_%s.jpg" % digest)
                    if os.path.exists(save_path):
                        got += 1
                        continue
                    if download_image(url, save_path):
                        got += 1
                        count += 1
                        print("[%d] %s -> %s" % (count, taxon, os.path.basename(save_path)))
                    if got >= per_species or count >= args.max:
                        break
                if got >= per_species or count >= args.max:
                    break
            page += 1
            time.sleep(1)
        print("== %s 完成 %d 张" % (taxon, got))

    print("完成：共 %d 张别的鸟在 %s" % (count, args.out))


if __name__ == "__main__":
    main()
