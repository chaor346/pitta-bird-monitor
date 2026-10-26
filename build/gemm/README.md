# GEMM 加速器构建产物（conv1 硬件化）

conv1 从 PS numpy 搬到 PL HLS GEMM 核后的构建产物。本目录放 bit/hwh、综合实现报告
（utilization/timing/power）和本说明；板端脚本在 `src/ps/`，测试数据在 `data/gemm/`，
板端自检脚本在 `board/verify_gemm.sh`。

## 仓库布局（按竞赛 3.3.5.4 规范）

| 仓库路径 | 内容 |
|---|---|
| `build/gemm/gemm_soc.bit` / `.hwh` | GEMM overlay 比特流与硬件描述（M=12864 K=9 N=16，三路 DMA，C_SG_LENGTH_WIDTH=23） |
| `build/gemm/gemm_utilization.rpt` | GEMM overlay routed 资源占用（LUT/FF/BRAM/DSP） |
| `build/gemm/gemm_timing.rpt` | 时序摘要（WNS/WHS） |
| `build/gemm/gemm_power.rpt` | 功耗估算 |
| `build/build_gemm.tcl` | 一键重建本 GEMM 工程并重新导出上述报告（自动在英文临时目录建工程） |
| `src/ps/e2e_board.py` | 端到端：wav → numpy 特征 → 硬件 conv1 → numpy 其余层 → 分数，与 numpy 全浮点对拍 |
| `src/ps/gemm_board.py` | 裸 GEMM：a.bin/b.bin → 硬件 → c_hw.bin，与 c_ref.bin 对拍；含 MD5 自检 |
| `src/ps/make_board_data.py` | PC 端生成 a/b/c_ref.bin 的脚本 |
| `data/gemm/` | 测试数据：`bird_sample.wav`、`a.bin`/`b.bin`/`c_ref.bin`（M=12864）、`*_small.bin`（M=32） |
| `board/verify_gemm.sh` | 板端文件版本自检（MD5 + hwh 大小，不加载硬件） |

## 板端部署

板端运行时要求脚本、bit/hwh、测试数据在**同一个目录**（板端脚本用 `here = os.path.dirname(__file__)` 找同目录文件）：

```bash
# 在 PC 上把分散的文件收集成板端目录
scp build/gemm/gemm_soc.bit build/gemm/gemm_soc.hwh xilinx@<board>:/home/xilinx/gemm/
scp src/ps/e2e_board.py src/ps/gemm_board.py       xilinx@<board>:/home/xilinx/gemm/
scp data/gemm/*                                     xilinx@<board>:/home/xilinx/gemm/
scp src/ps/audio_model.npz                          xilinx@<board>:/home/xilinx/gemm/
scp board/verify_gemm.sh                            xilinx@<board>:/home/xilinx/gemm/
```

然后板端：

```bash
cd /home/xilinx/gemm
bash verify_gemm.sh                          # 0. 自检文件版本
sudo python3 gemm_board.py --small           # 1. 小数据快速验证
sudo python3 gemm_board.py                   # 2. 全量 GEMM 对拍
sudo python3 e2e_board.py                    # 3. 端到端
sudo python3 e2e_board.py --repeat 5        #    重复 5 次测稳定耗时
```

## 已实测结果（PYNQ-Z2 @100 MHz，2026-10-25）

> ⚠️ 版本对应关系：下面的数字是在 **2026-10-25 那一版 bit**（`gemm_soc.bit` MD5
> `81714b83…`，hwh `3b54a09c…`）上跑出来的。本目录提交的 `gemm_soc.bit` 是
> **2026-10-26 用 `build_gemm.tcl` 重建的版本**（MD5 `8240f2dc…`，hwh `509b0336…`，
> hwh 大小同为 586046、资源/时序报告也由这次重建产生）。重新综合不改逻辑，
> 但**功能等价性还没在这块板上重新跑过**，引用下面数字前请先跑一次
> `e2e_board.py` 确认分数仍为 0.9979 左右。

```
numpy 全浮点  分数 = 0.997876
硬件 conv1    分数 = 0.997878
conv1 最大误差 = 0.001838（容差 0.02，点数 0/205824）
GEMM 硬件 conv1 单次耗时 = 0.0067s（--repeat 5）；numpy 整网(含conv1) 0.497s
判定: 仙八色鸫  阈值=0.9850
==== 硬件 conv1 端到端 PASS（与浮点一致） ====
```

**口径说明**：
- 6.7 ms 是**旧计时口径**下的值：脚本当时在等完两路 MM2S 之后才开始计时，测到的是"离看到
  ap_done 还差多久"，所以它是核完成时间的**下界**，且 `--repeat 5` 只打印最后一次（单次样本）。
  2026-10-26 已把计时起点改到写 `ap_start` 之前，并按 N 次给最小/中位/最大——**上板重跑后
  请用新值替换 6.7 ms**。
- 该值**不含** im2col、Q12 量化、DMA 传输、cache flush/invalidate、反量化。
- 0.497 s 是 numpy 整网（含 STFT/mel/conv1/conv2/conv3/FC/sigmoid）。
- 两者不能直接相除声称加速比；公平加速比（硬件 conv1 端到端 vs numpy conv1 单独）
  用 `e2e_board.py --bench 20` 测，目前待补。

## 设计要点

- 三路 AXI DMA：`dma_A`/`dma_B` 为 MM2S（PS→PL），`dma_C` 为 S2MM（PL→PS）。
- 数据精度：A/B 为 int16 Q12，C 为 int16 Q12，PS 侧 `/4096.0` 反量化。
- bias 与 ReLU 烘焙进 HLS 核内部，PS 只送 A/B。
- 驱动走寄存器轮询（`PYNQ_DISABLE_DMA_INTERRUPT=1`），以 `ap_done`（ap_ctrl bit1）
  作为计算完成权威判据。
- `C_SG_LENGTH_WIDTH=23`，单次 DMA 可传 8 MB（突破默认 16 KB 上限）。

## GEMM overlay 资源/时序/功耗（routed 实测，2026-10-26）

| 资源 | 占用 | 可用 | 利用率 |
|---|---|---|---|
| Slice LUTs | 5376 | 53200 | 10.11% |
| Slice Registers | 7505 | 106400 | 7.05% |
| Block RAM Tile | 11 | 140 | 7.86% |
| DSP48 | 67 | 220 | 30.45% |

- 时序：100 MHz，WNS +1.520 ns、WHS +0.008 ns，0 个失败端点。
- 功耗：总 1.741 W（动态 1.602 + 静态 0.139），confidence Medium，结温 45.1 ℃ 为估算。

## 待补

- 用仓库这一版（2026-10-26 重建）bit 重跑 `e2e_board.py`，确认分数/误差与 10-25 一致。
- 公平加速比的板端计时：`sudo python3 e2e_board.py --bench 20`（硬件 conv1 端到端含 Q12
  量化 + DMA 搬运 vs numpy conv1 单独，各 20 次取中位数）。

## 相关踩坑

上板过程中沉淀的 6 条 HLS 加速器踩坑见 `../../skill/pitfalls/pynq_pitfalls.md` D 类
（D1 TLAST 缺失 / D2 DMA 16 KB 上限 / D3 中断未接对 / D4 FCLK 未显式设置 /
D5 bit-hwh 版本不一致 / D6 ap_done 才是完成权威判据）。
