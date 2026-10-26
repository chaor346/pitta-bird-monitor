# board/test_output/ 板端实测证据

本目录存放**在 PYNQ-Z2 上真实运行**产生的输出，供 `data/comparison.csv` 引用。
原则：有数字就必须有对应日志；没有日志的数字一律标"待实测"。

## 现有文件

| 文件 | 来源 | 能证明什么 | 不能证明什么 |
|------|------|-----------|-------------|
| `end_to_end_20261024.md` | 2026-10-24 22:18 一次完整联动的原始 journalctl 片段 + 时间线整理 | 音频触发（score 0.9863，阈值 0.985，单窗口推理 2.075 s）、视觉 RECORD-INFER 6 次耗时 5.65~6.72 s、录像 37.40 s/187 帧、MP4 编码参数、misses/span 停止过程 | 单次样本，不能代表 P50/P99；不是图像推理基准测试（是录像期间抽样）；无 CPU/内存占用 |

> 原始网页内嵌 Jupyter 访问 token，因此原始 HTML 未放入仓库，仅保留去掉凭据的清单。

## 待补（按 `data/comparison.csv` 的"待实测"项对应）

| 需要的日志 | 覆盖指标 | 现状 | 采集方式 |
|-----------|---------|------|---------|
| `infer_latency_YYYYMMDD.log` | 图像推理基准延迟 | **仍缺**（现有 5.65~6.72 s 是录像期间抽样，不是基准） | 板上连续跑 ≥8 次 `./infer_ncnn <image> 320`，每次 `date +%s.%N` 记起止，完整输出重定向 |
| `audio_timing_YYYYMMDD.log` | 音频单窗口延迟 | **已有单次**（2.075 s，在 `end_to_end_20261024.md`） | 导出 `inmp441_predict_time.py` 的终端输出为文本；建议补 10~20 次取均值 |
| `e2e_run_YYYYMMDD.log` | 端到端 P50/P99、录像后滚 | **已有单次**（`end_to_end_20261024.md`），多次重复仍缺 | 重复联动 ≥5 次，每次记录 TRIGGER 与录像开始/结束时间戳 |
| `longrun_YYYYMMDD.log` | 系统连续运行 | **仍缺**（用 `board/stability_monitor.sh` 采集，注意音频每 31 分钟正常重启会递增 NRestarts） | 后台跑 `stability_monitor.sh --interval 300`，另附期间触发/录像是否正常的抽查记录 |
| `results_av_*/` 内的 JSON | 检测框、录像时长、触发次数 | **仍缺** | 从板上 `runtime/annotated/`、`runtime/videos/` 抽 1–2 个样本连同 JSON 一起拷回 |
| `gemm_e2e_YYYYMMDD.log` + `gemm_bench_YYYYMMDD.log` | GEMM 端到端分数、公平加速比 | **仍缺**（当前只有 `build/gemm/README.md` 里粘贴的一段） | 板上 `sudo python3 e2e_board.py` 与 `--bench 20` 的完整输出重定向到文件 |

## 命名与格式约定

- 文件名：`<主题>_<YYYYMMDD>.log`，全小写英文 + 下划线 + 数字。
- 内容：保留原始终端输出，不删行、不改数字；首行注明日期、命令、板端 IP、使用的 bit 与模型。
- 时间戳：建议命令前缀 `date +"%Y-%m-%d %H:%M:%S"`，或用 `ts` 类工具给每行加时间。

## 回填后要同步的位置

1. `data/comparison.csv`：对应行的"数值 / 测试次数 / 证据文件"改成日志里的真实值与本目录文件名；
2. `README.md` 的"关键性能指标"表：从"待板端实测"移入"已实测"；
3. `report/design_report.md` 第 6 节：同步数值与证据文件名；
4. `skill/verification/board_checklist.md`：勾选已执行项并填结果。
