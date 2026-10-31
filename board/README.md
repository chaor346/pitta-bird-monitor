# board/ 鏉跨鑴氭湰

鎵€鏈夎剼鏈互 `/home/xilinx` 涓哄伐浣滅洰褰曪紝鍔犺浇 bit 闇€瑕?root銆?
## 姝ｅ紡閮ㄧ讲锛坰ystemd 寮€鏈鸿嚜鍚級

| 鏂囦欢 | 浣滅敤 |
|------|------|
| `pitta-vision.service` | 鍥惧儚璇嗗埆 + 瀛樺湪鎬у綍鍍忋€俙Restart=always`锛屽惎鍔ㄥ墠 sleep 20s |
| `pitta-audio.service` | 楦熼福妫€娴嬨€俙Restart=always`锛屾瘡 1800s 姝ｅ父閫€鍑哄悗閲嶅紑鏂颁細璇?|
| `start_pitta_vision.sh` | 瑙嗚鍏ュ彛锛氱瓑 `/dev/video0` 鈫?`trigger_board_presence.py` |
| `start_pitta_audio.sh` | 闊抽鍏ュ彛锛氱瓑 `pl_server` 鈫?`inmp441_predict_time.py --threshold 0.85` |

瀹夎锛?
```bash
sudo cp board/pitta-vision.service board/pitta-audio.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now pitta-vision pitta-audio
journalctl -u pitta-audio -u pitta-vision -f
```

涓や釜 unit 閮?`Requires=pl_server.service`锛圥YNQ 闀滃儚鑷甫锛夈€?
## 鎵嬪姩璋冭瘯

| 鏂囦欢 | 璇存槑 |
|------|------|
| `start_vision.sh` | 瑙嗚鍓嶅彴杩愯锛屾棤灏辩华闂紝閫傚悎鎺ョ嚎鏃堕獙璇?|
| `start_audio.sh` | 闊抽鍓嶅彴杩愯锛岄槇鍊?0.5銆佽窇 600s 鍗抽€€ |

## 宸ュ叿鑴氭湰

| 鏂囦欢 | 浣滅敤 |
|------|------|
| `setup.sh` | 瑁?ffmpeg/v4l-utils/opencv銆佸缓 `runtime/`銆佺紪璇?`infer_ncnn` |
| `verify_gemm.sh` | 鏍￠獙 GEMM bit/hwh 鐨?MD5 涓?`C_SG_LENGTH_WIDTH`锛屼笉鍔犺浇纭欢 |
| `stability_monitor.sh` | 瀹氭椂璁板綍鏈嶅姟鐘舵€?鍐呭瓨/璐熻浇鍒?CSV |

```bash
nohup bash stability_monitor.sh --interval 300 --out stability_log.csv &
column -t -s, stability_log.csv
```

## test_output/

鏉跨鐪熷疄杩愯鏃ュ織锛岃璇ョ洰褰?README銆?