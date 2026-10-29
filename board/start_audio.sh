#!/bin/bash
# 音频前台调试脚本（阈值 0.5，跑 600s 即退）。正式部署用 systemd。
# 用法: sudo bash start_audio.sh
cd /home/xilinx
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
