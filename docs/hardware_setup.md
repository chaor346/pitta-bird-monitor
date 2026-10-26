# 硬件搭建指南

## 1. 器件清单（BOM）

| 器件 | 型号/规格 | 数量 | 接口 |
|------|-----------|------|------|
| FPGA 开发板 | PYNQ-Z2 (XC7Z020CLG400-1) | 1 | - |
| MEMS 麦克风 | INMP441（I2S 输出，24bit） | 1 | PMOD B |
| USB 摄像头 | 1080p USB UVC（布里豹K20） | 1 | USB /dev/video0 |
| 电源 | 5V/2.5A DC 适配器 | 1 | 板载电源口 |
| Micro USB | UART 调试线（可选） | 1 | 板载 UART |
| 网线 | 直连 PC 网口 | 1 | RJ45 |

## 2. 接线说明

### 2.1 INMP441 → PMOD B

| INMP441 引脚 | 连接目标 | PMOD 位置 |
|--------------|----------|-----------|
| VDD | 3V3 | PMOD B Pin6 |
| GND | GND | PMOD B Pin5 |
| SCK (BCLK) | FPGA W14 | PMOD B Pin1 |
| WS | FPGA Y14 | PMOD B Pin2 |
| SD | FPGA T11 | PMOD B Pin3 |
| **L/R** | **GND**（必须接地） | PMOD B Pin5 |

> ⚠️ L/R 悬空会导致数据全 0。接 GND = 左声道输出，接 VDD = 右声道输出。
> 本项目接 GND，使用左声道。

### 2.2 USB 摄像头

- 插入板子任意 USB Host 口，识别为 /dev/video0
- 每次重启后需 `sudo chmod 666 /dev/video0`
- 若报 "Pixel format unsupported"，用 `v4l2-ctl --list-formats-ext -d /dev/video0` 确认格式，
  程序默认请求 MJPG，`--no-mjpeg` 可请求 YUYV 对照

### 2.3 网络（PC ↔ 板子直连）

- 板子静态 IP：192.168.2.99（PYNQ 默认）
- PC 以太网口静态 IP：192.168.2.1/24
- 子网掩码：255.255.255.0，网关留空
- 常见故障：PC IP 被 Windows 改为 192.168.137.1（需管理员权限改回）

## 3. 供电要求

- 板子：5V/2.5A 适配器（不足会导致 USB 摄像头不稳定、灯闪）
- 麦克风：由 PMOD 3V3 供电（INMP441 功耗 <1mA，无额外电源需求）
- 摄像头：USB 供电，若图像卡顿可考虑带供电的 USB HUB

## 4. 上电顺序

1. 插好所有接线（麦克风、摄像头、网线）
2. 接 5V 电源 → 板子启动（约 30 秒）
3. 电源灯亮 → 网口灯闪 → `ping 192.168.2.99` 通
4. SSH 登录：`ssh xilinx@192.168.2.99`（密码 xilinx）

## 5. 故障排查表

| 现象 | 检查 | 修复 |
|------|------|------|
| 麦克风数据全 0 | L/R 引脚 | 万用表蜂鸣档测 L/R→GND 导通，接地 |
| DMA 无传输 | 寄存器偏移 | 读 .hwh 确认 S2MM_CR=0x30 |
| 摄像头打不开 | 权限/格式 | chmod 666；v4l2-ctl 查格式；--no-mjpeg |
| ping 不通 | PC IP/网线 | PC 设 192.168.2.1/24；换网线；复位板子 |
| 推理分数低 | 解码方式 | 用 raw/2**23，不要 &0xffffff 掩码 |
| 录像立即结束 | 无鸟判定 | absence-hits 调大；确认推理结果新鲜 |
| 板子死机 | 过热/供电 | 断电重启；检查电源 5V/2.5A |
