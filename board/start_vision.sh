#!/bin/bash
# 图像识别 + 存在性录像启动脚本（**历史手动调试版**，无开机就绪门）
# 正式部署请用 systemd：board/pitta-vision.service → board/start_pitta_vision.sh
# 用法: sudo bash start_vision.sh

cd /home/xilinx

echo "=== 启动图像识别 + 存在性录像 ==="
echo "摄像头: 640x480 @5fps | 推理: detect-hz=0.2 | 搜索窗口: 30s"
echo "录像: 目标存在性持续录像 | absence-hits=3 | absence-sec=6"
echo "录像锁: /home/xilinx/runtime/trigger/vision_recording.lock"
echo ""

# 摄像头权限
sudo chmod 666 /dev/video0

sudo python3 -u trigger_board_presence.py \
    --width 640 \
    --height 480 \
    --fps 5 \
    --detect-hz 0.2 \
    --search-sec 30 \
    --record-fps 5 \
    --absence-hits 3 \
    --absence-sec 6 \
    --vision-timeout 60 \
    --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock
