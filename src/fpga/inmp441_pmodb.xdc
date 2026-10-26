#==============================================================================
# INMP441 -> PYNQ-Z2 PmodB 约束
# 引脚来源：PYNQ-Z2 官方 master XDC (pynq-z2_v1.0.xdc)，PmodB(jb)
#
# PmodB 12 针排列（面对板卡）：
#   上排 1..6 : 1=IO0  2=IO1  3=IO2  4=IO3  5=GND  6=3.3V
#   下排 7..12: 7=IO4  8=IO5  9=IO6  10=IO7 11=GND 12=3.3V
#
# 接线：
#   INMP441 SCK(BCLK) -> PmodB 1  (jb[0] = W14)
#   INMP441 WS(LRCLK) -> PmodB 2  (jb[1] = Y14)
#   INMP441 SD(DOUT)  -> PmodB 3  (jb[2] = T11)
#   INMP441 VDD       -> PmodB 6 或 12 (3.3V)
#   INMP441 GND       -> PmodB 5 或 11 (GND)
#   INMP441 L/R       -> GND（左声道；若想右声道接 3.3V）
#   INMP441 CHIPEN    -> 3.3V（多数模块已默认接 VDD）
#
# 注意：块图中对外端口必须正好命名为 bclk / ws / sd（Make External 后改名）。
#==============================================================================

# ---- I2S 信号线（PmodB 上排前三针） ----
set_property -dict { PACKAGE_PIN W14 IOSTANDARD LVCMOS33 } [get_ports {bclk}]; # PmodB 1
set_property -dict { PACKAGE_PIN Y14 IOSTANDARD LVCMOS33 } [get_ports {ws}];   # PmodB 2
set_property -dict { PACKAGE_PIN T11 IOSTANDARD LVCMOS33 PULLDOWN true } [get_ports {sd}]; # PmodB 3  (SD 闲置时弱下拉，INMP441 数据手册要求约 100k 下拉)

# SD 更可靠的做法是在模块 SD 与 GND 之间外接 100k 电阻；
# 多数 INMP441 成品板已自带 100k 下拉，这里的 FPGA 内部下拉仅作兜底。
# VDD(3.3V) 旁建议就近并联 0.1uF 电容到 GND（多数模块已自带）。
