# test_audio/ 音频测试集

**正样本：仙八色鸫（Pitta nympha）鸣声 9 段，753.2 s / 1,474 个 2 s 窗口，命中 500 个。**
**负样本：环境音 10 段 + 其他鸟鸣 8 段，1,060.0 s / 2,063 个窗口全部未触发（误报 0）。**
板端录音尚未导入。

## 命名规范

```
<split>_<class>_<detail>.<ext>
split  : pos（正样本） / neg（负样本）
class  : pitta（仙八色鸫） / ambient（环境音） / bird（其他鸟鸣）
detail : 原始来源编号（ML…/XC…）或场景名 / 物种名
```

| 目录 | 前缀 | 示例 |
|------|------|------|
| `positive/` | `pos_pitta_nympha_` | `pos_pitta_nympha_xc179391.mp3` |
| `negative/ambient/` | `neg_ambient_` | `neg_ambient_rain_hiss.wav` |
| `negative/other_birds/` | `neg_bird_` | `neg_bird_mycerobas_carnipes.mp3` |

- 全部小写英文 + 下划线，无空格、无中文，符合竞赛对仓库路径的要求。
- 每段音频配两个同前缀 CSV：`_predictions.csv`（逐窗）与 `_events.csv`（事件），排序时自动聚在一起。
- `manifest.csv` 是全目录清单（路径、标签、类别、时长、采样率、声道、窗口数、各阈值命中数、事件数、峰值分数），改名后需同步更新。
- 2026-10-24 统一过一次命名：正样本加 `pos_` 前缀，环境音由 `neg_env_` 改为 `neg_ambient_`（与目录名一致）。只改文件名，音频内容与 CSV 数据未变。

## 正样本文件清单

| 文件 | 原始 ID | 时长 | 采样率 / 声道 | 窗口 | score≥0.5 | score≥0.985 | 事件 | 峰值 |
|------|---------|-----:|---------------|-----:|----------:|------------:|-----:|-----:|
| `positive/pos_pitta_nympha_ml341061311.mp3` | ML341061311 | 250.8 s | 48 kHz / 立体声 | 498 | 265 | 183 | 54 | 1.0000 |
| `positive/pos_pitta_nympha_xc1043065.wav` | XC1043065 | 143.0 s | 48 kHz / 单声道 | 282 | 156 | 102 | 33 | 1.0000 |
| `positive/pos_pitta_nympha_xc183002.mp3` | XC183002 | 68.8 s | 44.1 kHz / 立体声 | 134 | 61 | 44 | 12 | 1.0000 |
| `positive/pos_pitta_nympha_xc188359.mp3` | XC188359 | 68.8 s | 44.1 kHz / 立体声 | 134 | 47 | 27 | 10 | 0.9998 |
| `positive/pos_pitta_nympha_xc133003.mp3` | XC133003 | 66.7 s | 48 kHz / 立体声 | 130 | 69 | 50 | 15 | 1.0000 |
| `positive/pos_pitta_nympha_xc183003.mp3` | XC183003 | 52.9 s | 44.1 kHz / 立体声 | 102 | 32 | 22 | 6 | 1.0000 |
| `positive/pos_pitta_nympha_xc801745.mp3` | XC801745 | 45.0 s | 44.1 kHz / 单声道 | 87 | 41 | 30 | 9 | 1.0000 |
| `positive/pos_pitta_nympha_xc179391.mp3` | XC179391 | 42.9 s | 44.1 kHz / 单声道 | 82 | 41 | 34 | 8 | 1.0000 |
| `positive/pos_pitta_nympha_ml659112304.mp3` | ML659112304 | 14.3 s | 48 kHz / 立体声 | 25 | 12 | 8 | 3 | 1.0000 |
| **合计（9 段）** | — | **753.2 s** | — | **1,474** | **724** | **500** | **150** | — |

每段两个结果文件（同名前缀）：

- `*_predictions.csv`：逐窗 `start_sec / end_sec / score / prediction / event_id / rms_dbfs`；
- `*_events.csv`：`event_id / start_sec / end_sec / positive_windows / peak_score`。

## 筛选规则

原始包 `raw_target.zip` 共 15 段，全部为仙八色鸫。按下列客观指标筛，满足全部 6 条才收录：

| 规则 | 阈值 |
|------|------|
| 时长 | ≥ 10 s |
| 削波 | 样本绝对值≥0.999 的比例 < 0.1% |
| 本底噪声（帧 RMS 的 10 分位） | ≤ −35 dBFS |
| 动态范围（95 分位 − 10 分位） | ≥ 19 dB |
| 录音电平（帧 RMS 的 95 分位） | ≥ −32 dBFS |
| 鸣声带能量（0.2 s 帧内 2–4 kHz 占响帧能量） | ≥ 40% |
| 码率 | ≥ 128 kbps（WAV 不受限） |

结果：9 段入选，6 段排除。

### 排除的 6 段

| 原始 ID | 时长 | 排除原因 |
|---------|-----:|----------|
| ML658106733 | 18.2 s | 动态范围 14.9 dB，2–4 kHz 占 0%（主频 65 Hz），实质是低频噪声 |
| ML659430723 | 124.4 s | 本底 −29.7 dBFS（环境噪声大），动态范围 17.7 dB |
| ML661668457 | 21.4 s | 动态范围 16.0 dB，主频 1.78 kHz、2–4 kHz 占 0%，模型仅命中 10.3% |
| XC303934 | 46.9 s | 电平过低（最响 −31.7 dBFS），命中率 21.1% |
| XC304043 | 7.1 s | 时长不足 10 s |
| XC664516 | 11.7 s | 时长偏短，且码率 101 kbps 低于阈值 |

`ML661668457` 此前作为标注对照样本导入过一次，这次按规则移出。它不是录音损坏，而是其鸣声主频偏低、不在模型通带内，留作正样本会误导指标。如需复核旧评测，可用原始包单独跑（0.5 阈值下为 8 个窗口 / 2 个事件）。

## 负样本一：环境音（10 段）

| 文件 | 场景 | 时长 | 窗口 | 最高分 |
|------|------|-----:|-----:|-------:|
| `negative/ambient/neg_ambient_ac_hum_office.wav` | 室内空调嗡声 | 40.0 s | 77 | 0.0003 |
| `negative/ambient/neg_ambient_crowd_babble.wav` | 人群嘈杂 | 60.0 s | 117 | 0.0000 |
| `negative/ambient/neg_ambient_footsteps_pavement.wav` | 人行道脚步 | 30.0 s | 57 | 0.0064 |
| `negative/ambient/neg_ambient_garden_ambient.wav` | 庭院环境（无鸟） | 60.0 s | 117 | 0.0013 |
| `negative/ambient/neg_ambient_keyboard_typing.wav` | 键盘敲击 | 45.0 s | 87 | 0.0002 |
| `negative/ambient/neg_ambient_rain_hiss.wav` | 雨声 | 45.0 s | 87 | 0.0000 |
| `negative/ambient/neg_ambient_room_tone.wav` | 房间底噪 / 粉噪 | 45.0 s | 87 | 0.0001 |
| `negative/ambient/neg_ambient_traffic_street.wav` | 街道车流 | 60.0 s | 117 | 0.0005 |
| `negative/ambient/neg_ambient_wind_gusts.wav` | 阵风 | 60.0 s | 117 | 0.0004 |
| `negative/ambient/neg_ambient_wind_leaves.wav` | 风吹树叶 | 40.0 s | 77 | 0.0000 |
| **合计（10 段）** | — | **485.0 s** | **940** | **0.0064** |

- 全部为 32 kHz / 单声道 16 bit WAV，可直接按板端采样率喂模型，不需要重采样；均为无鸟鸣的环境片段（`garden_ambient` 在命名上已标注 no bird）。
- 挑选标准：覆盖 10 类互不重复的常见误触发场景（稳态嗡声、雨、风、水叶、脚步、人流、键盘、交通），无削波，时长 ≥30 s。

## 负样本二：其他鸟鸣（8 段）

| 文件 | 物种（原始文件名） | 时长 | 窗口 | 最高分 |
|------|------|-----:|-----:|-------:|
| `negative/other_birds/neg_bird_carpodacus_sibiricus_ussuriensis.mp3` | Carpodacus sibiricus ussuriensis | 120.1 s | 237 | 0.0329 |
| `negative/other_birds/neg_bird_urocynchramus_pylzowi.mp3` | Urocynchramus pylzowi | 109.1 s | 215 | 0.0031 |
| `negative/other_birds/neg_bird_pterorhinus_waddelli.mp3` | Pterorhinus waddelli | 86.5 s | 170 | 0.0042 |
| `negative/other_birds/neg_bird_cyanoptila_cumatilis.mp3` | Cyanoptila cumatilis | 81.8 s | 160 | 0.0017 |
| `negative/other_birds/neg_bird_carpodacus_subhimachalus.mp3` | Carpodacus subhimachalus | 67.1 s | 131 | 0.0009 |
| `negative/other_birds/neg_bird_mycerobas_carnipes.mp3` | Mycerobas carnipes | 40.8 s | 78 | 0.0024 |
| `negative/other_birds/neg_bird_pyrrhula_erythaca.mp3` | Pyrrhula erythaca | 37.3 s | 71 | 0.0029 |
| `negative/other_birds/neg_bird_agraphospiza_rubescens.mp3` | Agraphospiza rubescens | 32.3 s | 61 | 0.0018 |
| **合计（8 段）** | 8 个不同属 / 种 | **575.0 s** | **1,123** | **0.0329** |

挑选标准（从原始包的 54 种中取 8 种）：

| 规则 | 阈值 |
|------|------|
| 动态范围 | ≥ 27 dB |
| 2–8 kHz 能量占响帧 | ≥ 44% |
| 单文件体积 | ≤ 5 MB（原始码流，不转码） |
| 覆盖 | 不同属、不同体型与鸣唱类型，避免全是同一类雀形目鸣禽 |

**未导入的 46 种**：主因是体积（多段 20–110 MB，最长单段 26 min，全导入会让仓库体积翻数倍）与质量不达标。质量最差的几段为例：

| 物种 | 时长 | 不达标原因 |
|------|-----:|------------|
| Anthus_hodgsoni_hodgsoni | 44.5 s | 动态范围 4.9 dB，2–8 kHz 占 4.6%，几乎全是噪声 |
| Ianthocincla_maxima | 33.7 s | 动态范围 3.5 dB，2–8 kHz 占 3.0% |
| Motacilla_tschutschensis_taivana | 10.5 s | 动态范围 5.6 dB，2–8 kHz 占 8.2% |
| Carpodacus_davidianus | 41.1 s | 动态范围 17.9 dB，2–8 kHz 占 4.2% |
| Turdus_hortulorum | 216.0 s | 动态范围 8.3 dB，2–8 kHz 占 15.8% |
| Prinia_striata | 37.1 s | 本底 −25.6 dBFS 偏吵，且有削波 |

`Motacilla_tschutschensis_taivana` 正好是旧评测 `full_test_fixed_050` 的负样本之一（当时 max_score 0.0006），这次因质量不达标未导入；旧评测的 10 段负样本里只有 `Carpodacus_sibiricus_ussuriensis`、`Mycerobas_carnipes`、`Pterorhinus_waddelli`、`env_rain_hiss` 这 4 段进了本目录。

## 负样本误报结果

- 18 段、2,063 个 2 s 窗口，**score ≥ 0.5 的 0 个，score ≥ 0.985 的 0 个，候选事件 0 个**。
- 全目录最高分 0.0329（`Carpodacus_sibiricus_ussuriensis`），距 0.5 阈值还有 15 倍余量。
- 与旧 torch 评测逐段对照（同一录音）：`Mycerobas_carnipes` 0.0028 → 0.0024，`Pterorhinus_waddelli` 0.0027 → 0.0042，`Carpodacus_sibiricus_ussuriensis` 0.0209 → 0.0329，`env_rain_hiss` 0.00002 → 0.0000。数量级一致，差异来自 mp3 解码与重采样实现。
- **口径限制**：这只说明"这 18 段材料上没有误报"，不是总体误报率。真实野外还有昆虫、蛙类、风声骤变、设备摩擦等未覆盖，且 46 种鸟未测。

## 来源

- XC 编号来自 Xeno-canto（https://xeno-canto.org/<编号>），ML 编号来自 Macaulay Library。
- 原始包：`C:\Users\14204\Downloads\raw_target.zip` 的 `raw_target/` 目录（15 段），全部保留，本目录只取 9 段。
- 负样本原始包：`C:\Users\14204\Downloads\raw_negative.zip` 的 `raw_negative/` 目录（64 个文件：10 段环境音 + 54 种鸟），本目录取 18 个，其余保留在原包。
- **使用与再分发前请核对每段录音的许可条款**（Xeno-canto 条目页标注 CC 协议），并在报告/仓库 README 中注明来源编号。

## 推理设置（生成上述 CSV 的条件）

- 模型：`src/ps/audio_model.npz`（纯 numpy 实现，`src/ps/audio_numpy.py`），`sr=32000`、`n_fft=1024`、`hop=320`、`n_mels=64`、`mean=-45.12`、`std=16.89`；
- 窗口：2.0 s / 跳 0.5 s；立体声先取双声道平均；
- 重采样：44.1/48 kHz → 32 kHz，FFT 频域重采样（带限，不做低通设计）；
- 推理机：PC，numpy，27 段合计约 100 s；
- **`prediction` 用板端部署阈值 0.985**（取自 `audio_model.npz`）；`score≥0.5` 一列是为与既有评测记录（`run_config.json` 中 `threshold=0.5`）对齐保留的参考值。

## 与既有评测的对照

| 录音 | 本次 numpy 推理（0.5 阈值） | 上次 torch 推理（`runs/full_test_fixed_050`） |
|------|---------------------------|---------------------------------------------|
| `XC179391` | 41 个窗口 / 8 个事件 | 42 个窗口 / 8 个候选事件 |

两次基本吻合，差异来自重采样实现与模型导出精度。

## 缺口

- **正样本无逐窗人工标注**：`reference_annotations.json` 只给了 2 段录音的目标区间，本目录 9 段正样本都没有逐窗真值，因此能算“检出窗口数”，还不能算召回率。要算指标需人工标出每段鸣声起止。
- **负样本覆盖有限**：只测了 8 种鸟 + 10 类环境音，原始包里另有 46 种因体积/质量未导入；昆虫、蛙类、设备摩擦等未覆盖。
- **板端录音缺失**：PYNQ-Z2 上 INMP441 采的 32000 Hz 原始窗口（`/home/xilinx/results_av/*.wav`）仍需补采；本目录正样本都来自公开录音，不是板端采集（环境音负样本本身是 32 kHz WAV，格式与板端一致，但也不是在板端录的）。
- **许可条款未逐条核对**：27 段的具体 CC 协议需要在 Xeno-canto / Macaulay 条目页确认后再定仓库分发方式。
- **与 `comparison.csv` 的口径仍未对齐**：文件里写的“鸟鸣检测准确率 92% / 测试集 100 段”在本目录找不到对应材料，暂时不能用这套数据复现，建议按本目录结果重写该表。

## 已排除的错误素材（留档）

2026-10-24 曾导入 `runs.zip` 的 `mic_target_01` / `mic_check_01` / `mic_negative_01`。频谱核对：被判为目标（score 0.94–0.96）的窗口里 0.5–2 kHz 占 59–69%、2–6 kHz 仅 3–4%，与仙八色鸫 2–4 kHz 窄带哨音不符，确认是 PC 声卡录的人声/低频环境声，已全部移除。

同时暴露的问题：模型在这类非鸟鸣噪声上会给出 score≈1.0 的假阳性（`mic_target_01` 有 33/182 个窗口），建议在报告中如实写明，或用本目录正样本重新评估后再对外宣布准确率。
