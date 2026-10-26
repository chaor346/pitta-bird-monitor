# PYNQ 通用技能包（v0.3）

面向全国大学生嵌入式芯片与系统设计竞赛 · 自主选题赛道（3.3.5.2 技能包要求）。

本目录的定位是**可迁移的能力包**，不是本项目的说明书：换个题目、换块 PYNQ 板卡，
仍然能直接拿来用。项目专属的内容只在 `templates/` 里作为「填好的示例」出现，
且明确标注了哪些数字是本项目实测、哪些只是分析结论。

- 适用平台：PYNQ 框架下的 Zynq-7000 / Zynq UltraScale+ / Kria 板卡（工具本身不限定器件）
- 运行环境：PC 侧 Python ≥ 3.6（纯标准库，`--self-test` 不需要 Vivado、不需要板卡）
- 板端脚本：PYNQ-Z2 官方镜像（Python 3.6 + numpy）可直接运行

---

## 0. 这个包解决什么

FPGA + PYNQ 的调试时间里，很大一部分不是花在"设计想不通"，而是花在四类可复现的坑上：

| 坑 | 表现 | 本包的对应能力 |
|----|------|----------------|
| 寄存器偏移靠手抄 | DMA 不启动、状态位恒 0、无任何报错 | S1 从 `.hwh` 生成驱动骨架并反向对账 |
| 块图"能 validate"但不符合意图 | 上板数据全 0 / 通路断 | S2 双模式静态检查（tcl 意图 + hwh 事实） |
| DMA"完成了"但数据没到 | 读到旧值、覆盖率 0 | S3 预填模式 + cache 维护 + 错误位检查 |
| 资源/时序数据手抄 | 报告数字与实现不符、优化前后无法对比 | S4 报告解析 + 基线回归对比 |

## 1. 30 秒上手

```bash
cd skill/tools

python3 hwh_probe.py --self-test          # hwh_probe/bd_lint/vivado_report/golden_compare 均可离线自检
python3 verify_pack.py --project ..       # 一条命令跑完所有检查，产出验证台账
```

对任意 PYNQ 工程（只需有 `.hwh`）：

```bash
python3 hwh_probe.py <overlay.hwh> --emit-driver drv/   # 生成寄存器驱动骨架
python3 bd_lint.py --hwh <overlay.hwh>                  # 检查真实连通性
python3 dma_selftest.py --hwh <overlay.hwh> --dry-run   # 看要在板上做什么
```

## 2. 目录结构

```
skill/
├── README.md                 # 本文件：技能索引 + 逐项说明 + 验证台账
├── SKILL.md                  # 同一套能力的 agent-skill 形态（可被 Claude Code / 豆包加载）
├── tools/                    # 校验脚本（全部可独立运行，无第三方依赖）
│   ├── hwh_probe.py          #   S1 .hwh 解析 / 驱动骨架 / 偏移对账
│   ├── bd_lint.py            #   S2 块图静态检查（tcl + hwh）
│   ├── dma_selftest.py       #   S3 AXI DMA 通路自检（板端 + dry-run）
│   ├── vivado_report.py      #   S4 综合/实现指标提取与基线对比
│   ├── golden_compare.py     #   S5 黄金参考比对
│   └── verify_pack.py        #   S6 一键自检（含命名规范、构建可复现性）
├── templates/                # 提示词工作流与案例模板（填好即用）
│   ├── hw_sw_partition_prompt.md   # S7 算法 → 软硬件划分
│   ├── trigger_fsm.md              # S8 事件触发状态机
│   └── presence_recording.md       # S9 目标存在性录像
├── pitfalls/
│   └── pynq_pitfalls.md      #   S10 踩坑清单（25 条：A 硬件 5 / B PS 8 / C 协同 6 / D HLS 上板 6）
├── verification/             # 验证产物（前 6 项由 verify_pack.py 生成，可复现）
│   ├── report.md             #   结论表
│   ├── selfcheck.log         #   完整输出
│   ├── bd_lint.json          #   本例块图检查结果
│   ├── vivado_summary.md/.json
│   ├── hwh_summary.json      #   .hwh 解析摘要（实例/寄存器，不含端口明细）
│   └── board_checklist.md    #   板端实测执行清单（手写，待本队回填）
```

## 3. 技能索引

| 编号 | 名称 | 类型 | 换题目可用 | 换板卡可用 | 离线自检 | 真实工程数据 | 板端实测 |
|------|------|------|-----------|-----------|---------|-------------|---------|
| S1 | hwh_probe | 校验脚本 | ✅ | ✅ | PASS | PASS | 无需上板 |
| S2 | bd_lint | 校验脚本 | ✅ | ✅ | PASS | PASS | 无需上板 |
| S3 | dma_selftest | 校验脚本 | ✅ | ✅ | PASS（dry-run） | PASS（计划） | ⬜ 待执行 |
| S4 | vivado_report | 校验脚本 | ✅ | ✅ | PASS | PASS | 无需上板 |
| S5 | golden_compare | 校验脚本 | ✅ | ✅ | PASS | ✅ conv1 GEMM（max_err 0.001838，0/205824 超差） | 板端已跑 |
| S6 | verify_pack | 校验脚本 | ✅ | ✅ | PASS | PASS（10/10） | 无需上板 |
| S7 | 软硬件划分提示词 | 提示词工作流 | ✅ | ✅ | — | ✅ 已用（conv1 已上 PL，mel 未搬） | 无需上板 |
| S8 | 触发状态机 | 案例模板 | ✅ | ✅ | — | 已用（实测 <100 ms） | 部分实测 |
| S9 | 存在性录像 | 案例模板 | ✅ | ✅ | — | 已用（后滚 12 s） | 部分实测 |
| S10 | 踩坑清单 | 踩坑清单 | ✅ | ✅ | — | 25 条均有来源（18 条实测 / 7 条经验；含 D 类 HLS 上板 6 条） | 部分实测 |

「板端实测」列为 ⬜ 的，表示脚本已写好并通过离线检查，但**尚未在真实板卡上跑过**；
本包不声称这些项目已验证。详见第 8 节。

---

## 4. 逐项说明

### S1 `hwh_probe.py` —— 把 `.hwh` 当作唯一事实来源

**适用场景**：任何要访问 PL 寄存器的 PYNQ 工程（DMA、自定义 IP、AXI GPIO、加速器）。
尤其是「不知道某个 IP 的寄存器偏移是多少」「怀疑代码里的偏移写错了」的时候。

**使用方法**

```bash
python3 hwh_probe.py overlay.hwh                    # 实例表 + 寄存器表
python3 hwh_probe.py overlay.hwh --emit-driver drv/ # 生成 <实例>_regs.py
python3 hwh_probe.py overlay.hwh --audit app.py     # 源码里的偏移与 hwh 对账
python3 hwh_probe.py overlay.hwh --json out.json
```

生成的驱动骨架提供 `read/write/offset/wait_until`，偏移全部来自硬件描述，
并会把 `IS_ENABLED=false` 的寄存器标注为 `DISABLED`，避免对着占位寄存器调试。

**已验证效果**（本项目真实 `.hwh`）
- 正确解析 7 个实例、`axi_dma_0` 基址 `0x40400000`、19 个寄存器（`S2MM_DMACR 0x30`、
  `S2MM_DMASR 0x34`、`S2MM_DA 0x48`、`S2MM_DA_MSB 0x4C`、`S2MM_LENGTH 0x58`）。
- `--audit src/ps/inmp441_record.py`：10 处偏移引用 **全部命中**，并逐行给出
  「偏移 → 实例.寄存器名」的对应关系。
- 自动一致性检查发现一处真实矛盾：`C_INCLUDE_MM2S=0`（MM2S 通道未实现），
  而寄存器表把 `MM2S_DMACR/MM2S_DMASR/MM2S_SA/MM2S_SA_MSB` 标为启用。
- `--self-test` 覆盖：解析、基址、禁用通道、驱动骨架可 import、错误偏移必须被判为未知。

**从哪些失败中总结**：最早的驱动把 S2MM 控制寄存器偏移当成 `0x00`（沿用 MM2S 的排布），
写下去毫无反应、状态位也不变。v0.1 README 里留下的那句「S2MM_CR = 0x30（不是 0x00！）」
就是这次踩坑的记录。单点记住一个数字并不能防复发，因此改为从 `.hwh` 取全部偏移，
并把「对账」做成 `--audit`。

**失效条件**
- IP 未导出 `.hwh`（只有 `.bit`）时无法解析；需重新 `write_bitstream` 或从 `.xsa` 提取。
- 层次化设计里同名子模块会出现 `a.b` 形式的实例名，驱动骨架文件名已做替换，但实例属性需手动对齐。
- `.hwh` 只是硬件描述，不保证 PL 侧逻辑真的正确——它证明"寄存器存在"，不证明"功能可用"。

---

### S2 `bd_lint.py` —— 块图"能 validate"不等于"符合意图"

**适用场景**：综合前检查块图结构；综合后核对真实连通性；接手别人的工程时快速摸底。

**使用方法**

```bash
python3 bd_lint.py --tcl build/build.tcl --xdc src/fpga/pins.xdc   # 综合前
python3 bd_lint.py --hwh overlay.hwh                              # 综合后
python3 bd_lint.py --tcl build.tcl --hwh x.hwh --json out.json    # 两者互补
```

**规则集**（不写死任何 IP 实例名）

| 规则 | 级别 | 检查内容 |
|------|------|----------|
| T001 | ERROR | 一条 net 只连 1 个引脚（悬空连接） |
| T002 | ERROR | AXI-Stream 两端同为 m_axis 或同为 s_axis |
| T003 | ERROR | 同一网络混用高有效 reset 与低有效 aresetn |
| T005 | ERROR | DMA 流位宽 ≠ 内存位宽且未开 DRE（能过 validate，上板丢数据） |
| T006 | WARN | IP 创建后未参与任何连接 |
| T007 | WARN | 对外端口未在 XDC 中约束 |
| T009 | WARN | 存在多个时钟源，需确认跨域处理 |
| T010 | ERROR | 地址区间重叠 |
| H001 | ERROR | 时钟/复位输入无驱动 |
| H002 | ERROR | AXI-Stream 必需握手信号无连接 |
| H004 | WARN | 通道参数为 0 但寄存器标为启用 |
| H005 | INFO | 可选/调试口未接（`aux_reset_in` 等，属正常） |

**已验证效果**（本项目）
- `--tcl build/build.tcl --hwh build/inmp441.hwh --xdc src/fpga/inmp441_pmodb.xdc`
  → **ERROR=0，WARN=1，INFO=6**（WARN 即 S1 发现的那处 MM2S 矛盾）。
- 自检覆盖：续行 `\` 合并、一条 `connect_bd_intf_net` 的两个 pin 都必须抓到、
  6 类结构规则、XDC 约束比对、hwh 悬空判定。
- 对真实设计做过降噪：`aux_reset_in`、`mb_debug_sys_rst`、`dcm_locked`、
  `*ISSUECAP*_EN` 这类本来就可不接的端口归为 INFO，否则工具在真实工程上会满屏噪音。

**从哪些失败中总结**：v0.1 的 `validate_bd.py` 用正则只捕获 `connect_bd_intf_net`
行里的**第一个** pin，导致 `axi_dma_0/S_AXIS_S2MM` 永远被判为"未连接"；且把
`i2s_mems_rx`、`axi_dma_0` 写死在必查列表里，换个工程就失效。v0.2 改为"解析全部 pin +
规则不绑定实例名"，并把 XDC、位宽、地址重叠纳入检查。

**失效条件**
- tcl 模式只能看到脚本里写出来的东西：用 GUI 手工连的块图，需从 Vivado 导出 bd tcl 再检查。
- hwh 模式只能判断"连没连"，判断不了"连得对不对"（例如把 stream 接到错误通道）。
- 自定义 IP 的内部端口语义未知，只能按名字与信号类型做启发式判断。
- T009（多时钟源）只认 `FCLK_CLK*` 与 `clk_out*` 两种命名；自定义时钟名不会被统计，属提示级规则，不要当结论。

---

### S3 `dma_selftest.py` —— 先证明 DMA 通路本身是通的

**适用场景**：任何使用 AXI DMA 的 PYNQ 工程。上板后第一件事、"数据全 0"、
"传输不结束"、换 IP 版本后回归，都适用。

**使用方法**

```bash
python3 dma_selftest.py --hwh overlay.hwh --dry-run          # PC 上先看计划
sudo python3 dma_selftest.py --bit x.bit --hwh x.hwh --json dma.json
sudo python3 dma_selftest.py --bit x.bit --seconds 30        # 持续吞吐
sudo python3 dma_selftest.py --bit x.bit --hwh x.hwh --include-mm2s   # 链路确实有消费者时才测发送
```

每次传输都带超时（`--timeout`，默认 5 s）。源端没在发数时 S2MM 不会完成，
没有消费者的 MM2S 会一直等 TREADY——这两种情况都会在超时后报错退出，而不是把脚本挂死。
MM2S 默认跳过，因为"发送端有没有人接"工具无法判断。

**判定逻辑**（不靠"wait 返回了"就宣布成功）
1. 用 `C_INCLUDE_*` 判断通道是否真的实现，未实现的直接跳过；
2. 缓冲区预填已知模式 → `flush` → 传输 → `wait` → `invalidate`；
3. 统计**被覆盖的字数**，为 0 说明"传输完成但数据没来"；
4. 读 `*_DMASR`，`0x70`（DMAIntErr/DMASlvErr/DMADecErr）非 0 直接报错；
5. 记录每次耗时，持续模式给出均值 / P05 / 最大值，而不是瞬时峰值。

偏移优先取 `.hwh`，退化到 PYNQ 的 `register_map`；实例按 IP 类型自动发现，不要求叫 `axi_dma_0`。

**已验证效果**
- `--dry-run` 在本项目 `.hwh` 上正确识别：`axi_dma_0 @ 0x40400000`、
  **S2MM 已实现、MM2S 未实现（跳过）**，并只列出已实现通道要用的 5 个寄存器偏移
  （`S2MM_DMACR 0x30`、`S2MM_DMASR 0x34`、`S2MM_DA 0x48`、`S2MM_DA_MSB 0x4C`、`S2MM_LENGTH 0x58`）。
- **板端真实传输尚未执行**（见第 8 节），因此本包不给出任何 DMA 吞吐数字。

**从哪些失败中总结**：v0.1 的 `check_dma.py` 先往缓冲区写 `0xA5A5A5A5` 再做 S2MM 传输，
方向搞反了（S2MM 是"流入内存"，预填的图案会被覆盖，等于什么都没验证）；
也没有检查覆盖率和错误位；`sr` 变量在极端情况下还可能未定义。

**失效条件**
- 流源没有在发数（例如麦克风未接、I2S 未起振）：覆盖率为 0 是正常现象，要先确认源端在工作。
- 分包模式（源端带 TLAST）：一次请求长度大于单包时，DMA 会在首个 TLAST 处提前完成，
  这是协议行为，不是故障。
- 未接中断时不要依赖高层 `wait()` 的中断路径；本工具用线程 + 超时兜底，
  真实驱动里可参考 `pitfalls/pynq_pitfalls.md` 的 B6（轮询加 sleep）与 B8（软复位等完成）。

---

### S4 `vivado_report.py` —— 资源与时序不该手抄

**适用场景**：整理综合/实现数据、写报告、做优化前后对比、回归检查。

**使用方法**

```bash
python3 vivado_report.py --utilization build/utilization.rpt --timing build/timing.rpt \
        --md report/summary.md --json report/summary.json
python3 vivado_report.py --utilization u2.rpt --timing t2.rpt --baseline report/summary.json
```

**已验证效果**（本项目真实报告）

| 资源 | Used | Available | Util% |
|------|------|-----------|-------|
| LUT | 1675 | 53200 | 3.15 |
| FF | 2281 | 106400 | 2.14 |
| BRAM | 1 | 140 | 0.71 |
| DSP | 0 | 220 | 0.00 |
| BUFG | 1 | 32 | 3.13 |

- 时序：**WNS 2.029 ns**、TNS 0、**WHS 0.016 ns**、失败端点 0 / 6748，结论句"约束满足"。
- 时钟：`clk_fpga_0` 100 MHz（周期 10 ns）。
- 自检覆盖：8 列与 12 列两种 `Design Timing Summary` 格式（早期工具链少 WPWS/TPWS 两列）、
  资源行解析、时钟表、基线对比、时序违例时退出码为 1。

**从哪些失败中总结**：报告是定宽文本，手工抄一遍十几分钟且容易抄错一位；
换一版综合结果又要重抄，"优化前后对比"经常变成拿两版不同口径的数字硬比。
工具把口径固定下来：同一条命令、同一张表、同一个 JSON。

**失效条件**
- 只认英文版报告；中文界面输出的表头不同，需先切英文。
- 报告被截断或只导出了部分章节时字段会缺失，工具会跳过缺失项而不是猜值。
- 资源名随器件家族变化（`Slice LUTs` / `CLB LUTs`、`DSPs` / `DSP48E1`），
  别名表覆盖常见几类，冷门器件需自行补别名。

---

### S5 `golden_compare.py` —— 把"看起来对"变成可复现的判定

**适用场景**：硬件输出 vs 软件参考（CSV / NPY / 文本数值）；定点化、截位、饱和、
通道顺序这类悄悄改变数值的问题。

**使用方法**

```bash
python3 golden_compare.py --golden ref.csv --actual hw.csv --atol 1e-6
python3 golden_compare.py --golden ref.npy --actual hw.npy --rtol 1e-4 --json cmp.json
python3 golden_compare.py --golden ref.txt --actual hw.txt --show 5
```

**判定**：`|actual - golden| > atol + rtol * |golden|` 记为超差；输出总超差数、
每列最大绝对/相对误差、首个超差位置；CSV 的文本列走精确比对。

**已验证效果**
- 自检覆盖数值容差（1e-6 差值通过 / 0.1 差值报错并定位到第 2 行）、文本列精确比对、
  NPY 形状不一致必须报错。
- **本项目 conv1 GEMM 上板实测**（PYNQ-Z2 @100 MHz，`e2e_board.py`）：
  硬件 conv1 输出 C_hw (12864×16，Q12 反量化后 float32) vs numpy 全浮点 C_fp，
  205824 点逐点 `|hw - fp|`：最大误差 **0.001838**，容差 0.02 下 **0 点超差**；
  端到端鸣声分数 0.997878 vs 0.997876，判定 PASS。
- 板端 `gemm_board.py` 还提供 `.bin` 黄金对（`C_ref.bin` vs `C_hw.bin`），
  可直接 `python3 golden_compare.py --golden C_ref.bin --actual C_hw.bin --rtol 1e-4` 复现。

**从哪些失败中总结**：本项目音频链路出现过"用 `& 0xffffff` 解码导致符号位丢失"，
波形看起来有声音、置信度却整体偏低。这类问题肉眼极难发现，必须有逐样本比对。

**失效条件**
- 两边采样点没对齐（长度不同 / 有偏移）时不能直接比，需先对齐或改用相关/DTW。
- 浮点与非确定性算法（多线程 numpy）结果可能有末位差异，容差要给 `rtol` 而非只给 `atol`。

---

### S6 `verify_pack.py` —— 一条命令给出可信度

**适用场景**：交接前、提交前、换机器后；也用于回答"这套东西现在还能不能用"。

**使用方法**

```bash
python3 verify_pack.py --project ..            # 全量
python3 verify_pack.py --project .. --tools-only  # 只有工具、无工程数据时
```

**已验证效果**：本项目 **PASS=10 / FAIL=0 / SKIP=0**，覆盖四个工具自检、
hwh 解析、块图检查、DMA 测试计划、综合/实现指标、构建脚本可复现性、
以及**竞赛要求的纯英文命名规范**。产物见 `verification/report.md` 与 `selfcheck.log`。

**失效条件**
- 工程缺少 `.hwh` / 报告时对应项会 SKIP，而不是假装通过。
- 构建可复现性检查只静态核对 `add_files` 的路径存在性，含 tcl 变量的路径不核对；
  它不执行 Vivado，因此不能替代一次真实构建。

---

### S7 「算法 → 软硬件划分」提示词工作流

**适用场景**：拿到一个算法要决定 PL/PS 怎么分。

**使用方法**：见 `templates/hw_sw_partition_prompt.md`，模板 + 算法一起给模型，
重点核对模型给出的"预期加速比"是否有计算依据。

**已验证效果**：在本项目 mel + CNN 上产出完整划分表，两条结论都落地了——
- **被放弃的候选**：FFT+mel 整体搬 PL（分析估算 20×，但 AXI-Stream 乒乓缓冲 +
  定点验证的工程量不划算，未实施）；
- **已实施**：conv1 im2col 成 GEMM，PL HLS 核 + PS 三路 DMA，板端 PASS
  （硬件分数 0.997878 vs numpy 0.997876，conv1 最大误差 0.001838，0/205824 超差）。
- 模板特别要求"计时口径对齐"：PL 侧只算 HLS 核 `ap_start→ap_done`，与 PS 对比时
  两端必须同口径，否则加速比不可信。详见模板填写示例。

**失效条件**：算法步骤未定、无资源约束、或要求"保证加速比"时，输出不可采信。

### S8 事件触发状态机模板

**适用场景**：一个进程检测到事件后通知另一个进程做重处理。

**使用方法**：见 `templates/trigger_fsm.md`，含状态图、7 个参数的建议值与调错后果、
触发通道三条硬规则、反向锁通道、5 步自检。

**已验证效果**：本项目鸟鸣 → 图像识别，实测触发延迟 **< 100 ms**。

**失效条件**：跨文件系统/容器时路径通知失效；事件频率高于处理能力会堆积；
需要亚毫秒响应时应改用中断或共享内存。

### S9 目标存在性录像模板

**适用场景**：检测到目标才录、目标离开才停。

**使用方法**：见 `templates/presence_recording.md`，含伪代码、按推理耗时反推参数的对照表、
写盘不阻塞检测的做法、5 步自检。

**已验证效果**：本项目实测后滚约 **12 s**（`absence-hits=3`、`absence-sec=6`），
录像期间用锁文件暂停音频推理，避免 CPU 争抢。

**失效条件**：检测模型漏检率高时状态机救不了；推理耗时 ≫ 目标停留时间时只能"录到曾经有"；
多目标交替出现需按 ID 分别维护 `last_seen`。

### S10 踩坑清单

**适用场景**：遇到"看起来都正常但就是不对"的时候按症状查。

**使用方法**：见 `pitfalls/pynq_pitfalls.md`，25 条按 A（硬件接口 5 条）/
B（PS 软件 8 条）/ C（系统协同 6 条）/ D（HLS 加速器上板 6 条）分类，
每条给出触发条件、现象、定位步骤、根因、修法、来源；文末有按症状索引的快速对照表。

**已验证效果**：
- A1–A4、B1–B2、B5、C1–C5（12 条）在本项目 I2S/DMA/触发链路上有明确失败记录或实测观测；
- A5、B3–B4、B6–B8、C6（7 条）是开发中采用的做法与通用经验，引用前请按自己工程复核；
- D1–D6（6 条）来自把 Vitis HLS GEMM 核从 PC 仿真搬到 PYNQ-Z2 上板的全过程：
  TLAST 缺失、DMA 16 KB 上限、中断未接对、FCLK 未显式设置、bit/hwh 版本不一致、
  ap_done 才是完成权威判据。这 6 条对任何"PL 侧放计算核 + PS 三路 DMA 喂数据"
  的工程都直接适用。

**失效条件**：清单是经验集合，不是定理；换器件家族（UltraScale+、Versal）时
时钟/复位/MPSoC/NoC 相关条目需重新验证；D 类目前只在 GEMM（AXI-Stream 点对点）
这一种核型上验证过，换 FFT/FIR/自定义 RTL 核时需按症状表自行排查。

---

## 5. 验证台账

一条命令即可复现全部结论：在**项目根目录**执行 `python3 skill/tools/verify_pack.py --project .`。
（`--project` 必须指到项目根；指到 `skill/` 会得到 5 个 SKIP，因为找不到 build/ 与 .hwh。）
逐项数字已写在第 4 节各项的「已验证效果」里，此处不重复；原始输出与结论表在：

- `verification/report.md` —— 结论表（PASS/FAIL/SKIP 一览）
- `verification/selfcheck.log` —— 每个子命令的完整 stdout
- `verification/bd_lint.json` / `vivado_summary.json` / `hwh_summary.json` —— 机器可读结果

## 6. 换题目、换板卡怎么用（三步）

1. **换板卡**：只改输入文件路径。`hwh_probe.py` / `bd_lint.py --hwh` / `dma_selftest.py`
   都从 `.hwh` 读器件与偏移，不写死 `xc7z020` 或 `0x40400000`。
2. **换题目**：保留 `tools/` 全部，替换 `templates/` 中示例参数。
   S7 的模板与题目无关；S8/S9 的模板结构不变，只换"事件"和"目标"。
3. **换团队**：先跑 `verify_pack.py --project <新工程>`。
   SKIP 的项说明新工程缺对应产物，FAIL 的项会直接给出重跑命令。

## 7. 与本项目的关系（解耦说明）

- **不绑定**：`tools/` 里没有任何 `inmp441`、`i2s_mems_rx`、`axi_dma_0`、
  `pitta` 之类的硬编码；实例名、偏移、器件型号全部来自输入文件。
- **绑定（仅作示例）**：`templates/` 中引用的实测数字（触发延迟 < 100 ms、录像后滚 12 s、
  LUT 3.15%、WNS 2.029 ns）来自本项目，用于说明模板"填好是什么样"。
  换题目时应替换为本队数据。
- **v0.1 脚本已移除**：`check_dma.py`、`validate_bd.py` 在 v0.2 中删除，避免有人误用。
  它们的问题（S2MM 方向写反、只抓第一个 pin、写死实例名）已写进 S2/S3 的
  「从哪些失败中总结」，需要对照时按那两段复现即可。

## 8. 已知限制（如实声明）

1. **板端未实测**：`dma_selftest.py` 的板端分支尚未在 PYNQ-Z2 上运行过。
   离线部分（通道识别、寄存器偏移来源、计划输出）已通过；上板前请先跑
   `--dry-run` 核对计划，再在板上执行并保留输出。
   具体命令、判定条件与回填表格见 `verification/board_checklist.md`——那是执行清单，
   不是结果；未回填即视为未验证。
2. **黄金比对覆盖范围有限**：S5 已在 conv1 GEMM 上板跑通（硬件 vs numpy 浮点，
   max_err 0.001838，0/205824 点超差，容差 0.02）；但 I2S 音频链路本身
   （PL 采样流 vs PC 录 WAV）尚未做逐样本黄金比对。D 类踩坑只在 GEMM 这一种
   AXI-Stream 点对点核型上验证过，换 FFT/FIR/自定义 RTL 核需按症状表自行排查。
3. **不替代 Vivado**：`bd_lint.py` 是意图检查，不能替代 `validate_bd_design`、
   综合、实现与时序分析；`verify_pack.py` 的构建可复现性只做静态路径核对。
4. **不覆盖 MPSoC/Versal 特有项**：本包在 Zynq-7000 上验证；UltraScale+ / Versal 的
   时钟、复位、NoC、AI Engine 相关检查需要补充规则。
5. **命名规范检查按竞赛要求**：目录与文件名只允许英文/数字/下划线/连字符/点，
   且**除 `README.md`、`SKILL.md` 外应全小写**；出现大写会给出 WARN。
   若本队提交规范允许其他字符，需自行调整。

## 9. 版本变更

| 版本 | 变更 |
|------|------|
| v0.1 | 5 条经验写在一个 README 里；2 个脚本（`check_dma.py`、`validate_bd.py`，已在 v0.2 删除） |
| v0.2 | 拆成 6 个可运行校验脚本 + 3 个模板 + 1 份踩坑清单；修掉 v0.1 的两个缺陷（S2MM 方向写反、只抓第一个 pin）；新增 `.hwh` 驱动骨架生成、偏移对账、位宽/地址/连通性规则、报告基线对比、黄金比对、一键自检与命名规范检查；产出可复现的验证台账 |
| v0.3 | conv1 GEMM 上板后回灌经验：S5 从"无本项目配对数据"更新为 conv1 实测（max_err 0.001838，0/205824 超差）；S7 填写示例从"未实施"更新为"conv1 已上 PL、mel 未搬"；踩坑清单新增 D 类 6 条（TLAST 缺失 / DMA 16 KB 上限 / 中断未接对 / FCLK 未显式设置 / bit-hwh 版本不一致 / ap_done 才是完成权威判据），总数 19 → 25；明确"计时口径必须对齐"这一加速比可信度边界 |
