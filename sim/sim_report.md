# 仿真报告

本项目 PL 侧手写 RTL 的行为级仿真结果。仿真工具：Vivado xsim v2026.1。
所有仿真均可在无板卡环境下复现。

> GEMM 加速器为 Vitis HLS 自动生成，其 RTL 与 C 模型的一致性由 HLS 工具链的
> C/RTL co-simulation 保证；数值精度由板端 `e2e_board.py` 对拍验证
> （最大误差 0.001838，205824 点 0 超差），不再单独写仿真 testbench。

## 1. I2S 接收核（i2s_mems_rx）

| 项 | 内容 |
|---|---|
| RTL 来源 | 手写 `src/fpga/i2s_mems_rx.v` |
| Testbench | `sim/i2s_mems_rx_tb.v` |
| 运行脚本 | `sim/run_sim.sh` |
| 结果日志 | `sim/sim_result.log` |

### 覆盖场景

- 标准 I2S 协议：bclk/ws 由核自生成，testbench 模拟 INMP441 在 bclk 下降沿驱动 sd
- 24bit MSB-first 串行接收
- 左槽（ws=0）/ 右槽（ws=1）交替
- 24bit 符号扩展为 32bit（`{{8{v[23]}}, v}`）
- AXI4-Stream 输出：tdata/tvalid/tready 握手
- AXI-Stream 反压：25% 周期 tready=0，验证 FIFO 在反压下不丢数据、顺序不错
- `m_axis_tlast` 恒为 0（固定长度 buffer 传输）
- 正负样本覆盖：左槽 `0x100000+slot`（正），右槽 `0xE00000+slot`（负）

### 结果

```
接收 beats: 128
错误数: 0
测试结果: PASS
```

## 2. 复现方式

```bash
cd sim
bash run_sim.sh
```

前置：Vivado 工具链在 PATH（`xvlog`/`xelab`/`xsim`）。

## 3. 已知限制

- I2S tb 未测运行中拉复位场景
- 未跑 code coverage 覆盖率分析
