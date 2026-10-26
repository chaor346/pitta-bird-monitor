# 接口定义

## 1. FPGA 硬件接口

### 1.1 AXI DMA 寄存器映射（axi_dma_0 @ 0x40400000）

只使能 S2MM 通道（流→内存），寄存器偏移已从 .hwh 文件确认：

| 寄存器 | 偏移 | 说明 |
|--------|------|------|
| S2MM_CR | 0x30 | 控制：bit0=Run/Idle, bit1=Reset |
| S2MM_SR | 0x34 | 状态：bit12=Idle, bit0=Halted |
| S2MM_DA_L | 0x48 | 目的地址低32位（物理地址） |
| S2MM_DA_H | 0x4C | 目的地址高32位 |
| S2MM_LEN | 0x58 | 传输字节数-1 |

复位流程：
```python
def reset_dma(m, base):
    m.write(0x30, 0x4)      # S2MM_CR: Reset
    m.write(0x34, 0x1000)   # S2MM_SR: 清除所有错误位
    m.write(0x30, 0x1)      # S2MM_CR: Run
```

### 1.2 I2S 时序（i2s_mems_rx_0）

- 采样率：32000 Hz
- 数据格式：24bit 右对齐，**符号扩展到 32bit**
- 通道：立体声交错 [L, R]
- BCLK：由核内部生成（FCLK0=100MHz 分频）
- WS：0=左声道，1=右声道
- 输出流：连续 AXI-Stream，**TLAST 恒为 0**；2048 beats（1024 帧）是 PS 侧 S2MM 的 buffer 长度，DMA 收满一个 buffer 即向软件报一次完成，与硬件 TLAST 无关

```
BCLK ──┐_┌─┐_┌─┐_┌─┐_┌─┐_┌─┐_┌
WS    ───────┐           ┌───────┐
            └─L(24bit)───┘ R(24bit)
SD    ──[31:24]xxxxx[23:0]──
```

### 1.3 引脚约束（inmp441_pmodb.xdc）

| 信号 | PMOD B 引脚 | FPGA 引脚 |
|------|-------------|-----------|
| SCK (BCLK) | Pin1 | W14 |
| WS | Pin2 | Y14 |
| SD | Pin3 | T11 |
| VDD | Pin6 | 3V3 |
| GND | Pin5 | GND |
| L/R | Pin5 | GND（必须接地） |

**关键坑**：INMP441 的 L/R 引脚悬空时输出全 0，必须接地（左声道）或接 VDD（右声道）。

## 2. 软件接口协议

### 2.1 触发文件协议（音频→图像）

- 路径：`<BASE_DIR>/runtime/trigger/pitta.trigger`
- 音频端检测到鸟鸣（score≥threshold，正式部署 0.985、min_hits 1）时写入
- 写成**原子发布**：先写同目录临时文件再 `os.link()` 成目标名，避免读端拿到半截文件；
  若目标已存在（视觉端还没取走），本次事件被合并（`pending_exists_coalesced`），不排队堆积
- 图像端 WAITING 状态轮询检测到文件 → **删除文件** → 进入 SEARCHING
- 文件必须被删除，否则重复触发

内容是 **JSON**（不是纯文本），关键字段：

```json
{"start_s": 18.0, "end_s": 20.0, "score": 0.9863, "unix_time": 1761.0,
 "event_id": "3f1c…", "source": "inmp441", "hit_beijing": "2026-10-24 22:18:26",
 "audio_output": "/home/xilinx/runtime/audio_sessions/session_XXXXXXXX/results",
 "audio_file": ".../microphone.wav", "note": "window evidence, not exact call onset/offset",
 "time_definition": "model_hit_time_and_audio_window", "vision_notify": "published"}
```

> `start_s/end_s` 是**参与判定的 2 s 窗口**，不是鸟叫的精确起止；`hit_beijing` 是模型判定
> 命中时刻（北京时间），做时间轴统计请用它而不是窗口起点。

### 2.2 录像暂停锁协议（图像→音频）

- 路径：`<BASE_DIR>/runtime/trigger/vision_recording.lock`
- 图像端开始录像时写入（存在→音频暂停推理）
- 图像端录像保存完成后删除（消失→音频恢复）
- 两端 `--audio-pause-file` 路径必须一致

实现：`av_recording_lock.py` 提供 `RecordingLock`/`recording_state`，
基于文件存在性 + 锁内 PID 校验，避免误判。

### 2.3 状态接口（图像端）

| 状态 | 进入条件 | 退出条件 |
|------|----------|----------|
| WAITING | 程序启动 / 录像结束 | 检测到触发文件 |
| SEARCHING | 收到触发 | 检测到鸟 / 搜索超时(search_sec) |
| RECORDING | 检测到鸟并保存照片 | 连续无鸟或 vision_timeout |

## 3. 数据格式约定

### 3.1 音频数据

- 解码：硬件已把 24 bit 符号扩展到 32 bit。现行板端实现是
  `& 0xffffff` 取 24 bit → **按 bit23 符号扩展** → `/256` 得 int16 PCM（codec 只吃 PCM16）
  → `/32768` 得 float；净效果等价于 `signed / 2**23`
- ⚠️ 坑在"掩码后不补符号扩展"：`& 0xffffff` 会把负半周变成接近满量程的正值，导致推理分数骤降
  （旧代码就是这么错的，报错症状见 `skill/pitfalls/pynq_pitfalls.md` A2）

### 3.2 模型输入

| 模型 | 输入 | 输出 | 阈值 |
|------|------|------|------|
| 鸟鸣 CNN | mel [1,1,64,201] float32 | logit → sigmoid | 0.985（正式部署，`audio_model.npz` 内置）/ 0.5（调试、离线评估口径） |
| YOLOv8n | 图像 [1,3,320,320] RGB | boxes [1,5,2100] | conf 0.52, iou 0.45 |

### 3.3 录音输出

- WAV：32000Hz，立体声（左声道有效），float32→int16 可选
- 录像：H.264 MP4（ffmpeg 转码），yuv420p，record_fps

## 4. 目录约定

```
<BASE_DIR>/              # 脚本所在目录（/home/xilinx）
├── inmp441.bit          # 比特流
├── infer_ncnn           # 图像推理二进制
├── best_ncnn.param/bin  # 图像模型
├── audio_model.npz      # 音频模型
└── runtime/
    ├── trigger/         # 触发文件 + 录像锁
    ├── annotated/       # 检测照片 frame_*.jpg + JSON
    ├── videos/          # 录像 pitta_*.mp4 + JSON
    └── preview/         # 预览流（可选）
```
