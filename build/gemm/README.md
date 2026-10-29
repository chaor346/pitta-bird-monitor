# GEMM 加速器构建产物

conv1 硬件化后的 bit/hwh、报告和说明。板端脚本在 `src/ps/`，测试数据在 `data/gemm/`。

## 文件

| 文件 | 说明 |
|---|---|
| `gemm_soc.bit` / `.hwh` | GEMM overlay 比特流（M=12864 K=9 N=16，三路 DMA，C_SG_LENGTH_WIDTH=23） |
| `gemm_utilization.rpt` | routed 资源占用 |
| `gemm_timing.rpt` | 时序摘要 |
| `gemm_power.rpt` | 功耗 |
| `build_gemm.tcl`（上级目录） | 一键重建本工程 |

## 板端部署

```bash
scp gemm_soc.bit gemm_soc.hwh xilinx@<board>:/home/xilinx/gemm/
scp ../../src/ps/e2e_board.py ../../src/ps/gemm_board.py xilinx@<board>:/home/xilinx/gemm/
scp ../../data/gemm/* xilinx@<board>:/home/xilinx/gemm/
scp ../../board/verify_gemm.sh xilinx@<board>:/home/xilinx/gemm/
```

板端：
```bash
cd /home/xilinx/gemm
bash verify_gemm.sh
sudo python3 e2e_board.py
sudo python3 e2e_board.py --bench 20   # 公平加速比，待跑
```

## 已实测（2026-10-26，`--bench 20` 中位数）

```
numpy 全浮点  分数 = 0.997876
硬件 conv1    分数 = 0.997878
conv1 最大误差 = 0.001838（容差 0.02，0/205824 点超差）

公平加速比（--bench 20）：
  硬件端到端（DMA搬运+GEMM+反量化）= 52.7 ms
  纯核 ap_start→ap_done           = 6.7 ms
  numpy conv1 单独                = 31.0 ms
  端到端加速比 = 0.59x（搬运开销吃掉收益）
  纯核加速比   = 4.64x
```

> 结论：conv1 计算量太小（numpy 31ms），DMA 搬运 A/B/C 开销占端到端 87%，
> 故正式音频主程序仍走 numpy，GEMM overlay 仅作硬件加速能力验证。

## 设计要点

- 三路 AXI-DMA：A/B 为 MM2S（PS→PL），C 为 S2MM（PL→PS）
- 数据 Q12，bias + ReLU 烘焙进 HLS 核，PS 只送 A/B
- 寄存器轮询，`ap_done` 为完成判据
- `C_SG_LENGTH_WIDTH=23`，单次 DMA 可传 8 MB

## 资源/时序/功耗（2026-10-26 routed）

| 资源 | 占用 | 利用率 |
|---|---|---|
| Slice LUTs | 5376/53200 | 10.11% |
| Slice Registers | 7505/106400 | 7.05% |
| Block RAM | 11/140 | 7.86% |
| DSP48 | 67/220 | 30.45% |

- 时序：100 MHz，WNS +1.520 ns，0 失败端点
- 功耗：1.741 W（动态 1.602 + 静态 0.139）

## 相关踩坑

见 `../../skill/pitfalls/pynq_pitfalls.md` D 类（TLAST 缺失 / DMA 16 KB 上限 / 中断接线 / FCLK / bit-hwh 版本 / ap_done 判据）。
