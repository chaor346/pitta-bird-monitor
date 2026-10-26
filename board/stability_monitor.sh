#!/bin/bash
# ============================================================================
# 系统连续运行时长监控（PYNQ-Z2）
# ----------------------------------------------------------------------------
# 每隔一段时间记录两个服务状态、重启次数、内存、负载、磁盘、进程数到 CSV，
# 用于判断"无人工干预下系统能连续稳定运行多久"。
#
# 用法：
#   nohup bash stability_monitor.sh --interval 300 --out stability_log.csv &
#     --interval 采样间隔秒（默认 300 = 5 分钟）
#
# 判定口径：
#   - 连续运行时长 = 两个服务始终 active、**无非预期重启**、可用内存不持续下滑
#     （无泄漏）的累计时间。
#   - 重要：pitta-audio.service 配置为 --seconds 1800 + Restart=always，**每约 31 分钟
#     （1800s 运行 + 20s RestartSec + 启动开销）正常退出并重开新会话**，因此
#     audio_restarts 按这个节奏递增属**正常**，不能当成不稳定。
#     异常判据是：重启间隔明显短于 31 分钟、出现 failed/inactive、或某次重启后
#     长时间不 active。
#   - vision 服务正常应长期不重启（NRestarts 恒为 0），它一旦 >0 就要单独看原因。
#   - 期间建议手动播放几次鸟叫 / 放鸟图，确认仍能正常触发与录像（活性）。
#
# 跑完后看：
#   column -t -s, stability_log.csv
#   若 vision 服务 inactive/failed、vision_restarts >0、audio 重启间隔远小于 31 分钟、
#   或 MemAvailable 持续走低，即为不稳定，取首次异常前的时长作为连续运行时长。
# ============================================================================

INTERVAL=300
OUT="stability_log.csv"
while [ $# -gt 0 ]; do
  case "$1" in
    --interval) INTERVAL="$2"; shift 2 ;;
    --out)      OUT="$2"; shift 2 ;;
    *) echo "未知参数 $1"; exit 1 ;;
  esac
done

# 表头
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
