# 仙八色鸫鸣声与图像协同监测系统

基于 PYNQ-Z2 (Zynq-7000 XC7Z020) 的濒危鸟类自动化监测系统。
通过 FPGA 硬件音频采集 + ARM 端 AI 推理，实现鸟鸣触发、图像识别与目标存在性录像的完整闭环。

## 系统功能

1. **FPGA 音频采集**：INMP441 MEMS 麦克风 → I2S 接收核 → AXI DMA → DDR，32000Hz 采样，24bit 精度
2. **鸟鸣检测**：3 层 CNN，2 秒滑动窗口，检测到鸟鸣写触发文件。conv1（3×3, 16 通道）已做 PL HLS GEMM 核验证（M=12864 K=9 N=16, Q12 定点，独立 overlay `gemm_soc.bit`，端到端分数与浮点一致）；**正式运行的音频主程序仍为 numpy 全软件实现**，两个 overlay 分时加载
3. **声音触发图像**：图像端检测触发文件 → 进入搜索状态 → YOLOv8n (ncnn) 识别仙八色鸫
4. **目标存在性录像**：检测到鸟开始录像，鸟消失后延迟结束，录像期间暂停音频推理避免 CPU 争抢

## 硬件清单

| 器件 | 型号 | 接口 |
|------|------|------|
| FPGA 开发板 | PYNQ-Z2 (XC7Z020CLG400-1) | - |
| MEMS 麦克风 | INMP441 | PMOD B (I2S) |
| USB 摄像头 | 1080p USB UVC | /dev/video0 |

## 目录结构

```
pitta_bird_monitor/
├── README.md
├── LICENSE
├── .gitignore
├── docs/                  # 架构、接口、硬件接线
├── src/
│   ├── fpga/              # I2S 接收核 RTL + GEMM HLS IP
│   └── ps/                # 板端 Python + 模型 + PC 训练脚本（见 src/ps/README.md）
├── sim/                   # I2S 接收核 testbench（PASS）
├── build/                 # Vivado 构建脚本 + bit/hwh + 报告
│   └── gemm/              # GEMM overlay 构建产物
├── board/                 # 上板脚本（systemd 服务 + 手动调试）+ 实测日志
├── data/                  # 测试数据 + 指标汇总
├── skill/                 # 可复用 PYNQ 验证技能包
└── report/                # 设计报告 + 海报 + 大模型协作记录
```

## 复现步骤

### 1. 硬件连接

- INMP441 → PMOD B：VDD→Pin6(3V3), GND→Pin5, SCK→Pin1(W14), WS→Pin2(Y14), SD→Pin3(T11), L/R→Pin5(GND)
- USB 摄像头 → 板子 USB 口

### 2. FPGA 构建（可选，bit 已提供）

```bash
# 在 PC 上用 Vivado 2026.1
vivado -mode batch -source build/build.tcl
# 产出 inmp441.bit 和 inmp441.hwh
```

### 3. 板端部署

```bash
# 上传文件到 PYNQ-Z2（只拷 A 类运行文件，历史版本不必拷，见 src/ps/README.md）
scp build/inmp441.bit build/inmp441.hwh xilinx@192.168.2.99:/home/xilinx/
scp src/ps/inmp441_predict_time.py src/ps/inmp441_predict_pause.py \
    src/ps/trigger_board_presence.py src/ps/inmp441_record.py \
    src/ps/av_recording_lock.py src/ps/audio_numpy.py \
    src/ps/infer_ncnn.cpp xilinx@192.168.2.99:/home/xilinx/
scp src/ps/best_ncnn.param src/ps/best_ncnn.bin \
    src/ps/audio_model.npz src/ps/mel_basis.npy xilinx@192.168.2.99:/home/xilinx/
scp board/*.sh board/*.service xilinx@192.168.2.99:/home/xilinx/

# SSH 到板子
ssh xilinx@192.168.2.99

# 配置环境（依赖 + runtime 目录 + 摄像头权限 + 编译 infer_ncnn）
sudo bash /home/xilinx/setup.sh
```

> `setup.sh` 已包含 `infer_ncnn` 的编译，不必再手工 `g++`。

### 4. 运行

两种方式二选一：**手动调试**（下面终端 1/2，阈值 0.5）或 **systemd 正式部署**
（`board/pitta-audio.service` + `board/pitta-vision.service`，阈值 0.985、音频每 1800 s
自动换会话）。两者参数不同，报告里的实测数字均来自 systemd 正式部署。

```bash
# 正式部署（推荐，开机自启 + 崩溃拉起）
sudo cp board/pitta-audio.service board/pitta-vision.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now pitta-vision pitta-audio
journalctl -u pitta-audio -u pitta-vision -f
```

```bash
# 终端1：音频检测（调试参数，等价于 bash start_audio.sh）
sudo python3 -u inmp441_predict_pause.py \
  --model audio_model.npz --overlay inmp441.bit \
  --threshold 0.5 --min-hits 1 \
  --hop 1.5 --cooldown 5 \
  --release-threshold 0.3 --release-hits 2 \
  --seconds 600 --out results_av \
  --vision-trigger /home/xilinx/runtime/trigger/pitta.trigger \
  --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock

# 终端2：图像识别 + 存在性录像（等价于 bash start_vision.sh）
sudo chmod 666 /dev/video0
sudo python3 -u trigger_board_presence.py \
  --width 640 --height 480 --fps 5 --detect-hz 0.2 \
  --search-sec 30 --record-fps 5 \
  --absence-hits 3 --absence-sec 6 --vision-timeout 60 \
  --audio-pause-file /home/xilinx/runtime/trigger/vision_recording.lock
```

### 4.5 GEMM 端到端验证（conv1 硬件加速）

conv1 走 PL HLS GEMM 核的端到端验证，不依赖摄像头/麦克风，用录好的 wav 即可。
仓库里文件按规范分散存放，板端部署时需收集到同一目录：

```bash
# 在 PC 上把分散的 GEMM 文件收集到板端 /home/xilinx/gemm/
ssh xilinx@192.168.2.99 'mkdir -p /home/xilinx/gemm'
scp build/gemm/gemm_soc.bit build/gemm/gemm_soc.hwh  xilinx@192.168.2.99:/home/xilinx/gemm/
scp src/ps/e2e_board.py src/ps/gemm_board.py       xilinx@192.168.2.99:/home/xilinx/gemm/
scp data/gemm/*                                      xilinx@192.168.2.99:/home/xilinx/gemm/
scp src/ps/audio_model.npz                           xilinx@192.168.2.99:/home/xilinx/gemm/
scp board/verify_gemm.sh                             xilinx@192.168.2.99:/home/xilinx/gemm/

# 板端自检文件版本
cd /home/xilinx/gemm
bash verify_gemm.sh

# 端到端：wav → numpy 特征 → 硬件 conv1 → numpy 其余层 → 分数
sudo python3 e2e_board.py
sudo python3 e2e_board.py --repeat 5    # 重复 5 次测稳定耗时
```

预期输出：硬件 conv1 分数 ≈ 0.9979，numpy 全浮点 ≈ 0.9979，
conv1 最大误差 < 0.02（205824 点 0 超差），判定 PASS。
详见 `build/gemm/README.md`。

### 5. 测试

播放鸟鸣声音 → 终端1输出 `TRIGGER` → 终端2输出 `收到声音触发，开始搜鸟` → 检测到鸟 → 开始录像 → 鸟消失后延迟结束 → 回到等待。

### 6. 运行产物落点（简介所说的"照片、视频与预测日志"）

板端 `~/runtime/` 下：

| 目录 | 内容 |
|------|------|
| `runtime/annotated/` | `frame_*.jpg` 抓拍快照 + `frame_*.json` 预测日志（时间戳、帧序号、框坐标、置信度、推理耗时） |
| `runtime/videos/` | 目标存在期间的 MP4 录像 |
| `runtime/trigger/` | 音频触发文件 `pitta.trigger`、录像锁 `vision_recording.lock` |

### 7. 扩展到其他鸟类

软硬件流程与物种无关，换物种只需替换数据与模型：

1. **音频端**：采集新物种鸣声正样本 + 本地环境负样本，重跑 `train_binary_fixed.py`，替换 `audio_model.npz`；
2. **视觉端**：按 `pitta.yaml` 的标注格式采集新物种图片，重跑 `03_train.py` 训练 + `04_export.py` 导出 ncnn，替换 `best_ncnn.param/bin`；
3. 调整部署阈值（当前音频 0.985 / 视觉 conf 0.52）即可，采集核、I2S、DMA、录像状态机全部复用。

## FPGA 资源占用

| 资源 | 占用 | 可用 | 利用率 |
|------|------|------|--------|
| Slice LUTs | 1675 | 53200 | 3.15% |
| Slice Registers | 2281 | 106400 | 2.14% |
| Block RAM Tile | 1 | 140 | 0.71% |
| DSP48 | 0 | 220 | 0% |

时钟频率：100MHz (FCLK0)，时序收敛。

上表是**音频 overlay**（`inmp441.bit`）。GEMM overlay（`gemm_soc.bit`）单独一组：
LUT 5376 (10.11%) / FF 7505 (7.05%) / BRAM 11 (7.86%) / DSP 67 (30.45%)，WNS +1.520 ns，
功耗估算 1.741 W（confidence Medium）。两者分时加载，不同时占板。

## 关键性能指标

**已实测（PC 端离线推理 + FPGA 报告）：**

| 指标 | 数值 | 说明 |
|------|------|------|
| 音频采样率 | 32000 Hz | FPGA DMA 连续采集 |
| 音频窗口级特异性 | 100% | 本目录 18 段负样本 2,063 个窗口 0 误报，最高分 0.0329（非总体特异性） |
| 音频事件级召回率 | 97.4%（0.985）/ 98.1%（0.5） | 9 段正样本、155 个人耳核对事件（`events_truth.csv`）；4 处漏检中 2 处在 `xc188359`；窗口级 90.6%/95.4%，见 `data/test_audio/positive/recall_results/` |
| 图像检出率 | 99.2% | raw_pitta 有标注 1,061 张检出 1,052 张（训练池口径，conf 0.52） |
| 图像特异性 | 380/380 | data/neg 380 张（321 其他鸟 + 59 纯背景）0 误报（已见负样本口径） |
| 图像 mAP@0.5 | 86.7% | images/val 有标注 220 张 / 251 框；val 与训练集同源，属训练池口径 |
| 图像板端推理延迟 | 5.65~6.72 s | ncnn YOLOv8n 320×320 双核；端到端联动日志 6 次 RECORD-INFER 抽样（均值 6.17 s），见 `board/test_output/end_to_end_20261024.md` |
| 音频板端推理延迟 | 2.075 s | 单次窗口推理（含 STFT/mel/conv/numpy），同一份联动日志 |
| 端到端触发延迟 | 约 10.5 s | 鸟鸣 TRIGGER → 检测到鸟开始录像（22:18:26.9 → 22:18:37，秒级时间戳） |
| **conv1 GEMM HLS 核耗时** | **6.7 ms** | PYNQ-Z2 @100 MHz，`e2e_board.py --repeat 5`（旧计时口径：等完 DMA 后才起算、只打印最后一次，属核完成时间下界；脚本已改为从 `ap_start` 起算）。不含 im2col/Q12/DMA/反量化 |
| **conv1 硬件 vs numpy 最大误差** | **0.001838** | 205824 点逐点，容差 0.02 下 0 点超差；端到端分数 0.997878 vs 0.997876 |
| 音频 overlay 资源 LUT/FF/BRAM/DSP | 3.15% / 2.14% / 0.71% / 0% | inmp441.bit，WNS +2.029ns，功耗 1.684 W（confidence Low） |
| GEMM overlay 资源 LUT/FF/BRAM/DSP | 10.11% / 7.05% / 7.86% / 30.45% | gemm_soc.bit，WNS +1.520ns，功耗 1.741 W（confidence Medium） |

> **图像指标口径**：训练池 mAP@0.5 86.7% 为训练分布内指标。真正独立（与训练集 MD5 无重复）
> 的 266 张网络公开测试图上，板端阈值 conf 0.52 下图像级召回 **256/266 = 96.2%**，
> 检出置信度均值 0.91。详见 `data/test_images/independent/README.md`。

**待板端实测（见 `skill/verification/board_checklist.md`）：** 连续运行时长、GEMM 公平加速比（`e2e_board.py --bench 20`）、图像推理基准延迟。详见 `data/comparison.csv`（已标注每项的实测/待实测状态与证据文件）。

## 许可证

MIT License，全文见仓库根目录 `LICENSE`。第三方组件（PYNQ、ncnn、OpenCV、ffmpeg、
Ultralytics YOLOv8）遵循各自许可证，未在本仓库内重新分发。
