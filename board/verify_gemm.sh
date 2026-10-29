#!/bin/bash
# GEMM overlay 文件自检。在板子上与 gemm_soc.bit/.hwh 同目录运行: bash verify_gemm.sh
# 只读 MD5/大小/C_SG_LENGTH_WIDTH，不加载硬件。

cd "$(dirname "$0")"
echo "GEMM 文件自检 ($(pwd))"
echo "------------------------"

EXP_BIT_1025="81714b8306646bbe102e41236a0a3054"
EXP_BIT_1026="8240f2dc546fd9cb45e3e0adf65dc5c6"
EXP_HWH_1025="3b54a09cd5a5fb3fecfc17ae96796475"
EXP_HWH_1026="509b0336b112d0969d65c7757f621515"

check() {
  local f="$1"; shift
  if [ ! -f "$f" ]; then echo "[缺失] $f"; return 1; fi
  local got=$(md5sum "$f" | awk '{print $1}')
  local sz=$(stat -c%s "$f")
  local tag=""
  for pair in "$@"; do
    if [ "$got" = "${pair%%:*}" ]; then tag="${pair#*:}"; fi
  done
  if [ -n "$tag" ]; then
    echo "[  OK] $f  ${sz}B  $tag"
  else
    echo "[未知] $f  $got  ${sz}B"
    return 1
  fi
}

ok=1
check gemm_soc.bit "$EXP_BIT_1025:板端实测版 1025" "$EXP_BIT_1026:仓库重建版 1026" || ok=0
check gemm_soc.hwh "$EXP_HWH_1025:板端实测版 1025" "$EXP_HWH_1026:仓库重建版 1026" || ok=0

echo -n "C_SG_LENGTH_WIDTH: "
grep -o 'C_SG_LENGTH_WIDTH[^>]*VALUE="[0-9]*"' gemm_soc.hwh | grep -o 'VALUE="[0-9]*"' | sort -u | tr '\n' ' '
echo "(应=23)"

if [ "$ok" = "1" ]; then
  echo "通过。跑: sudo python3 e2e_board.py --bench 20"
else
  echo "不通过。用 scp 覆盖 gemm_soc.bit / gemm_soc.hwh / gemm_board.py 后重跑本脚本。"
fi
