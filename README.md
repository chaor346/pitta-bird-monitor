# 浠欏叓鑹查斧楦ｅ０涓庡浘鍍忓崗鍚岀洃娴嬬郴缁?
鍩轰簬 PYNQ-Z2 (Zynq-7000 XC7Z020) 鐨勬繏鍗遍笩绫昏嚜鍔ㄥ寲鐩戞祴绯荤粺銆?閫氳繃 FPGA 纭欢闊抽閲囬泦 + ARM 绔?AI 鎺ㄧ悊锛屽疄鐜伴笩楦ｈЕ鍙戙€佸浘鍍忚瘑鍒笌鐩爣瀛樺湪鎬у綍鍍忕殑瀹屾暣闂幆銆?
## 绯荤粺鍔熻兘

1. **FPGA 闊抽閲囬泦**锛欼NMP441 MEMS 楹﹀厠椋?鈫?I2S 鎺ユ敹鏍?鈫?AXI DMA 鈫?DDR锛?2000Hz 閲囨牱锛?4bit 绮惧害
2. **楦熼福妫€娴?*锛? 灞?CNN锛? 绉掓粦鍔ㄧ獥鍙ｏ紝妫€娴嬪埌楦熼福鍐欒Е鍙戞枃浠躲€俢onv1锛?脳3, 16 閫氶亾锛夊凡鍋?PL HLS GEMM 鏍搁獙璇侊紙M=12864 K=9 N=16, Q12 瀹氱偣锛岀嫭绔?overlay `gemm_soc.bit`锛岀鍒扮鍒嗘暟涓庢诞鐐逛竴鑷达級锛?*姝ｅ紡杩愯鐨勯煶棰戜富绋嬪簭浠嶄负 numpy 鍏ㄨ蒋浠跺疄鐜?*锛屼袱涓?overlay 鍒嗘椂鍔犺浇
3. **澹伴煶瑙﹀彂鍥惧儚**锛氬浘鍍忕妫€娴嬭Е鍙戞枃浠?鈫?杩涘叆鎼滅储鐘舵€?鈫?YOLOv8n (ncnn) 璇嗗埆浠欏叓鑹查斧
4. **鐩爣瀛樺湪鎬у綍鍍?*锛氭娴嬪埌楦熷紑濮嬪綍鍍忥紝楦熸秷澶卞悗寤惰繜缁撴潫锛屽綍鍍忔湡闂存殏鍋滈煶棰戞帹鐞嗛伩鍏?CPU 浜夋姠

## 纭欢娓呭崟

| 鍣ㄤ欢 | 鍨嬪彿 | 鎺ュ彛 |
|------|------|------|
| FPGA 寮€鍙戞澘 | PYNQ-Z2 (XC7Z020CLG400-1) | - |
| MEMS 楹﹀厠椋?| INMP441 | PMOD B (I2S) |
| USB 鎽勫儚澶?| 1080p USB UVC | /dev/video0 |

## 鐩綍缁撴瀯

```
pitta_bird_monitor/
鈹溾攢鈹€ README.md
鈹溾攢鈹€ LICENSE
鈹溾攢鈹€ .gitignore
鈹溾攢鈹€ docs/                  # 鏋舵瀯銆佹帴鍙ｃ€佺‖浠舵帴绾?鈹?  鈹溾攢鈹€ architecture.md
鈹?  鈹溾攢鈹€ interface.md
鈹?  鈹斺攢鈹€ hardware_setup.md
鈹溾攢鈹€ src/
鈹?  鈹溾攢鈹€ fpga/              # I2S 鎺ユ敹鏍?RTL + GEMM HLS IP
鈹?  鈹?  鈹溾攢鈹€ i2s_mems_rx.v
鈹?  鈹?  鈹溾攢鈹€ inmp441_pmodb.xdc
鈹?  鈹?  鈹溾攢鈹€ system_wrapper.v
鈹?  鈹?  鈹斺攢鈹€ gemm/          # HLS 鐢熸垚鐨?IP 鏍?鈹?  鈹斺攢鈹€ ps/                # 鏉跨 Python + 妯″瀷 + PC 璁粌鑴氭湰
鈹溾攢鈹€ sim/                   # I2S 鎺ユ敹鏍?testbench
鈹溾攢鈹€ build/                 # Vivado 鏋勫缓鑴氭湰 + bit/hwh + 鎶ュ憡
鈹?  鈹溾攢鈹€ build.tcl
鈹?  鈹溾攢鈹€ build_gemm.tcl
鈹?  鈹溾攢鈹€ inmp441.bit / .hwh
鈹?  鈹溾攢鈹€ utilization/timing/power.rpt
鈹?  鈹溾攢鈹€ drc_routed.rpt
鈹?  鈹溾攢鈹€ vivado_project.zip
鈹?  鈹斺攢鈹€ gemm/              # GEMM overlay
鈹溾攢鈹€ board/                 # 涓婃澘鑴氭湰 + 瀹炴祴鏃ュ織
鈹溾攢鈹€ data/                  # 娴嬭瘯鏁版嵁 + 鎸囨爣姹囨€?鈹溾攢鈹€ skill/                 # PYNQ 楠岃瘉鎶€鑳藉寘
鈹斺攢鈹€ report/                # 璁捐鎶ュ憡 + 娴锋姤
```

## 澶嶇幇姝ラ

### 1. 纭欢杩炴帴

- INMP441 鈫?PMOD B锛歏DD鈫扨in6(3V3), GND鈫扨in5, SCK鈫扨in1(W14), WS鈫扨in2(Y14), SD鈫扨in3(T11), L/R鈫扨in5(GND)
- USB 鎽勫儚澶?鈫?鏉垮瓙 USB 鍙?
### 2. FPGA 鏋勫缓锛堝彲閫夛紝bit 宸叉彁渚涳級

```bash
# 鍦?PC 涓婄敤 Vivado 2026.1
vivado -mode batch -source build/build.tcl
# 浜у嚭 inmp441.bit 鍜?inmp441.hwh
```

### 3. 鏉跨閮ㄧ讲

```bash
# 涓婁紶鏂囦欢鍒?PYNQ-Z2锛堝彧鎷?A 绫昏繍琛屾枃浠讹紝鍘嗗彶鐗堟湰涓嶅繀鎷凤紝瑙?src/ps/README.md锛?scp build/inmp441.bit build/inmp441.hwh xilinx@192.168.2.99:/home/xilinx/
scp src/ps/inmp441_predict_time.py src/ps/inmp441_predict_pause.py \
    src/ps/trigger_board_presence.py src/ps/inmp441_record.py \
    src/ps/av_recording_lock.py src/ps/audio_numpy.py \
    src/ps/infer_ncnn.cpp xilinx@192.168.2.99:/home/xilinx/
scp src/ps/best_ncnn.param src/ps/best_ncnn.bin \
    src/ps/audio_model.npz src/ps/mel_basis.npy xilinx@192.168.2.99:/home/xilinx/
scp board/*.sh board/*.service xilinx@192.168.2.99:/home/xilinx/

# SSH 鍒版澘瀛?ssh xilinx@192.168.2.99

# 閰嶇疆鐜锛堜緷璧?+ runtime 鐩綍 + 鎽勫儚澶存潈闄?+ 缂栬瘧 infer_ncnn锛?sudo bash /home/xilinx/setup.sh
```

> `setup.sh` 宸插寘鍚?`infer_ncnn` 鐨勭紪璇戯紝涓嶅繀鍐嶆墜宸?`g++`銆?
### 4. 杩愯

涓ょ鏂瑰紡浜岄€変竴锛?*鎵嬪姩璋冭瘯**锛堜笅闈㈢粓绔?1/2锛岄槇鍊?0.5锛夋垨 **systemd 姝ｅ紡閮ㄧ讲**
锛坄board/pitta-audio.service` + `board/pitta-vision.service`锛岄槇鍊?0.85銆侀煶棰戞瘡 1800 s
鑷姩鎹細璇濓級銆備袱鑰呭弬鏁颁笉鍚岋紝鎶ュ憡閲岀殑瀹炴祴鏁板瓧鍧囨潵鑷?systemd 姝ｅ紡閮ㄧ讲銆?
```bash
# 姝ｅ紡閮ㄧ讲锛堟帹鑽愶紝寮€鏈鸿嚜鍚?+ 宕╂簝鎷夎捣锛?sudo cp board/pitta-audio.service board/pitta-vision.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now pitta-vision pitta-audio
journalctl -u pitta-audio -u pitta-vision -f
```

```bash
# 缁堢1锛氶煶棰戞娴嬶紙璋冭瘯鍙傛暟锛岀瓑浠蜂簬 bash start_audio.sh锛?sudo python3 -u inmp441_predict_pause.py \
  --model audio_model.npz --overlay inmp441.bit \
  --threshold 0.5 --min-hits 1 \
  --hop 1.5 --cooldown 5 \
  --release-threshold 0.3 --release-hits 2 \
  --seconds 600 --out results_av \
  --vision-trigger /home/xilinx/runtime/trigger/pitta.trigger \
  --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock

# 缁堢2锛氬浘鍍忚瘑鍒?+ 瀛樺湪鎬у綍鍍忥紙绛変环浜?bash start_vision.sh锛?sudo chmod 666 /dev/video0
sudo python3 -u trigger_board_presence.py \
  --width 640 --height 480 --fps 5 --detect-hz 0.2 \
  --search-sec 30 --record-fps 5 \
  --absence-hits 3 --absence-sec 6 --vision-timeout 60 \
  --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock
```

### 4.5 GEMM 绔埌绔獙璇侊紙conv1 纭欢鍔犻€燂級

conv1 璧?PL HLS GEMM 鏍哥殑绔埌绔獙璇侊紝涓嶄緷璧栨憚鍍忓ご/楹﹀厠椋庯紝鐢ㄥ綍濂界殑 wav 鍗冲彲銆?浠撳簱閲屾枃浠舵寜瑙勮寖鍒嗘暎瀛樻斁锛屾澘绔儴缃叉椂闇€鏀堕泦鍒板悓涓€鐩綍锛?
```bash
# 鍦?PC 涓婃妸鍒嗘暎鐨?GEMM 鏂囦欢鏀堕泦鍒版澘绔?/home/xilinx/gemm/
ssh xilinx@192.168.2.99 'mkdir -p /home/xilinx/gemm'
scp build/gemm/gemm_soc.bit build/gemm/gemm_soc.hwh  xilinx@192.168.2.99:/home/xilinx/gemm/
scp src/ps/e2e_board.py src/ps/gemm_board.py       xilinx@192.168.2.99:/home/xilinx/gemm/
scp data/gemm/*                                      xilinx@192.168.2.99:/home/xilinx/gemm/
scp src/ps/audio_model.npz                           xilinx@192.168.2.99:/home/xilinx/gemm/
scp board/verify_gemm.sh                             xilinx@192.168.2.99:/home/xilinx/gemm/

# 鏉跨鑷鏂囦欢鐗堟湰
cd /home/xilinx/gemm
bash verify_gemm.sh

# 绔埌绔細wav 鈫?numpy 鐗瑰緛 鈫?纭欢 conv1 鈫?numpy 鍏朵綑灞?鈫?鍒嗘暟
sudo python3 e2e_board.py
sudo python3 e2e_board.py --repeat 5    # 閲嶅 5 娆℃祴绋冲畾鑰楁椂
```

棰勬湡杈撳嚭锛氱‖浠?conv1 鍒嗘暟 鈮?0.9979锛宯umpy 鍏ㄦ诞鐐?鈮?0.9979锛?conv1 鏈€澶ц宸?< 0.02锛?05824 鐐?0 瓒呭樊锛夛紝鍒ゅ畾 PASS銆?璇﹁ `build/gemm/README.md`銆?
### 5. 娴嬭瘯

鎾斁楦熼福澹伴煶 鈫?缁堢1杈撳嚭 `TRIGGER` 鈫?缁堢2杈撳嚭 `鏀跺埌澹伴煶瑙﹀彂锛屽紑濮嬫悳楦焋 鈫?妫€娴嬪埌楦?鈫?寮€濮嬪綍鍍?鈫?楦熸秷澶卞悗寤惰繜缁撴潫 鈫?鍥炲埌绛夊緟銆?
### 6. 杩愯浜х墿钀界偣锛堢畝浠嬫墍璇寸殑"鐓х墖銆佽棰戜笌棰勬祴鏃ュ織"锛?
鏉跨 `~/runtime/` 涓嬶細

| 鐩綍 | 鍐呭 |
|------|------|
| `runtime/annotated/` | `frame_*.jpg` 鎶撴媿蹇収 + `frame_*.json` 棰勬祴鏃ュ織锛堟椂闂存埑銆佸抚搴忓彿銆佹鍧愭爣銆佺疆淇″害銆佹帹鐞嗚€楁椂锛?|
| `runtime/videos/` | 鐩爣瀛樺湪鏈熼棿鐨?MP4 褰曞儚 |
| `runtime/trigger/` | 闊抽瑙﹀彂鏂囦欢 `pitta.trigger`銆佸綍鍍忛攣 `vision_recording.lock` |

### 7. 鎵╁睍鍒板叾浠栭笩绫?
杞‖浠舵祦绋嬩笌鐗╃鏃犲叧锛屾崲鐗╃鍙渶鏇挎崲鏁版嵁涓庢ā鍨嬶細

1. **闊抽绔?*锛氶噰闆嗘柊鐗╃楦ｅ０姝ｆ牱鏈?+ 鏈湴鐜璐熸牱鏈紝閲嶈窇 `train_binary_fixed.py`锛屾浛鎹?`audio_model.npz`锛?2. **瑙嗚绔?*锛氭寜 `pitta.yaml` 鐨勬爣娉ㄦ牸寮忛噰闆嗘柊鐗╃鍥剧墖锛岄噸璺?`03_train.py` 璁粌 + `04_export.py` 瀵煎嚭 ncnn锛屾浛鎹?`best_ncnn.param/bin`锛?3. 璋冩暣閮ㄧ讲闃堝€硷紙褰撳墠闊抽 0.85 / 瑙嗚 conf 0.52锛夊嵆鍙紝閲囬泦鏍搞€両2S銆丏MA銆佸綍鍍忕姸鎬佹満鍏ㄩ儴澶嶇敤銆?
## FPGA 璧勬簮鍗犵敤

| 璧勬簮 | 鍗犵敤 | 鍙敤 | 鍒╃敤鐜?|
|------|------|------|--------|
| Slice LUTs | 1675 | 53200 | 3.15% |
| Slice Registers | 2281 | 106400 | 2.14% |
| Block RAM Tile | 1 | 140 | 0.71% |
| DSP48 | 0 | 220 | 0% |

鏃堕挓棰戠巼锛?00MHz (FCLK0)锛屾椂搴忔敹鏁涖€?
涓婅〃鏄?*闊抽 overlay**锛坄inmp441.bit`锛夈€侴EMM overlay锛坄gemm_soc.bit`锛夊崟鐙竴缁勶細
LUT 5376 (10.11%) / FF 7505 (7.05%) / BRAM 11 (7.86%) / DSP 67 (30.45%)锛學NS +1.520 ns锛?鍔熻€椾及绠?1.741 W锛坈onfidence Medium锛夈€備袱鑰呭垎鏃跺姞杞斤紝涓嶅悓鏃跺崰鏉裤€?
## 鍏抽敭鎬ц兘鎸囨爣

**宸插疄娴嬶紙PC 绔绾挎帹鐞?+ FPGA 鎶ュ憡锛夛細**

| 鎸囨爣 | 鏁板€?| 璇存槑 |
|------|------|------|
| 闊抽閲囨牱鐜?| 32000 Hz | FPGA DMA 杩炵画閲囬泦 |
| 闊抽绐楀彛绾х壒寮傛€?| 100% | 鏈洰褰?18 娈佃礋鏍锋湰 2,063 涓獥鍙?0 璇姤锛屾渶楂樺垎 0.0329锛堥潪鎬讳綋鐗瑰紓鎬э級 |
| 闊抽浜嬩欢绾у彫鍥炵巼 | 97.4%锛?.985锛? 98.1%锛?.5锛?| 9 娈垫鏍锋湰銆?55 涓汉鑰虫牳瀵逛簨浠讹紙`events_truth.csv`锛夛紱4 澶勬紡妫€涓?2 澶勫湪 `xc188359`锛涚獥鍙ｇ骇 90.6%/95.4%锛岃 `data/test_audio/positive/recall_results/` |
| 鍥惧儚妫€鍑虹巼 | 99.2% | raw_pitta 鏈夋爣娉?1,061 寮犳鍑?1,052 寮狅紙璁粌姹犲彛寰勶紝conf 0.52锛?|
| 鍥惧儚鐗瑰紓鎬?| 380/380 | data/neg 380 寮狅紙321 鍏朵粬楦?+ 59 绾儗鏅級0 璇姤锛堝凡瑙佽礋鏍锋湰鍙ｅ緞锛?|
| 鍥惧儚 mAP@0.5 | 86.7% | images/val 鏈夋爣娉?220 寮?/ 251 妗嗭紱val 涓庤缁冮泦鍚屾簮锛屽睘璁粌姹犲彛寰?|
| 鍥惧儚鏉跨鎺ㄧ悊寤惰繜 | 5.65~6.72 s | ncnn YOLOv8n 320脳320 鍙屾牳锛涚鍒扮鑱斿姩鏃ュ織 6 娆?RECORD-INFER 鎶芥牱锛堝潎鍊?6.17 s锛夛紝瑙?`board/test_output/end_to_end_20261024.md` |
| 闊抽鏉跨鎺ㄧ悊寤惰繜 | 2.075 s | 鍗曟绐楀彛鎺ㄧ悊锛堝惈 STFT/mel/conv/numpy锛夛紝鍚屼竴浠借仈鍔ㄦ棩蹇?|
| 绔埌绔Е鍙戝欢杩?| 绾?10.5 s | 楦熼福 TRIGGER 鈫?妫€娴嬪埌楦熷紑濮嬪綍鍍忥紙22:18:26.9 鈫?22:18:37锛岀绾ф椂闂存埑锛?|
| **conv1 GEMM HLS 鏍歌€楁椂** | **6.7 ms** | PYNQ-Z2 @100 MHz锛岀函鏍?ap_start鈫抋p_done锛沗--bench 20` 涓綅鏁?|
| **conv1 鍏钩鍔犻€熸瘮** | **0.59x锛堢鍒扮锛? 4.64x锛堢函鏍革級** | 绔埌绔?52.7ms锛圖MA鎼繍+GEMM+鍙嶉噺鍖栵級vs numpy conv1 31.0ms锛涙惉杩愬紑閿€鍚冩帀鏀剁泭锛屾晠姝ｅ紡闊抽涓荤▼搴忎粛璧?numpy |
| **conv1 纭欢 vs numpy 鏈€澶ц宸?* | **0.001838** | 205824 鐐归€愮偣锛屽宸?0.02 涓?0 鐐硅秴宸紱绔埌绔垎鏁?0.997878 vs 0.997876 |
| 闊抽 overlay 璧勬簮 LUT/FF/BRAM/DSP | 3.15% / 2.14% / 0.71% / 0% | inmp441.bit锛學NS +2.029ns锛屽姛鑰?1.684 W锛坈onfidence Low锛?|
| GEMM overlay 璧勬簮 LUT/FF/BRAM/DSP | 10.11% / 7.05% / 7.86% / 30.45% | gemm_soc.bit锛學NS +1.520ns锛屽姛鑰?1.741 W锛坈onfidence Medium锛?|

> **鍥惧儚鎸囨爣鍙ｅ緞**锛氳缁冩睜 mAP@0.5 86.7% 涓鸿缁冨垎甯冨唴鎸囨爣銆傜湡姝ｇ嫭绔嬶紙涓庤缁冮泦 MD5 鏃犻噸澶嶏級
> 鐨?266 寮犵綉缁滃叕寮€娴嬭瘯鍥句笂锛屾澘绔槇鍊?conf 0.52 涓嬪浘鍍忕骇鍙洖 **256/266 = 96.2%**锛?> 妫€鍑虹疆淇″害鍧囧€?0.91銆傝瑙?`data/test_images/independent/README.md`銆?
**寰呮澘绔疄娴嬶細** 杩炵画杩愯鏃堕暱锛坄stability_monitor.sh --interval 300` 鎸?鈮?h锛夈€侴EMM 鍏钩鍔犻€熸瘮宸叉祴锛?.59x 绔埌绔?/ 4.64x 绾牳锛夛紝鍥惧儚鎺ㄧ悊寤惰繜宸叉湁 6 娆℃娊鏍凤紙鍧囧€?6.2s锛夈€傝瑙?`data/comparison.csv`銆?
## 璁稿彲璇?
MIT License锛屽叏鏂囪浠撳簱鏍圭洰褰?`LICENSE`銆傜涓夋柟缁勪欢锛圥YNQ銆乶cnn銆丱penCV銆乫fmpeg銆?Ultralytics YOLOv8锛夐伒寰悇鑷鍙瘉锛屾湭鍦ㄦ湰浠撳簱鍐呴噸鏂板垎鍙戙€?