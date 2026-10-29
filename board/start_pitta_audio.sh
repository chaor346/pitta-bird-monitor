#!/bin/bash
set -e
cd /home/xilinx
mkdir -p /home/xilinx/runtime/trigger
mkdir -p /home/xilinx/runtime/audio_sessions

# 等 PYNQ PL Server 就绪，避免开机期加载 Overlay 冲突
for i in $(seq 1 60); do
  if pgrep -f start_pl_server.py >/dev/null 2>&1; then
    echo "[BOOT] pl_server ready (check ${i})"
    break
  fi
  sleep 1
done
if ! pgrep -f start_pl_server.py >/dev/null 2>&1; then
  echo "[BOOT] pl_server not found, abort" >&2
  exit 1
fi

SESSION_DIR=$(mktemp -d /home/xilinx/runtime/audio_sessions/session_XXXXXXXX)

exec /usr/bin/python3 -u \
  /home/xilinx/inmp441_predict_time.py \
  --model /home/xilinx/audio_model.npz \
  --overlay /home/xilinx/inmp441.bit \
  --threshold 0.9850068688392639 \
  --min-hits 1 \
  --hop 1.5 \
  --cooldown 5 \
  --release-threshold 0.3 \
  --release-hits 2 \
  --seconds 1800 \
  --out "$SESSION_DIR/results" \
  --vision-trigger /home/xilinx/runtime/trigger/pitta.trigger \
  --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock
