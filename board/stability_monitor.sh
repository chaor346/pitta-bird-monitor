#!/bin/bash
# 连续运行监控：定时记录两个服务状态/重启次数/内存/负载/磁盘到 CSV。
#
# 用法：
#   nohup bash stability_monitor.sh --interval 300 --out stability_log.csv &
#
# 注意：pitta-audio 每 1800s 正常退出后由 systemd 重启（约 31 分钟一轮），
#       audio_restarts 按此节奏递增属正常；异常判据是重启间隔明显短于 31 分钟、
#       出现 failed/inactive、或 vision_restarts > 0。

INTERVAL=300
OUT="stability_log.csv"
while [ $# -gt 0 ]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --out)      OUT="$2"; shift 2 ;;
    *) echo "unknown arg: $1"; exit 1 ;;
  esac
done

echo "timestamp,uptime_sec,vision_active,audio_active,vision_restarts,audio_restarts,mem_total_kb,mem_available_kb,load1,load5,load15,root_used_pct,procs" > "$OUT"

while true; do
  TS="$(date '+%Y-%m-%d %H:%M:%S')"
  UP="$(awk '{print $1}' /proc/uptime)"
  VIS="$(systemctl is-active pitta-vision.service 2>/dev/null)"
  AUD="$(systemctl is-active pitta-audio.service 2>/dev/null)"
  VR="$(systemctl show -p NRestarts --value pitta-vision.service 2>/dev/null)"
  AR="$(systemctl show -p NRestarts --value pitta-audio.service 2>/dev/null)"
  MT="$(awk '/MemTotal/{print $2}' /proc/meminfo)"
  MA="$(awk '/MemAvailable/{print $2}' /proc/meminfo)"
  read L1 L5 L15 _ < /proc/loadavg
  DU="$(df / | awk 'NR==2{gsub("%",""); print $5}')"
  PR="$(ps -e --no-headers | wc -l)"
  echo "$TS,$UP,$VIS,$AUD,$VR,$AR,$MT,$MA,$L1,$L5,$L15,$DU,$PR" >> "$OUT"
  sleep "$INTERVAL"
done
