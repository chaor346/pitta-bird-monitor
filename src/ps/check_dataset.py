# -*- coding: utf-8 -*-
"""数据集体检：检查 raw_pitta 里的图是不是合法 JPEG、有没有损坏/过小文件。"""
import glob
import os

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "raw_pitta")

bad = []
files = sorted(glob.glob(os.path.join(ROOT, "*.jpg")))
for f in files:
    size = os.path.getsize(f)
    if size < 2048:
        bad.append((os.path.basename(f), "too small: %d bytes" % size))
        continue
    with open(f, "rb") as fp:
        head = fp.read(3)
    if head != b"\xff\xd8\xff":  # JPEG 魔数
        bad.append((os.path.basename(f), "not jpeg magic"))

print("checked:", len(files))
if bad:
    print("bad files:")
    for name, why in bad:
        print("  ", name, why)
else:
    print("all files look like valid JPEGs.")
