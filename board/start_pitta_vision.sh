#!/bin/bash
set -e
cd /home/xilinx
mkdir -p /home/xilinx/runtime/trigger

# 等 USB 摄像头枚举完成
for i in $(seq 1 60); do
  if [ -e /dev/video0 ]; then
    echo "[BOOT] /dev/video0 ready (check ${i})"
    break
  fi
  sleep 1
done
if [ ! -e /dev/video0 ]; then
  echo "[BOOT] /dev/video0 not found within 60s, abort" >&2
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
