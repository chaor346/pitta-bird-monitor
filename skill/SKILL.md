---
name: pynq-bringup-check
description: PYNQ/Zynq 工程上板前的通用验证能力包。用于把 .hwh 转成寄存器驱动骨架并对账硬编码偏移、静态检查 Vivado 块图连通性与 AXI 位宽配置、自检 AXI DMA 通路（覆盖检查 + 错误位 + 吞吐）、从 Vivado 报告提取资源与时序指标并做基线回归、以及按容差比对硬件输出与黄金参考。当用户提到 PYNQ overlay、DMA 不传输或数据全 0、块图 validate 通过但上板异常、资源/时序数据整理、硬件输出与参考不一致时使用。
---

# PYNQ 上板前验证（pynq-bringup-check）

一套与具体题目解耦的 PYNQ 验证能力。所有工具只依赖 Python 标准库（`.npy` 比对需 numpy），
`--self-test` 不需要 Vivado、不需要板卡。详细说明见同目录 `README.md`。

## 何时使用

| 症状 / 任务 | 用哪个 |
|-------------|--------|
| 不知道某个 IP 的寄存器偏移，或怀疑偏移写错 | `tools/hwh_probe.py` |
| 想直接生成寄存器驱动，不手抄偏移 | `tools/hwh_probe.py --emit-driver` |
| 块图 validate 通过，但上板数据不对 | `tools/bd_lint.py` |
| DMA 不启动 / 数据全 0 / 状态位恒定 | `tools/dma_selftest.py` |
| 要整理 LUT/FF/BRAM/DSP、WNS，或比较优化前后 | `tools/vivado_report.py` |
| 硬件输出与软件参考是否一致 | `tools/golden_compare.py` |
| 交接 / 提交前想知道这套东西还能不能用 | `tools/verify_pack.py` |
| 要决定算法哪部分放 PL | `templates/hw_sw_partition_prompt.md` |
| 事件触发多进程联动 | `templates/trigger_fsm.md` |
| 有目标才录、离开才停 | `templates/presence_recording.md` |
| HLS 核 S2MM 不置 IOC / DMA 16 KB 上限 / 中断挂死 / bit 版本不对 | `pitfalls/pynq_pitfalls.md` D 类 |
| "看起来都对但就是不对" | `pitfalls/pynq_pitfalls.md` |

## 工具速查

本 Skill 目录下的相对路径（`$S` 表示本目录）：

```bash
python3 $S/tools/hwh_probe.py overlay.hwh                    # 实例与寄存器表
python3 $S/tools/hwh_probe.py overlay.hwh --emit-driver drv/ # 驱动骨架
python3 $S/tools/hwh_probe.py overlay.hwh --audit app.py     # 偏移对账
python3 $S/tools/bd_lint.py --tcl build.tcl --hwh x.hwh --xdc pins.xdc
python3 $S/tools/dma_selftest.py --hwh x.hwh --dry-run
sudo python3 $S/tools/dma_selftest.py --bit x.bit --hwh x.hwh --json dma.json
sudo python3 $S/tools/dma_selftest.py --bit x.bit --hwh x.hwh --include-mm2s   # 有消费者时才测发送
python3 $S/tools/vivado_report.py --utilization u.rpt --timing t.rpt --md s.md --json s.json
python3 $S/tools/golden_compare.py --golden ref.csv --actual hw.csv --atol 1e-6
python3 $S/tools/verify_pack.py --project <project_root>
```

## 工作流

1. **摸底**：`hwh_probe.py <hwh>` 列出实例、基址、寄存器表；确认要用的通道
   （`C_INCLUDE_*`）与寄存器 `IS_ENABLED` 是否一致，不一致以参数为准。
2. **对账**：`hwh_probe.py <hwh> --audit <源码或目录>`。出现 `[ERROR] 无对应寄存器`
   就停下改代码，不要带去上板。
3. **结构**：`bd_lint.py --tcl … --hwh … --xdc …`。**退出码 1 表示有 ERROR，
   修完再综合**；WARN 需逐条确认；INFO（可选口未接）可忽略。
4. **通路**：先 `dma_selftest.py --dry-run` 确认计划（通道、偏移、测试项），
   再在板上执行。判定看「覆盖字数 > 0」和「错误位 = 0」，不看 `wait()` 是否返回。
   每次传输带 `--timeout`（默认 5 s），MM2S 默认不测（无消费者会永久等 TREADY）。
5. **指标**：`vivado_report.py` 产出资源/时序表；优化后用 `--baseline 上一次.json`
   看回归；`verify_pack.py` 做整体收口并生成 `verification/report.md`。

## 判定口径（不要放宽）

- 寄存器"能读"不等于通道"存在"；偏移一律以 `.hwh` 为准。
- 传输"完成"不等于数据"到位"；必须有覆盖率与错误位两项证据。
- 时序结论以 `timing.rpt` 的结论句和 WNS 为准，不以"综合通过"代替。
- 报告里的每个数字都要能由命令复现；无法复现的估计值必须标注为估计。

## 失效条件（出现以下任一情况，本包的结论不再成立）

| 条件 | 为什么失效 | 怎么办 |
|---|---|---|
| 不是 Xilinx Zynq / 没有 `.hwh` | 所有偏移、位宽、通道信息都从 `.hwh` 读；`bd_lint`/`dma_selftest` 只认 PYNQ 的 Overlay/MMIO/allocate | 先导出 `.hwh`；纯 RTL 仿真或非 Xilinx 平台请换工具 |
| `.bit` 与 `.hwh` 不配套 | 寄存器表与硬件对不上，读到的"正确值"是错的（本项目 D5 踩过） | 用同一版工程同时导出 bit/hwh，先做 MD5/大小核对 |
| 只用 `.xsa`、没有 `.hwh` | `hwh_probe.py` 不解析 xsa | 从 Vivado 导出 `hwh`，或手工补 hwh |
| 接口不是 AXI DMA（VDMA / AXI-Stream FIFO / 自定义 DMA） | `dma_selftest.py` 只按 AXI DMA 的 DMASR/CR 与 S2MM/MM2S 通道写死流程 | 参照脚本改寄存器映射，或改用厂商示例 |
| 精度/定标与你验证过的那组不同 | 容差是按 int16 + Q12 校准的（`golden_compare --atol`） | 换精度必须重新定容差并重跑黄金比对 |
| 触发/录像模板跑在 Windows 共享目录、NFS、容器只读盘上 | 模板依赖同一文件系统内的 `os.link()` 原子发布 | 换本地 ext4，或改成"临时文件 + rename"的等价方案 |
| PYNQ 版本升级（如 2.x → 3.x） | `Overlay`/`Clocks`/`allocate` 行为与 API 可能有变 | 先跑 `verify_pack.py` 与 `dma_selftest.py --dry-run`，再上板 |
| 结论未经板端执行 | `verification/report.md` 的 10 项 PASS 全是**离线**检查；`board_checklist.md` 未回填即视为未验证 | 按 `board_checklist.md` 上板并留存原始输出 |

## 不要用它做什么

- 不替代 `validate_bd_design`、综合、实现与时序分析。
- 不做上板实测的"代跑"：`dma_selftest.py` 的板端结果必须由真实板卡产生。
- 不判断功能是否满足题目需求（只判断通路、数值一致性、数据口径）。
- 不修改用户工程源码：除 `--emit-driver` 产出新文件外，工具只读输入。
