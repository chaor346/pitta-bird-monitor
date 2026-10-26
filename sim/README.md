# sim/ 仿真

对 FPGA 侧手写 I2S 接收核 `i2s_mems_rx` 做行为级仿真，验证其把 INMP441 的 I2S 串行数据
正确接收、24bit 符号扩展为 32bit，并按 [左,右] 顺序输出到 AXI4-Stream。

> GEMM 加速器为 Vitis HLS 自动生成，RTL 与 C 模型一致性由 HLS 工具链 co-simulation
> 保证；数值精度由板端 `e2e_board.py` 对拍验证，不在此单独写 testbench。

## 文件

| 文件 | 说明 |
|------|------|
| `i2s_mems_rx_tb.v` | I2S 接收核 testbench（含 25% AXI-Stream 反压） |
| `sim_result.log` | 最近一次仿真输出：**PASS，0 错误，128 beats** |
| `sim_report.md` | 仿真报告（覆盖场景 + 结果汇总） |
| `run_sim.sh` | 一键编译+运行 |

## 命令行复现（Vivado 自带 xsim，无需板卡）

需先在 PATH 中能找到 Vivado 的 `xvlog/xelab/xsim`（或用 Vivado 安装目录下 `bin/` 的全路径）。

```bash
bash run_sim.sh
```

预期输出：

```
=== 仿真开始（BACKPRESSURE=1）===
=== 仿真结束 ===
接收 beats: 128
错误数: 0
测试结果: PASS
```

> 说明：testbench 参数 `N_PAIRS=12` 是设计校验窗口（24 beats），仿真跑了 3 ms
> 实际窗口，按 32 kHz 采样率 ≈ 64 个左右/右槽 = 128 beats，全部 0 错误。

## 测试方法

- Testbench 用确定性的"槽序号"模式生成数据：左槽（ws=0）发 `24'h100000+槽号`，
  右槽（ws=1）发 `24'hE00000+槽号`，正负样本各占一半（覆盖符号位两种情况）。
- 核自己生成 bclk/ws（与实际硬件一致），testbench 只在 bclk 下降沿驱动 sd，
  模拟 INMP441；核在 bclk 上升沿采样。
- 校验端在 AXI4-Stream 上逐 beat 比对，同时检查：
  - 数据 = 24bit 符号扩展（`{{8{v[23]}}, v}`）；
  - 顺序严格 [左,右]；
  - `m_axis_tlast` 恒为 0（核按固定长度 buffer 传输，不在每个样本提前结束）；
  - AXI-Stream 反压下（25% 周期 tready=0）FIFO 不丢数据、顺序不错。
- beat0 为复位后首个左槽：SD 驱动尚未与核自生成的 ws 完成沿同步，预期为空(0)，
  从 beat1 起全部对齐。

## GUI 查看波形（可选）

```bash
xelab -debug all i2s_mems_rx_tb -s simsnap
xsim simsnap -gui
# 在 Tcl Console：
#   add_wave -position end  sim:/i2s_mems_rx_tb/*
#   run all
# 重点观察：bclk/ws/sd、phase、shifter、m_axis_tdata/tvalid、FIFO 读写指针。
```
