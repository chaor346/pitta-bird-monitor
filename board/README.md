# board/ 板端脚本与实测证据

本目录所有脚本都以 `/home/xilinx` 为工作目录、要求 `root` 运行（加载 bit 需要）。
**只有 systemd 那一套是正式部署**，其余为手动调试或工具脚本。

## 正式部署（systemd，开机自启 + 崩溃拉起）

| 文件 | 作用 |
|------|------|
| `pitta-audio.service` | 音频检测服务。`Requires=pl_server.service`、`After=… pitta-vision.service`、`Restart=always`、`RestartSec=20`、`KillSignal=SIGINT`、`StartLimitBurst=3/120s` |
| `pitta-vision.service` | 图像识别 + 存在性录像服务。`Restart=always`、`RestartSec=15`、启动前 sleep 20 s |
| `start_pitta_audio.sh` | 音频服务入口：等 `start_pl_server.py` 就绪（≤60 s）→ 建独立会话目录 → `exec inmp441_predict_time.py --threshold 0.9850068688392639 --min-hits 1 --hop 1.5 --cooldown 5 --release-threshold 0.3 --release-hits 2 --seconds 1800` |
| `start_pitta_vision.sh` | 图像服务入口：等 `/dev/video0`（≤60 s）→ `trigger_board_presence.py --width 640 --height 480 --fps 5 --detect-hz 0.2 --search-sec 30 --record-fps 5 --absence-hits 3 --absence-sec 6 --vision-timeout 60` |

安装与查看：

```bash
sudo cp board/pitta-audio.service board/pitta-vision.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pitta-vision pitta-audio
journalctl -u pitta-audio -u pitta-vision -f
```

> 音频服务每 1800 s 正常退出并由 `Restart=always` 重开新会话，这是设计行为；
> 判断稳定性时不要把它的 `NRestarts` 递增当成故障（见 `stability_monitor.sh` 里的口径说明）。

## 手动调试（旧脚本，仅演示/排障用）

| 文件 | 与正式版的差别 |
|------|----------------|
| `start_audio.sh` | 阈值 **0.5**（正式 0.985）、跑 **600 s** 即退出、无就绪门、无会话目录、输出到 `results_av/` |
| `start_vision.sh` | 参数与正式版一致，但没有 `/dev/video0` 就绪门与开机保护 |

两者都直接 `sudo python3 …` 前台运行，适合接线刚调通时逐段验证，不适合长时间无人值守。

## 环境与工具

| 文件 | 作用 |
|------|------|
| `setup.sh` | 一键装依赖（ffmpeg/v4l-utils/opencv）、建 `runtime/` 目录、`chmod 666 /dev/video0`、编译 `infer_ncnn` |
| `verify_gemm.sh` | GEMM overlay 版本自检：只读 MD5/大小/`C_SG_LENGTH_WIDTH`，不加载硬件；接受"10-25 板端实测版"和"10-26 仓库重建版"两个已知版本 |
| `stability_monitor.sh` | 连续运行监控：每 N 秒把两个服务的 `is-active`/`NRestarts`、内存、负载、磁盘、进程数写进 CSV |

`stability_monitor.sh` 用法：

```bash
sudo systemctl start pitta-vision pitta-audio
nohup bash stability_monitor.sh --interval 300 --out stability_log.csv &
column -t -s, stability_log.csv
```

## test_output/ 实测证据

只放**板端真实运行**的输出，`data/comparison.csv` 的证据列指向这里：

- `end_to_end_20261024.md` —— 一次完整联动的原始 journalctl + 时间线（音频 0.9863 触发、
  视觉 6 次推理 5.65~6.72 s、录像 37.40 s/187 帧）；
- `board_files_20261025.txt` —— 板端 Jupyter 文件清单（已去 token），只能证明文件存在；
- 该目录 `README.md` 写明每个文件"能证明/不能证明什么"，以及还缺哪几类日志。
