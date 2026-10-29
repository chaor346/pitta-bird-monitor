# board/test_output/ 板端实测证据

存放 PYNQ-Z2 上真实运行产生的输出，供 `data/comparison.csv` 引用。

## 现有文件

| 文件 | 能证明 | 不能证明 |
|------|--------|---------|
| `end_to_end_20261024.md` | 一次完整联动：音频 score 0.9863 触发、视觉 6 次推理 5.65~6.72 s、录像 37.40 s/187 帧 H.264 | 单次样本，不代表 P50/P99；无 CPU/内存占用 |
| `board_files_20261025.txt` | 板端文件清单（已去 token） | 文件内容本身是否可用 |

## 待补

| 日志 | 覆盖指标 | 采集方式 |
|------|---------|---------|
| `gemm_bench_YYYYMMDD.log` | GEMM 公平加速比 | `sudo python3 e2e_board.py --bench 20` 输出重定向 |
| `longrun_YYYYMMDD.log` | 连续运行时长 | `stability_monitor.sh --interval 300` 挂 ≥8h |
| `infer_latency_YYYYMMDD.log` | 图像推理 P50/P99 | 连续 ≥8 次 `./infer_ncnn <img> 320`，记起止时间 |

文件名格式：`<topic>_<YYYYMMDD>.log`，保留原始终端输出，首行注明命令、板端 IP、bit/模型版本。
