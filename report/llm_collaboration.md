# 大模型协作记录

本文档记录项目开发过程中与大模型（LLM）的关键协作过程，包括提示词、模型回答、自我纠错轨迹与智能体工作流设计。

---

## 1. FPGA DMA 寄存器排查过程

### 问题
AXI DMA S2MM 通道不传输数据，MMIO 读写寄存器无反应。

### 提示词
```
AXI DMA 的 S2MM 通道寄存器偏移是多少？我用的是 Xilinx AXI DMA 7.1 IP，
只使能了 S2MM 通道。我在 .hwh 文件里看到基地址是 0x40400000，
但写 0x00 偏移的 CR 寄存器不生效。
```

### 模型回答（关键纠错）
> AXI DMA 的 S2MM 通道寄存器偏移不是从 0x00 开始！
> MM2S 通道: CR=0x00, SR=0x04, DA=0x18, LEN=0x28
> S2MM 通道: CR=0x30, SR=0x34, DA=0x48, LEN=0x58
> 你只使能了 S2MM，所以应该用 0x30 偏移，不是 0x00。

### 验证
修改偏移后 DMA 正常传输，问题解决。此经验沉淀为 Skill 1。

---

## 2. INMP441 数据全 0 排查

### 问题
DMA 能收到数据，但全部是 0，左声道和右声道 RMS 都接近 0。

### 提示词
```
INMP441 I2S 麦克风数据全 0，可能是什么原因？
我已经确认 BCLK/WS/SD 引脚约束正确，DMA 也能收到数据但全是 0。
L/R 引脚我没接，悬空了。
```

### 模型回答（关键纠错）
> INMP441 的 L/R 引脚必须接 GND 或 VDD，不能悬空！
> - L/R = GND → 左声道输出数据
> - L/R = VDD → 右声道输出数据
> - 悬空 → 内部状态不确定，可能输出全 0
> 请用万用表蜂鸣档确认 L/R 到 GND 的导通性。

### 验证
用户用万用表确认 L/R 未接地，接地后左声道 RMS=753545，数据正常。此经验沉淀为 Skill 1。

---

## 3. 24bit 音频数据解码错误

### 问题
录音 WAV 文件离线推理分数高（0.9+），但实时推理分数极低（最高 0.075）。

### 提示词
```
同样的音频数据，inmp441_record.py 录的 WAV 用模型推理 score=0.9，
但 inmp441_predict.py 实时推理 score=0.075。
record.py 用 raw.astype(np.float64) / 2**23，
predict.py 用 & 0xffffff 掩码 + 手动符号扩展 + 转 int16。
哪个是对的？
```

### 模型回答（关键纠错）
> 你的 I2S 核是 24bit 右对齐并符号扩展到 32bit。
> 这意味着硬件已经把 24bit 有符号数符号扩展成了 32bit，
> 直接 raw / 2**23 就是正确的 float 转换。
> 用 & 0xffffff 掩码会把符号位抹掉，导致负数变成正数，
> 信号严重失真，所以推理分数低。
> 统一用 raw / 2**23，不要掩码。

### 验证
修改后实时推理 score 达到 0.9+，与离线一致。

---

## 4. signal only works in main thread 错误

### 问题
inmp441_predict.py 用子线程做 DMA 采集，报 `ValueError: signal only works in main thread`。

### 提示词
```
Python 子线程里调用 signal.alarm 报错 signal only works in main thread，
怎么解决？我的 recv_packet 函数用 signal 做 DMA 超时。
```

### 模型回答
> signal 模块只能在主线程使用。两种解决方案：
> 1. 把 DMA 采集放主线程，推理放子线程（推荐，采集是硬实时）
> 2. 不用 signal，用 MMIO 轮询 SR 寄存器做超时（while 循环 + time.time()）

### 选择
采用方案1，采集放主线程同步执行，推理用异步线程。修改后稳定运行。

---

## 5. 录像逻辑设计：固定时长 → 目标存在性

### 问题
固定时长录像（10秒）录到大量无鸟画面，存储效率低，且鸟还在时录像就结束了。

### 提示词
```
我需要实现：检测到鸟时开始录像，鸟消失后延迟3秒结束录像，
鸟一直在就一直录。当前是固定10秒录像。怎么改状态机？
```

### 模型回答（设计方案）
> 用"连续无鸟次数 + 时间跨度"双条件确认目标离开：
> 1. 检测到鸟 → 启动录像，last_bird_seen=now
> 2. 录像中持续异步推理 → 有鸟刷新 last_bird_seen，misses=0
> 3. 无鸟 → misses+=1，记录首次无鸟时间
> 4. 结束条件：misses >= absence_hits AND span >= absence_sec
> 5. 故障保护：vision_timeout 无新鲜结果 → 强制结束
> 推理错误/过期结果必须清零 misses，不能当作鸟离开。

### 迭代
- 第一版：固定3秒延迟 → 推理慢（6s）导致3秒内推理结果还没回来，无法确认
- 第二版：absence-hits=1 → 一次漏检就结束，太敏感
- 第三版：absence-hits=3, absence-sec=6 → 稳定，后滚约12秒
此经验沉淀为 Skill 4。

---

## 6. 智能体工作流设计：音频触发图像联动

### 工作流
```
[音频端] INMP441 → DMA → numpy CNN → 鸟鸣检测
    ↓ 检测到鸟鸣
写 pitta.trigger 文件
    ↓
[图像端] 轮询检测 pitta.trigger → 删除文件
    ↓
WAITING → SEARCHING → YOLOv8n 识别
    ↓ 检测到鸟
保存照片 → 启动录像 → RECORDING
    ↓ 鸟消失
延迟结束 → 回到 WAITING
```

### 关键设计决策
- **触发文件 vs 网络通信**：选择文件触发，因为两端在同一板子上，文件系统延迟 <100ms，且实现简单
- **音频暂停机制**：录像期间暂停音频推理，避免 CPU 争抢导致图像推理更慢
- **状态机解耦**：音频端和图像端独立进程，通过文件系统通信，崩溃不互相影响

---

## 7. GEMM 加速器上板踩坑（conv1 硬件化）

把 conv1 从 PS numpy 搬到 PL HLS GEMM 核（`gemm_top`，三路 DMA：A/B 进、C 出）
的过程中，连续遇到 6 个上板问题，全部通过与大模型协作定位。

### 7.1 S2MM 永不置 IOC（TLAST 缺失）

**问题**：DMA `recvchannel.transfer(bufC)` 返回后，DMASR 的 IOC 位始终不亮；
缓冲里其实已经有数据，但通道停在 Running，下次 transfer 报错。

**提示词**：
```
AXI DMA S2MM 通道 transfer 之后 IOC 位一直不置位，但 buffer 里有数据了。
HLS 核输出是 AXI-Stream，可能是什么原因？
```

**模型回答（关键纠错）**：
> HLS 生成的 stream 在最后一个 beat 没有拉 TLAST。AXI DMA 的 S2MM 靠 TLAST 判断
> "一帧结束"，没有 TLAST 它会一直等。两个修法：
> 1. HLS 设计里给末拍显式拉 TLAST（新版 Vitis HLS 修正了）；
> 2. 旧 bit 兼容：不要把 S2MM IOC 当完成判据，改用 HLS 核 ap_ctrl 的 ap_done(bit1)
> 作为计算完成权威判据；S2MM 缺 IOC 时 stop()→sleep 2ms→start() 复位通道复用。

**验证**：采用兼容方案，`gemm_board.py` 里 `wait_ap_done()` 轮询 ap_done，
`_ensure_s2mm_idle()` 在缺 IOC 时复位通道。此经验沉淀为 Skill D1。

### 7.2 DMA 单次 16 KB 上限

**问题**：M=12864×N=16×2byte=411 KB 的 C 缓冲，DMA transfer 失败。

**提示词**：
```
PYNQ AXI DMA recvchannel._size 报 16384 字节，但我需要传 411 KB。
怎么提高单次传输上限？
```

**模型回答**：
> 这是 AXI DMA IP 的 `c_sg_length_width` 参数，默认 14（2^14=16 KB）。
> 在 Vivado 里把它改成 23（2^23=8 MB），重新综合即可。板端可以读
> `dma.recvchannel._size` 验证是否变成 8388608。

**验证**：重新综合后 `_size=8388608`，板端脚本加了 FATAL 检查
（`if cap < need: 报错并提示重新覆盖 bit/hwh`）。沉淀为 Skill D2。

### 7.3 PYNQ 默认走中断，中断没接好导致永久挂死

**问题**：`transfer()` 之后 `wait()` 永远不返回，CPU 单核 100%。

**模型回答**：
> PYNQ 的 DMA sendchannel/recvchannel 默认等中断回调。如果块图里 DMA 的 irq
> 没接到 PS 的 pl_ps_irq0，回调永远不来。两个做法：
> 1. 正确：块图里把 irq 接到 PS，重新综合；
> 2. 快速：`os.environ["PYNQ_DISABLE_DMA_INTERRUPT"]="1"`，并清空每个 IP 的
> `interrupts` 描述，自己用寄存器轮询 DMASR。

**验证**：采用快速方案，`gemm_board.py` 第 27、143–145 行。沉淀为 Skill D3。

### 7.4 bit/hwh 版本不一致

**问题**："我明明改了 TLAST 怎么还是不置 IOC"——因为板上根本是旧 bit。

**模型建议**：板端启动时硬编码期望 MD5 做自检，不一致就 FATAL 退出；
覆盖文件后必须断电重启或重开 Python 进程（PYNQ Overlay 缓存）。

**验证**：`verify_board.sh` 与 `gemm_board.py` 的 MD5 自检（`gemm_soc.bit`
期望 MD5 `81714b8306646bbe102e41236a0a3054`）。沉淀为 Skill D5。

### 7.5 端到端结果

板端 `e2e_board.py --repeat 5` 实测：
- numpy 全浮点分数 0.997876；
- 硬件 conv1 分数 0.997878；
- conv1 205824 点最大误差 0.001838（容差 0.02，0 点超差）；
- HLS 核 ap_done 纯计算 6.7 ms；numpy 整网 0.493–0.497 s；
- 判定 PASS。

**注意**：6.7 ms 只是 HLS 核纯计算时间，不含 im2col/Q12/DMA/cache/反量化；
与 numpy 整网 0.497 s 不能直接相除声称加速比。公平加速比待补测。
此口径意识本身也是与大模型协作中反复核对后确立的。

---

## 8. 提示词模板沉淀

从以上协作过程中提炼的可复用提示词模板，详见 `skill/README.md` Skill 2。

---

## 9. 模型选择与放弃的候选

| 候选方案 | 选择/放弃 | 原因 |
|----------|-----------|------|
| ncnn 音频模型 | 放弃 | sound_ncnn.bin 仅 476 字节（onnx2ncnn 未读外部权重），转换失败 |
| numpy 音频模型 | 选择 | 用户提供，纯 numpy 实现，无需额外库，精度验证通过 |
| ALSA 音频采集 | 放弃 | /proc/asound/cards 显示 no soundcards，板子无音频编解码器 |
| FPGA DMA 音频采集 | 选择 | I2S 核 + AXI DMA，高吞吐低延迟，不占 CPU |
| 固定时长录像 | 放弃 | 存储效率低，鸟还在就结束 |
| 目标存在性录像 | 选择 | 只录目标相关片段，存储效率高 5-10x |
| conv1 走 PS numpy（整网） | 放弃（已替换） | A9 上整网 0.5 s，conv1 是计算主项之一 |
| **conv1 走 PL HLS GEMM** | **选择** | im2col 后是规则 GEMM（M=12864 K=9 N=16），Q12 定点；板端 ap_done 6.7 ms，端到端分数与 numpy 一致（max_err 0.001838，0/205824 超差） |
| FFT+mel 搬 PL | 放弃（暂不实施） | 分析估算 20×，但 AXI-Stream 乒乓缓冲 + 定点验证工程量大，性价比不高，留作后续 |

---

## 10. GEMM 工程缺失：依据 .hwh 反推一键重建

### 问题
提交前发现 GEMM 加速器只保留了板端 `gemm_soc.bit/.hwh`、HLS IP 源码，**Vivado `.xpr` 工程已不存在**，无法直接导出 GEMM overlay 自身的综合/实现/功耗报告。

### 与大模型协作的重建过程
1. 解析 `gemm_soc.hwh`，逐一反推出块图：实例（ps7、gemm_top_0、dma_A/B/C、xlconcat、proc_sys_reset）、地址段、AXI 位宽、中断连接；
2. 编写 `build/build_gemm.tcl` 自动重建块图并跑综合/实现/比特流；
3. 三次迭代修复：
   - 手动 `set_property offset` 报只读——automation 已自动分配，删除多余赋值；
   - 时钟/复位引脚名核对（HLS 核为 `ap_clk`/`ap_rst_n`、有 `interrupt`）；
   - **中文工程路径导致 processing_system7 生成失败**——改为在系统英文临时目录建工程，仅把报告写回；
4. 把 HLS IP 从扁平文件重组为完整标准打包目录（`component.xml` + hdl/drivers/xgui/constraints）。

### 结果
脚本端到端跑通，`build/gemm/` 下生成三份报告（utilization/timing/power）与 bit/hwh：
LUT 10.11%、FF 7.05%、BRAM 7.86%、DSP 30.45%、WNS +1.520 ns、功耗 1.741 W。

### 同步建立的测量工具
- `label_audio_events.py` + `eval_recall.py`：半自动标注 + 事件级召回（在 PC 上完成）；
- `stability_monitor.sh`：板端连续运行时长监控。

> 关键原则（与大模型反复核对确立）：真值不能用模型自身输出代替；公平加速比必须同板同口径；
> 估计值必须标注。这些都写进了 `skill/SKILL.md` 的判定口径。
