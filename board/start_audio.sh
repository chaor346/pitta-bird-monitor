#!/bin/bash
# 音频检测端启动脚本（**历史手动调试版**：阈值 0.5、跑 600 s 即退出）
# 正式部署请用 systemd：board/pitta-audio.service → board/start_pitta_audio.sh
# （阈值 0.985、min-hits 1、每 1800 s 换会话、带就绪门与会话目录）
# 用法: sudo bash start_audio.sh

cd /home/xilinx

echo "=== 启动音频检测 ==="
echo "模型: audio_model.npz | 阈值: 0.5 | 窗口: 2s | hop: 1.5s"
echo "触发文件: /home/xilinx/runtime/trigger/pitta.trigger"
echo "录像锁: /home/xilinx/runtime/trigger/vision_recording.lock"
echo ""

sudo python3 -u inmp441_predict_pause.py \
    --model audio_model.npz \
    --overlay inmp441.bit \
    --threshold 0.5 \
    --min-hits 1 \
    --hop 1.5 \
    --cooldown 5 \
    --release-threshold 0.3 \
    --release-hits 2 \
    --seconds 600 \
    --out results_av \
    --vision-trigger /home/xilinx/runtime/trigger/pitta.trigger \
    --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock
