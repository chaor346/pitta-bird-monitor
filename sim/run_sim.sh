#!/bin/bash
# ============================================================
# 一键编译 + 运行 I2S 接收核仿真
# 用法: bash run_sim.sh
# 前置: Vivado 工具链在 PATH (xvlog/xelab/xsim)
# ============================================================
set -e
cd "$(dirname "$0")"

echo "=== [1/3] 编译 RTL + testbench ==="
xvlog ../src/fpga/i2s_mems_rx.v i2s_mems_rx_tb.v

echo "=== [2/3] 建立仿真快照 ==="
xelab -debug typical i2s_mems_rx_tb -s simsnap

echo "=== [3/3] 运行 ==="
xsim simsnap -runall
