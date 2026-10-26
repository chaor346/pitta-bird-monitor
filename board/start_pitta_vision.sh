#!/bin/bash
set -e
cd /home/xilinx
mkdir -p /home/xilinx/runtime/trigger

# 就绪门：等待 USB 摄像头枚举完成（最多 60s），避免开机早期设备未就绪导致反复失败。
for i in $(seq 1 60); do
  if [ -e /dev/video0 ]; then
    echo "[BOOT] 已找到 /dev/video0（第 ${i} 次检查）"
    break
  fi
  sleep 1
done
if [ ! -e /dev/video0 ]; then
  echo "[BOOT] 启动后 60s 内未找到 /dev/video0，放弃启动" >&2
  exit 1
fi

exec /usr/bin/python3 -u \
  /home/xilinx/trigger_board_presence.py \
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
