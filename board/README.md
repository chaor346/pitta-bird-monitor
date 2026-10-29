# board/ 板端脚本

所有脚本以 `/home/xilinx` 为工作目录，加载 bit 需要 root。

## 正式部署（systemd 开机自启）

| 文件 | 作用 |
|------|------|
| `pitta-vision.service` | 图像识别 + 存在性录像。`Restart=always`，启动前 sleep 20s |
| `pitta-audio.service` | 鸟鸣检测。`Restart=always`，每 1800s 正常退出后重开新会话 |
| `start_pitta_vision.sh` | 视觉入口：等 `/dev/video0` → `trigger_board_presence.py` |
| `start_pitta_audio.sh` | 音频入口：等 `pl_server` → `inmp441_predict_time.py --threshold 0.985` |

安装：

```bash
sudo cp board/pitta-vision.service board/pitta-audio.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pitta-vision pitta-audio
journalctl -u pitta-audio -u pitta-vision -f
```

两个 unit 都 `Requires=pl_server.service`（PYNQ 镜像自带）。

## 手动调试

| 文件 | 说明 |
|------|------|
| `start_vision.sh` | 视觉前台运行，无就绪门，适合接线时验证 |
| `start_audio.sh` | 音频前台运行，阈值 0.5、跑 600s 即退 |

## 工具脚本

| 文件 | 作用 |
|------|------|
| `setup.sh` | 装 ffmpeg/v4l-utils/opencv、建 `runtime/`、编译 `infer_ncnn` |
| `verify_gemm.sh` | 校验 GEMM bit/hwh 的 MD5 与 `C_SG_LENGTH_WIDTH`，不加载硬件 |
| `stability_monitor.sh` | 定时记录服务状态/内存/负载到 CSV |

```bash
nohup bash stability_monitor.sh --interval 300 --out stability_log.csv &
column -t -s, stability_log.csv
```

## test_output/

板端真实运行日志，见该目录 README。
