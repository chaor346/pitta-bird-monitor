#!/bin/bash
# ============================================================
# 板上自检：在 PYNQ 终端运行  bash verify_gemm.sh
# 作用：不用跑 GEMM，立刻确认当前目录里的 bit/hwh
#       是不是 2026-10-25 最终版（含 TLAST 修复 + DMA 23bit）。
# 注意：本脚本需与 gemm_soc.bit/gemm_soc.hwh/gemm_board.py 在同一目录。
#       板端部署见 build/gemm/README.md。
# ============================================================
cd "$(dirname "$0")"
echo "================================================================"
echo " GEMM 板上文件自检（目录: $(pwd)）"
echo "================================================================"

EXP_BIT_1025="81714b8306646bbe102e41236a0a3054"   # 2026-10-25 板端跑出实测数据的那一版
EXP_BIT_1026="8240f2dc546fd9cb45e3e0adf65dc5c6"   # 2026-10-26 用 build_gemm.tcl 重建、随仓库提交的一版
EXP_HWH_1025="3b54a09cd5a5fb3fecfc17ae96796475"
EXP_HWH_1026="509b0336b112d0969d65c7757f621515"

# 注意：同一份工程重新综合一次，.bit 的 MD5 就会变（.bit 不是字节可复现产物），
# 所以这里接受"已知版本集合"而不是只认一个值；以后重建请把新 MD5 追加进来。
check() {
  local f="$1"; shift
  if [ ! -f "$f" ]; then
    echo "[缺失] $f 不存在！"
    return 1
  fi
  local got=$(md5sum "$f" | awk '{print $1}')
  local sz=$(stat -c%s "$f")
  local tag=""
  for pair in "$@"; do
    if [ "$got" = "${pair%%:*}" ]; then tag="${pair#*:}"; fi
  done
  if [ -n "$tag" ]; then
    echo "[  OK] $f  $got  ${sz}字节  已知版本：$tag"
  else
    echo "[未知] $f  $got  ${sz}字节（不是已知版本，请确认是否覆盖成功）"
    return 1
  fi
}

ok=1
check gemm_soc.bit "$EXP_BIT_1025:2026-10-25 板端实测版" "$EXP_BIT_1026:2026-10-26 仓库重建版" || ok=0
check gemm_soc.hwh "$EXP_HWH_1025:2026-10-25 板端实测版" "$EXP_HWH_1026:2026-10-26 仓库重建版" || ok=0

echo "----------------------------------------------------------------"
echo -n "hwh 长度位 C_SG_LENGTH_WIDTH: "
grep -o 'C_SG_LENGTH_WIDTH[^>]*VALUE="[0-9]*"' gemm_soc.hwh | grep -o 'VALUE="[0-9]*"' | sort -u | tr '\n' ' '
echo "（应为 23）"
echo -n "hwh 大小: "; stat -c%s gemm_soc.hwh
echo "（最终版应为 586046；旧版是 586492）"
echo "================================================================"

if [ "$ok" = "1" ]; then
  echo "结论：文件是已知版本，可用. 请【断电重启板子或重开终端】后运行："
  echo "   sudo python3 gemm_board.py --small"
  echo "   sudo python3 gemm_board.py"
  echo "注意：若上面显示「2026-10-26 仓库重建版」，说明这一版 bit 还没在本板跑过分值对拍，"
  echo "      引用 0.997878 / 6.7 ms 前请先跑一遍下面两条并留存输出："
  echo "   sudo python3 e2e_board.py"
  echo "   sudo python3 e2e_board.py --bench 20     # 公平加速比"
else
  echo "结论：板上不是已知版本！请用网页 Upload 或 scp 把下面 3 个文件覆盖到 $(pwd)："
  echo "   gemm_soc.bit  gemm_soc.hwh  gemm_board.py"
  echo "覆盖后重新运行  bash verify_gemm.sh，直到两行都显示 [OK]。"
fi
