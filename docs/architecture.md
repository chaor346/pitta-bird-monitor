# 系统架构设计

## 1. 系统概述

本项目实现濒危鸟类仙八色鸫的自动化监测：通过 FPGA 硬件采集麦克风音频，ARM 端 AI 推理检测鸟鸣，鸟鸣触发图像识别，识别到鸟后自动录像，鸟消失后延迟结束。系统完全运行在 PYNQ-Z2 (Xilinx Zynq-7000 XC7Z020) 单板上。

## 2. 系统分层架构

```
┌─────────────────────────────────────────────────────────────┐
│                        PYNQ-Z2 (XC7Z020)                    │
│                                                             │
│  ┌─────────── PL (FPGA 可编程逻辑) ───────────┐              │
│  │  INMP441 (MEMS麦克风)                      │              │
│  │      │ I2S (BCLK/WS/SD)                    │              │
│  │      ▼                                    │              │
│  │  i2s_mems_rx 接收核                        │              │
│  │  （32000Hz, 24bit右对齐, 双槽交错）         │              │
│  │      │ AXI-Stream 连续流 (TLAST恒0)        │              │
│  │      ▼                                    │              │
│  │  axi_dma_0 S2MM 通道                       │              │
│  │      │ AXI4 (burst)                       │              │
│  └──────┼─────────────────────────────────────┘              │
│         │ S_AXI_HP0（DDR 访问）                              │
│         ▼                                                   │
│  ┌─────── PS (ARM Cortex-A9 双核 @650MHz) ────┐              │
│  │  音频线程: DMA轮询 → numpy鸟鸣CNN推理        │              │
│  │  （2s窗口, 64×201 mel频谱, score≥0.985 正式/0.5 调试）   │              │
│  │      │ 检测到鸟鸣                            │              │
│  │      ▼                                     │              │
│  │  写触发文件 runtime/trigger/pitta.trigger   │              │
│  │      │                                     │              │
│  │  图像线程: 轮询触发文件 → YOLOv8n识别       │              │
│  │  （ncnn, 320×320, conf≥0.52）               │              │
│  │      │ 检测到鸟                             │              │
│  │      ▼                                     │              │
│  │  保存照片 + 启动录像（存在性录像）            │              │
│  │  鸟消失→延迟结束 → 回到等待                  │              │
│  └─────────────────────────────────────────────┘              │
│         │                                                   │
│         ▼                                                   │
│  USB摄像头 /dev/video0（640×480, 5fps）                     │
│  存储: runtime/annotated/（照片） runtime/videos/（录像）    │
└─────────────────────────────────────────────────────────────┘
```

## 3. 软硬件划分依据

| 功能 | 划分 | 理由 |
|------|------|------|
| I2S 音频采集 | **PL (FPGA)** | 32kHz×2声道×24bit 实时数据流，FPGA 并行接收不占 CPU；DMA 直接写 DDR，吞吐高、延迟低 |
| 音频缓冲/分帧 | PS | 内存操作，简单灵活 |
| Mel 频谱计算 | PS（numpy） | 当前实现；未来可迁移 FPGA 加速（FFT+矩阵乘） |
| **conv1 卷积（3×3, 16 通道）** | **PL HLS GEMM（独立 overlay 已上板验证）** | im2col 后是规则 GEMM（M=12864 K=9 N=16，Q12 定点），板端观测 ap_done 6.7 ms，端到端分数与浮点一致。注意：正式运行的音频主程序仍用 numpy conv1，硬件版为独立 overlay `gemm_soc.bit`，与音频 overlay 分时加载 |
| conv2/conv3/FC 等其余层 | PS（numpy） | 层间依赖强、模型小，numpy 已够；硬件 conv1 之外的整网约 0.5 s |
| 图像预处理 | PS | OpenCV 缩放/颜色转换 |
| YOLOv8n 推理 | PS（ncnn） | ARM NEON 优化，320×320 约 5-7s |
| 状态机/录像控制 | PS | 控制逻辑复杂，灵活性要求高 |
| 录像编码 | PS（ffmpeg） | 软件编码足够（5fps 640×480） |

**核心原则**：高吞吐、低延迟、数据流固定的功能放 FPGA；控制复杂、需要迭代演进的功能放 PS。

## 4. 数据流

```
音频路径:
INMP441 ─I2S─→ i2s_mems_rx ─AXI-Stream─→ axi_dma_0 S2MM ─AXI4─→ DDR buffer
    → numpy mel频谱 [64,201] → im2col/Q12 → PL HLS GEMM(conv1, 三路DMA)
    → numpy 其余层(conv2/conv3/FC) → score → 写 pitta.trigger
（conv1 硬件加速为独立 overlay gemm_soc.bit，端到端验证见 e2e_board.py）

图像路径:
USB摄像头 ─UVC─→ OpenCV (640×480) ─缩放─→ 320×320 RGB
    → ncnn YOLOv8n → boxes → 画框/保存照片/录像

联动路径:
音频端写 pitta.trigger ─文件系统─→ 图像端检测删除 → SEARCHING 状态
录像期间: 写 vision_recording.lock → 音频端暂停推理（避免CPU争抢）
录像结束: 删除 lock → 音频恢复
```

## 5. 状态机

### 图像端状态机

```
         ┌──────────────────────────────────────────┐
         │                                          │
         ▼                                          │
      WAITING ◄──────────────────────────┐          │
         │                               │          │
         │ 检测到 pitta.trigger           │          │
         ▼                               │          │
      SEARCHING                          │          │
         │                               │          │
         ├─ 搜索超时(search_sec=30s) ────┤          │
         │                               │          │
         │ 检测到鸟(conf≥0.52)            │          │
         ▼                               │          │
      RECORDING ──► 连续无鸟(absence_hits次且   ────┘
                    跨度≥absence_sec) 或
                    vision_timeout故障
```

### 音频端状态

```
采集 → 每2s窗口推理 → score≥threshold 连续min_hits次？
    → 写触发文件 → cooldown 冷却
录像锁存在 → 暂停推理（避免与图像抢CPU）
```

## 6. 关键设计决策

1. **触发文件协议**：两端独立进程，通过文件系统通信（写入延迟<100ms），比网络通信简单可靠
2. **音频暂停机制**：录像期间暂停音频推理，让出 CPU 给图像推理
3. **存在性录像**：连续 absence_hits 次无鸟 + 首末无鸟帧跨度≥absence_sec 才结束，抗单帧漏检
4. **推理错误不判为"鸟离开"**：错误/过期结果清零 misses，避免误结束
5. **慢速推理抽样判断**：推理 5-7s 只能抽样，结束晚于鸟实际离开是已知限制
