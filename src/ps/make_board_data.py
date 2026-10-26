#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import numpy as np

TB = r"D:/qiansai/gemm_acc/tb"
OUT = r"D:/qiansai/gemm_vivado/board"
os.makedirs(OUT, exist_ok=True)

K, N = 9, 16


def conv(tag, M):
    A = np.loadtxt(os.path.join(TB, f"A{tag}.txt"), dtype=np.int64)
    B = np.loadtxt(os.path.join(TB, f"B{tag}.txt"), dtype=np.int64)
    C = np.loadtxt(os.path.join(TB, f"C_ref{tag}.txt"), dtype=np.float64)
    assert A.size == M * K, (A.size, M * K)
    assert B.size == K * N, (B.size, K * N)
    assert C.size == M * N, (C.size, M * N)
    assert A.min() >= -32768 and A.max() <= 32767, "A 超出 int16"
    assert B.min() >= -32768 and B.max() <= 32767, "B 超出 int16"
    A.astype("<i2").tofile(os.path.join(OUT, f"a{tag}.bin"))
    B.astype("<i2").tofile(os.path.join(OUT, f"b{tag}.bin"))
    C.astype("<f4").tofile(os.path.join(OUT, f"c_ref{tag}.bin"))
    print(f"{tag if tag else 'full'}: M={M:6d}  A={A.size:7d} B={B.size:4d} C={C.size:7d}  "
          f"A范围[{A.min()},{A.max()}]  B范围[{B.min()},{B.max()}]")


conv("", 12864)      # 全量
conv("_small", 32)   # 小数据快速验证
print("板端数据已生成到", OUT)
