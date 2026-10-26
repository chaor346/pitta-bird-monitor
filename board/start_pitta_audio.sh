#!/bin/bash
set -e
cd /home/xilinx
mkdir -p /home/xilinx/runtime/trigger
mkdir -p /home/xilinx/runtime/audio_sessions

# 就绪门：等待 PYNQ PL Server（比特流加载服务）就绪，最多 60s。
# 避免在 PL 未就绪时调用 Overlay() 加载 inmp441.bit，杜绝开机期 FPGA 配置竞争。
for i in $(seq 1 60); do
  if pgrep -f start_pl_server.py >/dev/null 2>&1; then
    echo "[BOOT] pl_server 已就绪（第 ${i} 次检查）"
    break
  fi
  sleep 1
done
if ! pgrep -f start_pl_server.py >/dev/null 2>&1; then
  echo "[BOOT] 未检测到 pl_server，放弃启动，避免在 PL 未就绪时加载 Overlay" >&2
  exit 1
fi

# 每次（重新）启动服务生成唯一会话目录，避免重启后与旧结果重名。
# results 目录由音频程序自己创建，这里不要提前创建。
SESSION_DIR=$(mktemp -d /home/xilinx/runtime/audio_sessions/session_XXXXXXXX)

# 音频用 inmp441_predict_time.py：包含“录像期间暂停音频”联动，并额外记录鸟鸣北京时间。
# 若要换回不含时间记录的版本，把下一行文件改成 inmp441_predict_pause.py 即可。
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
