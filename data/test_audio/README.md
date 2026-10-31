# test_audio/ 闊抽娴嬭瘯闆?
**姝ｆ牱鏈細浠欏叓鑹查斧锛圥itta nympha锛夐福澹?9 娈碉紝753.2 s / 1,474 涓?2 s 绐楀彛锛屽懡涓?500 涓€?*
**璐熸牱鏈細鐜闊?10 娈?+ 鍏朵粬楦熼福 8 娈碉紝1,060.0 s / 2,063 涓獥鍙ｅ叏閮ㄦ湭瑙﹀彂锛堣鎶?0锛夈€?*
鏉跨褰曢煶灏氭湭瀵煎叆銆?
## 鍛藉悕瑙勮寖

```
<split>_<class>_<detail>.<ext>
split  : pos锛堟鏍锋湰锛?/ neg锛堣礋鏍锋湰锛?class  : pitta锛堜粰鍏壊楦級 / ambient锛堢幆澧冮煶锛?/ bird锛堝叾浠栭笩楦ｏ級
detail : 鍘熷鏉ユ簮缂栧彿锛圡L鈥?XC鈥︼級鎴栧満鏅悕 / 鐗╃鍚?```

| 鐩綍 | 鍓嶇紑 | 绀轰緥 |
|------|------|------|
| `positive/` | `pos_pitta_nympha_` | `pos_pitta_nympha_xc179391.mp3` |
| `negative/ambient/` | `neg_ambient_` | `neg_ambient_rain_hiss.wav` |
| `negative/other_birds/` | `neg_bird_` | `neg_bird_mycerobas_carnipes.mp3` |

- 鍏ㄩ儴灏忓啓鑻辨枃 + 涓嬪垝绾匡紝鏃犵┖鏍笺€佹棤涓枃锛岀鍚堢珵璧涘浠撳簱璺緞鐨勮姹傘€?- 姣忔闊抽閰嶄袱涓悓鍓嶇紑 CSV锛歚_predictions.csv`锛堥€愮獥锛変笌 `_events.csv`锛堜簨浠讹級锛屾帓搴忔椂鑷姩鑱氬湪涓€璧枫€?- `manifest.csv` 鏄叏鐩綍娓呭崟锛堣矾寰勩€佹爣绛俱€佺被鍒€佹椂闀裤€侀噰鏍风巼銆佸０閬撱€佺獥鍙ｆ暟銆佸悇闃堝€煎懡涓暟銆佷簨浠舵暟銆佸嘲鍊煎垎鏁帮級锛屾敼鍚嶅悗闇€鍚屾鏇存柊銆?- 2026-10-24 缁熶竴杩囦竴娆″懡鍚嶏細姝ｆ牱鏈姞 `pos_` 鍓嶇紑锛岀幆澧冮煶鐢?`neg_env_` 鏀逛负 `neg_ambient_`锛堜笌鐩綍鍚嶄竴鑷达級銆傚彧鏀规枃浠跺悕锛岄煶棰戝唴瀹逛笌 CSV 鏁版嵁鏈彉銆?
## 姝ｆ牱鏈枃浠舵竻鍗?
| 鏂囦欢 | 鍘熷 ID | 鏃堕暱 | 閲囨牱鐜?/ 澹伴亾 | 绐楀彛 | score鈮?.5 | score鈮?.985 | 浜嬩欢 | 宄板€?|
|------|---------|-----:|---------------|-----:|----------:|------------:|-----:|-----:|
| `positive/pos_pitta_nympha_ml341061311.mp3` | ML341061311 | 250.8 s | 48 kHz / 绔嬩綋澹?| 498 | 265 | 183 | 54 | 1.0000 |
| `positive/pos_pitta_nympha_xc1043065.wav` | XC1043065 | 143.0 s | 48 kHz / 鍗曞０閬?| 282 | 156 | 102 | 33 | 1.0000 |
| `positive/pos_pitta_nympha_xc183002.mp3` | XC183002 | 68.8 s | 44.1 kHz / 绔嬩綋澹?| 134 | 61 | 44 | 12 | 1.0000 |
| `positive/pos_pitta_nympha_xc188359.mp3` | XC188359 | 68.8 s | 44.1 kHz / 绔嬩綋澹?| 134 | 47 | 27 | 10 | 0.9998 |
| `positive/pos_pitta_nympha_xc133003.mp3` | XC133003 | 66.7 s | 48 kHz / 绔嬩綋澹?| 130 | 69 | 50 | 15 | 1.0000 |
| `positive/pos_pitta_nympha_xc183003.mp3` | XC183003 | 52.9 s | 44.1 kHz / 绔嬩綋澹?| 102 | 32 | 22 | 6 | 1.0000 |
| `positive/pos_pitta_nympha_xc801745.mp3` | XC801745 | 45.0 s | 44.1 kHz / 鍗曞０閬?| 87 | 41 | 30 | 9 | 1.0000 |
| `positive/pos_pitta_nympha_xc179391.mp3` | XC179391 | 42.9 s | 44.1 kHz / 鍗曞０閬?| 82 | 41 | 34 | 8 | 1.0000 |
| `positive/pos_pitta_nympha_ml659112304.mp3` | ML659112304 | 14.3 s | 48 kHz / 绔嬩綋澹?| 25 | 12 | 8 | 3 | 1.0000 |
| **鍚堣锛? 娈碉級** | 鈥?| **753.2 s** | 鈥?| **1,474** | **724** | **500** | **150** | 鈥?|

姣忔涓や釜缁撴灉鏂囦欢锛堝悓鍚嶅墠缂€锛夛細

- `*_predictions.csv`锛氶€愮獥 `start_sec / end_sec / score / prediction / event_id / rms_dbfs`锛?- `*_events.csv`锛歚event_id / start_sec / end_sec / positive_windows / peak_score`銆?
## 绛涢€夎鍒?
鍘熷鍖?`raw_target.zip` 鍏?15 娈碉紝鍏ㄩ儴涓轰粰鍏壊楦€傛寜涓嬪垪瀹㈣鎸囨爣绛涳紝婊¤冻鍏ㄩ儴 6 鏉℃墠鏀跺綍锛?
| 瑙勫垯 | 闃堝€?|
|------|------|
| 鏃堕暱 | 鈮?10 s |
| 鍓婃尝 | 鏍锋湰缁濆鍊尖墺0.999 鐨勬瘮渚?< 0.1% |
| 鏈簳鍣０锛堝抚 RMS 鐨?10 鍒嗕綅锛?| 鈮?鈭?5 dBFS |
| 鍔ㄦ€佽寖鍥达紙95 鍒嗕綅 鈭?10 鍒嗕綅锛?| 鈮?19 dB |
| 褰曢煶鐢靛钩锛堝抚 RMS 鐨?95 鍒嗕綅锛?| 鈮?鈭?2 dBFS |
| 楦ｅ０甯﹁兘閲忥紙0.2 s 甯у唴 2鈥? kHz 鍗犲搷甯ц兘閲忥級 | 鈮?40% |
| 鐮佺巼 | 鈮?128 kbps锛圵AV 涓嶅彈闄愶級 |

缁撴灉锛? 娈靛叆閫夛紝6 娈垫帓闄ゃ€?
### 鎺掗櫎鐨?6 娈?
| 鍘熷 ID | 鏃堕暱 | 鎺掗櫎鍘熷洜 |
|---------|-----:|----------|
| ML658106733 | 18.2 s | 鍔ㄦ€佽寖鍥?14.9 dB锛?鈥? kHz 鍗?0%锛堜富棰?65 Hz锛夛紝瀹炶川鏄綆棰戝櫔澹?|
| ML659430723 | 124.4 s | 鏈簳 鈭?9.7 dBFS锛堢幆澧冨櫔澹板ぇ锛夛紝鍔ㄦ€佽寖鍥?17.7 dB |
| ML661668457 | 21.4 s | 鍔ㄦ€佽寖鍥?16.0 dB锛屼富棰?1.78 kHz銆?鈥? kHz 鍗?0%锛屾ā鍨嬩粎鍛戒腑 10.3% |
| XC303934 | 46.9 s | 鐢靛钩杩囦綆锛堟渶鍝?鈭?1.7 dBFS锛夛紝鍛戒腑鐜?21.1% |
| XC304043 | 7.1 s | 鏃堕暱涓嶈冻 10 s |
| XC664516 | 11.7 s | 鏃堕暱鍋忕煭锛屼笖鐮佺巼 101 kbps 浣庝簬闃堝€?|

`ML661668457` 姝ゅ墠浣滀负鏍囨敞瀵圭収鏍锋湰瀵煎叆杩囦竴娆★紝杩欐鎸夎鍒欑Щ鍑恒€傚畠涓嶆槸褰曢煶鎹熷潖锛岃€屾槸鍏堕福澹颁富棰戝亸浣庛€佷笉鍦ㄦā鍨嬮€氬甫鍐咃紝鐣欎綔姝ｆ牱鏈細璇鎸囨爣銆傚闇€澶嶆牳鏃ц瘎娴嬶紝鍙敤鍘熷鍖呭崟鐙窇锛?.5 闃堝€间笅涓?8 涓獥鍙?/ 2 涓簨浠讹級銆?
## 璐熸牱鏈竴锛氱幆澧冮煶锛?0 娈碉級

| 鏂囦欢 | 鍦烘櫙 | 鏃堕暱 | 绐楀彛 | 鏈€楂樺垎 |
|------|------|-----:|-----:|-------:|
| `negative/ambient/neg_ambient_ac_hum_office.wav` | 瀹ゅ唴绌鸿皟鍡″０ | 40.0 s | 77 | 0.0003 |
| `negative/ambient/neg_ambient_crowd_babble.wav` | 浜虹兢鍢堟潅 | 60.0 s | 117 | 0.0000 |
| `negative/ambient/neg_ambient_footsteps_pavement.wav` | 浜鸿閬撹剼姝?| 30.0 s | 57 | 0.0064 |
| `negative/ambient/neg_ambient_garden_ambient.wav` | 搴櫌鐜锛堟棤楦燂級 | 60.0 s | 117 | 0.0013 |
| `negative/ambient/neg_ambient_keyboard_typing.wav` | 閿洏鏁插嚮 | 45.0 s | 87 | 0.0002 |
| `negative/ambient/neg_ambient_rain_hiss.wav` | 闆ㄥ０ | 45.0 s | 87 | 0.0000 |
| `negative/ambient/neg_ambient_room_tone.wav` | 鎴块棿搴曞櫔 / 绮夊櫔 | 45.0 s | 87 | 0.0001 |
| `negative/ambient/neg_ambient_traffic_street.wav` | 琛楅亾杞︽祦 | 60.0 s | 117 | 0.0005 |
| `negative/ambient/neg_ambient_wind_gusts.wav` | 闃甸 | 60.0 s | 117 | 0.0004 |
| `negative/ambient/neg_ambient_wind_leaves.wav` | 椋庡惞鏍戝彾 | 40.0 s | 77 | 0.0000 |
| **鍚堣锛?0 娈碉級** | 鈥?| **485.0 s** | **940** | **0.0064** |

- 鍏ㄩ儴涓?32 kHz / 鍗曞０閬?16 bit WAV锛屽彲鐩存帴鎸夋澘绔噰鏍风巼鍠傛ā鍨嬶紝涓嶉渶瑕侀噸閲囨牱锛涘潎涓烘棤楦熼福鐨勭幆澧冪墖娈碉紙`garden_ambient` 鍦ㄥ懡鍚嶄笂宸叉爣娉?no bird锛夈€?- 鎸戦€夋爣鍑嗭細瑕嗙洊 10 绫讳簰涓嶉噸澶嶇殑甯歌璇Е鍙戝満鏅紙绋虫€佸棥澹般€侀洦銆侀銆佹按鍙躲€佽剼姝ャ€佷汉娴併€侀敭鐩樸€佷氦閫氾級锛屾棤鍓婃尝锛屾椂闀?鈮?0 s銆?
## 璐熸牱鏈簩锛氬叾浠栭笩楦ｏ紙8 娈碉級

| 鏂囦欢 | 鐗╃锛堝師濮嬫枃浠跺悕锛?| 鏃堕暱 | 绐楀彛 | 鏈€楂樺垎 |
|------|------|-----:|-----:|-------:|
| `negative/other_birds/neg_bird_carpodacus_sibiricus_ussuriensis.mp3` | Carpodacus sibiricus ussuriensis | 120.1 s | 237 | 0.0329 |
| `negative/other_birds/neg_bird_urocynchramus_pylzowi.mp3` | Urocynchramus pylzowi | 109.1 s | 215 | 0.0031 |
| `negative/other_birds/neg_bird_pterorhinus_waddelli.mp3` | Pterorhinus waddelli | 86.5 s | 170 | 0.0042 |
| `negative/other_birds/neg_bird_cyanoptila_cumatilis.mp3` | Cyanoptila cumatilis | 81.8 s | 160 | 0.0017 |
| `negative/other_birds/neg_bird_carpodacus_subhimachalus.mp3` | Carpodacus subhimachalus | 67.1 s | 131 | 0.0009 |
| `negative/other_birds/neg_bird_mycerobas_carnipes.mp3` | Mycerobas carnipes | 40.8 s | 78 | 0.0024 |
| `negative/other_birds/neg_bird_pyrrhula_erythaca.mp3` | Pyrrhula erythaca | 37.3 s | 71 | 0.0029 |
| `negative/other_birds/neg_bird_agraphospiza_rubescens.mp3` | Agraphospiza rubescens | 32.3 s | 61 | 0.0018 |
| **鍚堣锛? 娈碉級** | 8 涓笉鍚屽睘 / 绉?| **575.0 s** | **1,123** | **0.0329** |

鎸戦€夋爣鍑嗭紙浠庡師濮嬪寘鐨?54 绉嶄腑鍙?8 绉嶏級锛?
| 瑙勫垯 | 闃堝€?|
|------|------|
| 鍔ㄦ€佽寖鍥?| 鈮?27 dB |
| 2鈥? kHz 鑳介噺鍗犲搷甯?| 鈮?44% |
| 鍗曟枃浠朵綋绉?| 鈮?5 MB锛堝師濮嬬爜娴侊紝涓嶈浆鐮侊級 |
| 瑕嗙洊 | 涓嶅悓灞炪€佷笉鍚屼綋鍨嬩笌楦ｅ敱绫诲瀷锛岄伩鍏嶅叏鏄悓涓€绫婚泙褰㈢洰楦ｇ |

**鏈鍏ョ殑 46 绉?*锛氫富鍥犳槸浣撶Н锛堝娈?20鈥?10 MB锛屾渶闀垮崟娈?26 min锛屽叏瀵煎叆浼氳浠撳簱浣撶Н缈绘暟鍊嶏級涓庤川閲忎笉杈炬爣銆傝川閲忔渶宸殑鍑犳涓轰緥锛?
| 鐗╃ | 鏃堕暱 | 涓嶈揪鏍囧師鍥?|
|------|-----:|------------|
| Anthus_hodgsoni_hodgsoni | 44.5 s | 鍔ㄦ€佽寖鍥?4.9 dB锛?鈥? kHz 鍗?4.6%锛屽嚑涔庡叏鏄櫔澹?|
| Ianthocincla_maxima | 33.7 s | 鍔ㄦ€佽寖鍥?3.5 dB锛?鈥? kHz 鍗?3.0% |
| Motacilla_tschutschensis_taivana | 10.5 s | 鍔ㄦ€佽寖鍥?5.6 dB锛?鈥? kHz 鍗?8.2% |
| Carpodacus_davidianus | 41.1 s | 鍔ㄦ€佽寖鍥?17.9 dB锛?鈥? kHz 鍗?4.2% |
| Turdus_hortulorum | 216.0 s | 鍔ㄦ€佽寖鍥?8.3 dB锛?鈥? kHz 鍗?15.8% |
| Prinia_striata | 37.1 s | 鏈簳 鈭?5.6 dBFS 鍋忓惖锛屼笖鏈夊墛娉?|

`Motacilla_tschutschensis_taivana` 姝ｅソ鏄棫璇勬祴 `full_test_fixed_050` 鐨勮礋鏍锋湰涔嬩竴锛堝綋鏃?max_score 0.0006锛夛紝杩欐鍥犺川閲忎笉杈炬爣鏈鍏ワ紱鏃ц瘎娴嬬殑 10 娈佃礋鏍锋湰閲屽彧鏈?`Carpodacus_sibiricus_ussuriensis`銆乣Mycerobas_carnipes`銆乣Pterorhinus_waddelli`銆乣env_rain_hiss` 杩?4 娈佃繘浜嗘湰鐩綍銆?
## 璐熸牱鏈鎶ョ粨鏋?
- 18 娈点€?,063 涓?2 s 绐楀彛锛?*score 鈮?0.5 鐨?0 涓紝score 鈮?0.85 鐨?0 涓紝鍊欓€変簨浠?0 涓?*銆?- 鍏ㄧ洰褰曟渶楂樺垎 0.0329锛坄Carpodacus_sibiricus_ussuriensis`锛夛紝璺?0.5 闃堝€艰繕鏈?15 鍊嶄綑閲忋€?- 涓庢棫 torch 璇勬祴閫愭瀵圭収锛堝悓涓€褰曢煶锛夛細`Mycerobas_carnipes` 0.0028 鈫?0.0024锛宍Pterorhinus_waddelli` 0.0027 鈫?0.0042锛宍Carpodacus_sibiricus_ussuriensis` 0.0209 鈫?0.0329锛宍env_rain_hiss` 0.00002 鈫?0.0000銆傛暟閲忕骇涓€鑷达紝宸紓鏉ヨ嚜 mp3 瑙ｇ爜涓庨噸閲囨牱瀹炵幇銆?- **鍙ｅ緞闄愬埗**锛氳繖鍙鏄?杩?18 娈垫潗鏂欎笂娌℃湁璇姤"锛屼笉鏄€讳綋璇姤鐜囥€傜湡瀹為噹澶栬繕鏈夋槅铏€佽洐绫汇€侀澹伴鍙樸€佽澶囨懇鎿︾瓑鏈鐩栵紝涓?46 绉嶉笩鏈祴銆?
## 鏉ユ簮

- XC 缂栧彿鏉ヨ嚜 Xeno-canto锛坔ttps://xeno-canto.org/<缂栧彿>锛夛紝ML 缂栧彿鏉ヨ嚜 Macaulay Library銆?- 鍘熷鍖咃細`C:\Users\14204\Downloads\raw_target.zip` 鐨?`raw_target/` 鐩綍锛?5 娈碉級锛屽叏閮ㄤ繚鐣欙紝鏈洰褰曞彧鍙?9 娈点€?- 璐熸牱鏈師濮嬪寘锛歚C:\Users\14204\Downloads\raw_negative.zip` 鐨?`raw_negative/` 鐩綍锛?4 涓枃浠讹細10 娈电幆澧冮煶 + 54 绉嶉笩锛夛紝鏈洰褰曞彇 18 涓紝鍏朵綑淇濈暀鍦ㄥ師鍖呫€?- **浣跨敤涓庡啀鍒嗗彂鍓嶈鏍稿姣忔褰曢煶鐨勮鍙潯娆?*锛圶eno-canto 鏉＄洰椤垫爣娉?CC 鍗忚锛夛紝骞跺湪鎶ュ憡/浠撳簱 README 涓敞鏄庢潵婧愮紪鍙枫€?
## 鎺ㄧ悊璁剧疆锛堢敓鎴愪笂杩?CSV 鐨勬潯浠讹級

- 妯″瀷锛歚src/ps/audio_model.npz`锛堢函 numpy 瀹炵幇锛宍src/ps/audio_numpy.py`锛夛紝`sr=32000`銆乣n_fft=1024`銆乣hop=320`銆乣n_mels=64`銆乣mean=-45.12`銆乣std=16.89`锛?- 绐楀彛锛?.0 s / 璺?0.5 s锛涚珛浣撳０鍏堝彇鍙屽０閬撳钩鍧囷紱
- 閲嶉噰鏍凤細44.1/48 kHz 鈫?32 kHz锛孎FT 棰戝煙閲嶉噰鏍凤紙甯﹂檺锛屼笉鍋氫綆閫氳璁★級锛?- 鎺ㄧ悊鏈猴細PC锛宯umpy锛?7 娈靛悎璁＄害 100 s锛?- **`prediction` 鐢ㄦ澘绔儴缃查槇鍊?0.85**锛堝彇鑷?`audio_model.npz`锛夛紱`score鈮?.5` 涓€鍒楁槸涓轰笌鏃㈡湁璇勬祴璁板綍锛坄run_config.json` 涓?`threshold=0.5`锛夊榻愪繚鐣欑殑鍙傝€冨€笺€?
## 涓庢棦鏈夎瘎娴嬬殑瀵圭収

| 褰曢煶 | 鏈 numpy 鎺ㄧ悊锛?.5 闃堝€硷級 | 涓婃 torch 鎺ㄧ悊锛坄runs/full_test_fixed_050`锛?|
|------|---------------------------|---------------------------------------------|
| `XC179391` | 41 涓獥鍙?/ 8 涓簨浠?| 42 涓獥鍙?/ 8 涓€欓€変簨浠?|

涓ゆ鍩烘湰鍚诲悎锛屽樊寮傛潵鑷噸閲囨牱瀹炵幇涓庢ā鍨嬪鍑虹簿搴︺€?
## 缂哄彛

- **姝ｆ牱鏈棤閫愮獥浜哄伐鏍囨敞**锛歚reference_annotations.json` 鍙粰浜?2 娈靛綍闊崇殑鐩爣鍖洪棿锛屾湰鐩綍 9 娈垫鏍锋湰閮芥病鏈夐€愮獥鐪熷€硷紝鍥犳鑳界畻鈥滄鍑虹獥鍙ｆ暟鈥濓紝杩樹笉鑳界畻鍙洖鐜囥€傝绠楁寚鏍囬渶浜哄伐鏍囧嚭姣忔楦ｅ０璧锋銆?- **璐熸牱鏈鐩栨湁闄?*锛氬彧娴嬩簡 8 绉嶉笩 + 10 绫荤幆澧冮煶锛屽師濮嬪寘閲屽彟鏈?46 绉嶅洜浣撶Н/璐ㄩ噺鏈鍏ワ紱鏄嗚櫕銆佽洐绫汇€佽澶囨懇鎿︾瓑鏈鐩栥€?- **鏉跨褰曢煶缂哄け**锛歅YNQ-Z2 涓?INMP441 閲囩殑 32000 Hz 鍘熷绐楀彛锛坄/home/xilinx/results_av/*.wav`锛変粛闇€琛ラ噰锛涙湰鐩綍姝ｆ牱鏈兘鏉ヨ嚜鍏紑褰曢煶锛屼笉鏄澘绔噰闆嗭紙鐜闊宠礋鏍锋湰鏈韩鏄?32 kHz WAV锛屾牸寮忎笌鏉跨涓€鑷达紝浣嗕篃涓嶆槸鍦ㄦ澘绔綍鐨勶級銆?- **璁稿彲鏉℃鏈€愭潯鏍稿**锛?7 娈电殑鍏蜂綋 CC 鍗忚闇€瑕佸湪 Xeno-canto / Macaulay 鏉＄洰椤电‘璁ゅ悗鍐嶅畾浠撳簱鍒嗗彂鏂瑰紡銆?- **涓?`comparison.csv` 鐨勫彛寰勪粛鏈榻?*锛氭枃浠堕噷鍐欑殑鈥滈笩楦ｆ娴嬪噯纭巼 92% / 娴嬭瘯闆?100 娈碘€濆湪鏈洰褰曟壘涓嶅埌瀵瑰簲鏉愭枡锛屾殏鏃朵笉鑳界敤杩欏鏁版嵁澶嶇幇锛屽缓璁寜鏈洰褰曠粨鏋滈噸鍐欒琛ㄣ€?
## 宸叉帓闄ょ殑閿欒绱犳潗锛堢暀妗ｏ級

2026-10-24 鏇惧鍏?`runs.zip` 鐨?`mic_target_01` / `mic_check_01` / `mic_negative_01`銆傞璋辨牳瀵癸細琚垽涓虹洰鏍囷紙score 0.94鈥?.96锛夌殑绐楀彛閲?0.5鈥? kHz 鍗?59鈥?9%銆?鈥? kHz 浠?3鈥?%锛屼笌浠欏叓鑹查斧 2鈥? kHz 绐勫甫鍝ㄩ煶涓嶇锛岀‘璁ゆ槸 PC 澹板崱褰曠殑浜哄０/浣庨鐜澹帮紝宸插叏閮ㄧЩ闄ゃ€?
鍚屾椂鏆撮湶鐨勯棶棰橈細妯″瀷鍦ㄨ繖绫婚潪楦熼福鍣０涓婁細缁欏嚭 score鈮?.0 鐨勫亣闃虫€э紙`mic_target_01` 鏈?33/182 涓獥鍙ｏ級锛屽缓璁湪鎶ュ憡涓瀹炲啓鏄庯紝鎴栫敤鏈洰褰曟鏍锋湰閲嶆柊璇勪及鍚庡啀瀵瑰瀹ｅ竷鍑嗙‘鐜囥€?