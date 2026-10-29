#!/bin/bash
# 视觉前台调试脚本（无就绪门）。正式部署用 systemd。
# 用法: sudo bash start_vision.sh
cd /home/xilinx
chmod 666 /dev/video0
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
