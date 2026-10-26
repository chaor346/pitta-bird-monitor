# 板端实测清单（待本队执行并回填）

本文件是**执行清单**，不是结果。`skill/verification/` 里已有的报告全部来自离线检查；
下列条目需在真实 PYNQ-Z2 上运行后，把输出贴回本文件并附日志路径，才算"板端已验证"。

原则：每条都要有**可复现的命令 + 原始输出 + 判定**。没有原始输出的一律写「未执行」。

---

## 0. 准备

```bash
# 板子上确认环境
python3 -c "import pynq, numpy; print(pynq.__version__, numpy.__version__)"
uname -a
# 板子 IP 与目录（按本队实际填写）
BOARD=192.168.2.99
BASE=/home/xilinx/pitta_bird_monitor
```

拷入产物：

```bash
scp build/inmp441.bit build/inmp441.hwh xilinx@$BOARD:$BASE/
scp -r skill/tools xilinx@$BOARD:$BASE/skill_tools/
```

回填项：板卡型号 / 器件 / PYNQ 版本 / 内核版本 = ____________

---

## 1. DMA 通路自检（S3）

```bash
cd $BASE
python3 skill_tools/dma_selftest.py --hwh inmp441.hwh --dry-run
sudo python3 skill_tools/dma_selftest.py --bit inmp441.bit --hwh inmp441.hwh \
     --json dma_selftest.json
sudo python3 skill_tools/dma_selftest.py --bit inmp441.bit --hwh inmp441.hwh --seconds 60
```

判定：

| 项 | 通过条件 | 实测值 | 结论 |
|----|----------|--------|------|
| S2MM 覆盖字数 | > 0 | | |
| 错误位 0x70 | = 0 | | |
| 单次耗时 / 吞吐 | 记录，不设门槛 | | |
| 60 s 持续吞吐（P05 / 均值） | 无异常轮次 | | |
| MM2S | 若未实现应显示"跳过" | | |

证据文件：`dma_selftest.json`、终端输出。

⚠️ 若覆盖字数为 0：先确认麦克风已接、I2S 已起振（`audio_test` 能录到非零 RMS），
再怀疑 DMA。这是"传输完成但源端没发数"的典型情形。

---

## 2. 音频采集基线（项目侧，用于对照）

```bash
sudo python3 inmp441_record.py --overlay inmp441.bit --seconds 5 --wav board_5s.wav
```

判定：左右声道 RMS 打印非 0，WAV 可播放，时长与 `--seconds` 一致（±0.1 s）。
回填：L RMS = ______，R RMS = ______，文件时长 = ______ s

---

## 3. 黄金参考比对（S5）

针对**本项目**，建议的最小配对：

1. 用 PC 侧 numpy 实现（或 `infer_pc.py`）对同一段音频算出 logit / mel 矩阵，存 `ref.npy`；
2. 板端用同一段音频、同一模型算出结果，存 `hw.npy`；
3. 比对：

```bash
python3 skill_tools/golden_compare.py --golden ref.npy --actual hw.npy --atol 1e-4 --json cmp.json
```

判定：超差数 = 0（定点/浮点差异用 `--rtol 1e-4` 放宽）。
回填：超差 = ______ / ______，最大绝对误差 = ______

---

## 4. 资源与时序（S4，在 PC 上跑即可）

```bash
python3 skill/tools/vivado_report.py --utilization build/utilization.rpt \
        --timing build/timing.rpt --md verification/vivado_summary.md \
        --json verification/vivado_summary.json
```

判定：WNS > 0 且结论句为"constraints are met"。
本项**已在 PC 上完成**：LUT 3.15%、WNS 2.029 ns。无需上板重复。

---

## 5. 触发与录像（S8 / S9，项目侧）

```bash
# 终端1：音频检测     终端2：图像识别 + 录像
sudo python3 inmp441_predict_pause.py ...
sudo python3 trigger_board_presence.py ...
```

判定与回填：

| 项 | 通过条件 | 实测 |
|----|----------|------|
| 触发延迟（写文件 → 图像端检测到） | 记录 P50/P95 | |
| 录像后滚时间（鸟离开 → 结束） | 与 `absence_hits`/`absence_sec` 推算一致 | |
| 有效帧占比 | 明显高于固定时长方案 | |
| 锁文件生效（录像期间音频暂停、结束恢复） | 日志可见 | |
| 连续运行时长 / 异常次数 | 记录 | |

---

## 5.5 GEMM 加速器验证与公平加速比（板端）

先把 GEMM 相关文件放到板端同一目录（见 `build/gemm/README.md` 的部署命令）：

```bash
# PC 上收集（bit/hwh、脚本、数据、权重）
scp build/gemm/gemm_soc.bit build/gemm/gemm_soc.hwh xilinx@$BOARD:$BASE/gemm/
scp src/ps/e2e_board.py src/ps/gemm_board.py        xilinx@$BOARD:$BASE/gemm/
scp data/gemm/*                                      xilinx@$BOARD:$BASE/gemm/
scp src/ps/audio_model.npz                           xilinx@$BOARD:$BASE/gemm/
```

板端执行：

```bash
cd $BASE/gemm
sudo python3 gemm_board.py --small        # 小数据快速对拍
sudo python3 gemm_board.py                # 全量 GEMM 对拍 c_ref
sudo python3 e2e_board.py                 # 端到端，对拍 numpy 分数
sudo python3 e2e_board.py --bench 20      # 公平加速比（各 20 次取中位数）
```

判定与回填：

| 项 | 通过条件 | 实测 |
|----|----------|------|
| 裸 GEMM 对拍 | 与 c_ref 一致（MD5/容差） | 待补（10-25 只留了端到端输出，未留 c_hw 对拍） |
| 端到端分数 | 与 numpy 差 < 0.01 | ✅ 2026-10-25：0.997878 vs 0.997876（差 2e-6） |
| 最大误差 | 容差 0.02 下 0 点超差 | ✅ 2026-10-25：0.001838，0/205824 点超差 |
| **公平加速比（端到端）** | 记录（硬件含量化+搬运 vs numpy conv1） | 待测（`--bench 20`） |
| 纯核加速比 | 记录（仅参考） | ✅ 2026-10-25：核 6.7 ms；numpy 整网 0.497 s（不可直接相除） |

> 已实测（2026-10-25，对应 bit MD5 `81714b83…`）：分数 0.997878 vs 0.997876、最大误差
> 0.001838、核 6.7 ms；公平加速比需用 `--bench 20` 补测。
> ⚠️ 仓库现在的 bit 是 2026-10-26 重建版（MD5 `8240f2dc…`），引用上述数字前需在本板
> 重跑一次 `e2e_board.py` 确认。

---

## 5.6 系统连续运行时长（板端，长测）

```bash
# 传监控脚本（PC）
scp board/stability_monitor.sh xilinx@$BOARD:/home/xilinx/
# 板端：启动服务 + 后台监控（每 5 分钟一条）
sudo systemctl start pitta-vision pitta-audio
nohup bash stability_monitor.sh --interval 300 --out stability_log.csv &
```

让系统连续跑 8h / 24h，期间手动播几次鸟叫、放几张鸟图，确认仍能触发录像（活性）。

```bash
column -t -s, stability_log.csv
```

判定：两个服务始终 active、**vision** 的 NRestarts 不增加（vision 正常应长期不重启）、
MemAvailable 不持续下滑（无泄漏）。
注意：`pitta-audio.service` 是 `--seconds 1800` + `Restart=always`，**每约 31 分钟正常退出
并重开新会话**，`audio_restarts` 按这个节奏递增属正常，不能当作不稳定；异常是重启间隔
明显短于 31 分钟或出现 failed。
回填：连续无故障运行 = ______ h；期间活性检查 ______ 次全部正常 / 异常现象 ______。

---

## 6. 回填后要做的事

1. 把本文件改名或加后缀标注日期，例如 `board_checklist_2026-11-01.md`，保留历史；
2. 在 `skill/README.md` 第 3 节索引表的「板端实测」列，把 ⬜ 改成 ✅ 并注明日期；
3. 若某项未通过，把现象追加到 `pitfalls/pynq_pitfalls.md`（这是最有价值的沉淀）；
4. 在项目根目录重跑 `python3 skill/tools/verify_pack.py --project .` 刷新 `verification/report.md`。
