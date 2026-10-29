# GEMM 加速器 HLS IP（Vitis HLS 生成）

conv1 卷积加速器的 PL 侧实现，HLS IP 打包目录（`component.xml` 自洽）。
Verilog/VHDL 均由 Vitis HLS 综合生成，不是手写 RTL；HLS C++ 源文件不在本仓库。

> **命名说明**：HLS 自动生成的文件名含大写字母（`RAM_AUTO_1R1W`、
> `Pipeline_VITIS_LOOP` 等）。这些文件名是 Vivado IP 打包时固定的，重命名会导致
> Vivado 工程找不到文件，故保留原名。本项目其余目录与文件均为小写。

## 目录结构

| 路径 | 作用 |
|---|---|
| `component.xml` | IP 定义（VLNV `student:user:gemm_top:1.0`、接口、参数、寄存器） |
| `hdl/verilog/` | HLS 生成的 Verilog 源码（本项目实际使用，19 个文件） |
| `hdl/vhdl/` | HLS 同时生成的 VHDL 版本（HLS 默认打包，本项目未使用，可保留） |
| `constraints/gemm_top_ooc.xdc` | OOC（Out-of-Context）综合约束 |
| `drivers/gemm_top_v1_0/` | HLS 生成的软件驱动（`.mdd/.tcl/.yaml` + `xgemm_top*.c/.h`），供 Vitis/Standalone 使用 |
| `xgui/gemm_top_v1_0.tcl` | IP 在 Vivado 块图里的图形配置界面 |
| `doc/ReleaseNotes.txt`、`misc/logo.png` | HLS 打包附带的说明与图标 |

## hdl/verilog 文件清单

| 文件 | 作用 |
|---|---|
| `gemm_top.v` | 顶层模块（约 200 KB）：实例化下面所有子模块，暴露 s_axi_ctrl_bus / s_axis_A / s_axis_B / m_axis_C |
| `gemm_top_ctrl_bus_s_axi.v` | AXI4-Lite 控制总线从设备（M/K/N/ap_ctrl 寄存器映射） |
| `gemm_top_gemm_top_Pipeline_46_1_*.v` | GEMM 主流水线（M×K×N 矩阵乘核心） |
| `gemm_top_gemm_top_Pipeline_60_4_*.v` | 第二个流水线（A/B 缓冲读取） |
| `gemm_top_gemm_top_Pipeline_67_6_*.v` | 第三个流水线（乘加） |
| `gemm_top_gemm_top_Pipeline_82_8_*.v` | 第四个流水线（输出写回） |
| `gemm_top_gemm_top_Pipeline_95_11.v` | bias + ReLU 流水线（含 BIAS_Q_ROM） |
| `gemm_top_*_buf_RAM_AUTO_1R1W.v` | A/B/C 三端口 RAM wrapper（HLS 自动生成） |
| `gemm_top_mul_28s_28s_52_3_1.v` | 定点乘法器（28×28→52 bit） |
| `gemm_top_mul_32s_32s_32_2_1.v` | 定点乘法器（32×32→32 bit） |
| `gemm_top_regslice_both.v` | 寄存器切片（时序收敛用） |
| `gemm_top_sparsemux_*.v` | 稀疏多路选择器 |
| `gemm_top_flow_control_loop_pipe_sequential_init.v` | 流水级初始化 |
| `gemm_top_hls_deadlock_*.v/.vh` | HLS 死锁监视器（调试用，可综合） |
| `gemm_top_Pipeline_95_11_BIAS_Q_ROM_AUTO_1R.dat` | bias 常量 ROM 数据（Q12 定点） |

## 接口（来自顶层 `gemm_top.v`）

- **s_axi_ctrl_bus**：AXI4-Lite 从接口，挂 M_AXI_GP0
  - `0x00` AP_CTRL（bit0 ap_start / bit1 ap_done / bit2 ap_idle）
  - `0x10` REG_M（行数，本项目 12864）
  - `0x18` REG_K（列数，固定 9）
  - `0x20` REG_N（列数，固定 16）
- **s_axis_A**：AXI-Stream 输入 A（int16 Q12，M×K = 12864×9）
- **s_axis_B**：AXI-Stream 输入 B（int16 Q12，K×N = 9×16）
- **m_axis_C**：AXI-Stream 输出 C（int16 Q12，M×N = 12864×16，已含 bias + ReLU）
- **interrupt**：GEMM 完成中断输出

## 数据精度

- 输入 A/B：`ap_fixed<16,4>`（Q12，16 bit 有符号，4 bit 整数）
- 输出 C：`ap_fixed<16,4>`（Q12）
- PS 侧 `/4096.0` 反量化回 float

## 与 block design 的关系

本 IP 在 Vivado block design 里和这些 IP 一起组成 GEMM overlay：

- `ps7`（Zynq-7020，FCLK0=100MHz）
- `axi_dma` ×3（dma_A/dma_B 是 MM2S，dma_C 是 S2MM，`C_SG_LENGTH_WIDTH=23`）
- `axi_interconnect` ×4、`proc_sys_reset`、`xlconcat`（4 输入中断拼接）

块图由 `../../build/build_gemm.tcl` 一键重建；板端 bit/hwh 与综合/实现报告在
`../../build/gemm/`（`gemm_soc.bit` / `.hwh` + utilization/timing/power 报告）。

## 手写 RTL 在哪

本项目手写的 RTL 只有 `../i2s_mems_rx.v`（I2S 串行接收核，6.9 KB）。
GEMM 核是 HLS 生成的，这是竞赛 3.3.2 允许的实现方式（"RTL、Vitis HLS、
AI Engine、PS 侧软件及其任意组合均可"）。
