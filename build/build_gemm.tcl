#!/usr/bin/env tcl
# ============================================================================
# GEMM 加速器 Vivado 工程一键重建脚本
# 用法: 在 build/ 目录下执行
#         <Vivado>/bin/vivado.bat -mode batch -source build_gemm.tcl
# 目标器件: xc7z020clg400-1 (PYNQ-Z2)
#
# 重建 conv1 GEMM 加速器块图（HLS gemm_top + 三路 AXI DMA），
# 跑综合/实现/比特流，并把 utilization/timing/power 报告与 bit/hwh 导出到 gemm/。
#
# 注意：Vivado 的 IP 生成器（XIT）对【中文工程路径】支持有缺陷，会在生成
#       processing_system7 时失败。因此本脚本把工程建在系统英文临时目录
#       （%TEMP%/gemm_work），仅把最终报告与 bit/hwh 写回本目录的 gemm/。
#       块图结构、地址、实例名均依据 gemm/gemm_soc.hwh 反推，与原工程一致。
# ============================================================================

set part xc7z020clg400-1
set project_name gemm_soc

# ---- 路径解析 ----
set build_dir  [file dirname [file normalize [info script]]]
set proj_root  [file normalize $build_dir/..]
set ip_src     [file normalize $proj_root/src/fpga/gemm]
set gemm_out   [file normalize $build_dir/gemm]

# ---- 英文工作区（规避中文路径 XIT 问题）----
set work [file normalize $::env(TEMP)/gemm_work]
file delete -force $work
file mkdir $work
file mkdir $work/ip_repo
file copy -force $ip_src $work/ip_repo/
set ip_repo $work/ip_repo/gemm

set output_dir $work/output
file mkdir $output_dir

# ---- 工程 ----
create_project $project_name $output_dir -part $part -force

# ---- 注册 HLS IP 仓库（gemm_top, VLNV student:user:gemm_top:1.0）----
set_property ip_repo_paths [list $ip_repo] [current_project]
update_ip_catalog

# ============================================================
# 块图
# ============================================================
create_bd_design "gemm_soc"

# ---- Zynq PS ----
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 ps7
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {
    make_external "FIXED_IO, DDR"
    apply_board_preset "1"
    Master "Disable"
    Slave "Disable"
} [get_bd_cells ps7]

# 使能 GP0、HP0/HP1/HP2(64bit)、FCLK0=100MHz、F2P 中断
set_property -dict [list \
    CONFIG.PCW_FPGA0_PERIPHERAL_FREQMHZ {100} \
    CONFIG.PCW_USE_M_AXI_GP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP0 {1} \
    CONFIG.PCW_USE_S_AXI_HP1 {1} \
    CONFIG.PCW_USE_S_AXI_HP2 {1} \
    CONFIG.PCW_S_AXI_HP0_DATA_WIDTH {64} \
    CONFIG.PCW_S_AXI_HP1_DATA_WIDTH {64} \
    CONFIG.PCW_S_AXI_HP2_DATA_WIDTH {64} \
    CONFIG.PCW_USE_FABRIC_INTERRUPT {1} \
    CONFIG.PCW_IRQ_F2P_INTR {1} \
] [get_bd_cells ps7]

# ---- HLS GEMM 核 ----
create_bd_cell -type ip -vlnv student:user:gemm_top:1.0 gemm_top_0

# ---- 三路 DMA：A/B 仅 MM2S，C 仅 S2MM；SG 长度位 23，stream 16bit，内存侧 32bit ----
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 dma_A
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_include_s2mm {0} \
    CONFIG.c_include_mm2s {1} \
    CONFIG.c_sg_length_width {23} \
    CONFIG.c_m_axis_mm2s_tdata_width {16} \
    CONFIG.c_m_axi_mm2s_data_width {32} \
] [get_bd_cells dma_A]

create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 dma_B
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_include_s2mm {0} \
    CONFIG.c_include_mm2s {1} \
    CONFIG.c_sg_length_width {23} \
    CONFIG.c_m_axis_mm2s_tdata_width {16} \
    CONFIG.c_m_axi_mm2s_data_width {32} \
] [get_bd_cells dma_B]

create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 dma_C
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_include_mm2s {0} \
    CONFIG.c_include_s2mm {1} \
    CONFIG.c_sg_length_width {23} \
    CONFIG.c_s_axis_s2mm_tdata_width {16} \
    CONFIG.c_m_axi_s2mm_data_width {32} \
] [get_bd_cells dma_C]

# ---- 复位 ----
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 rst_ps7_100M

# ---- 中断拼接（4 输入：DMA A/B/C + GEMM 自身完成中断）----
create_bd_cell -type ip -vlnv xilinx.com:ip:xlconcat:2.1 xlconcat_0
set_property CONFIG.NUM_PORTS {4} [get_bd_cells xlconcat_0]

# ---- 时钟：全部接 FCLK0 ----
connect_bd_net [get_bd_pins ps7/FCLK_CLK0] \
    [get_bd_pins ps7/M_AXI_GP0_ACLK] \
    [get_bd_pins gemm_top_0/ap_clk] \
    [get_bd_pins dma_A/s_axi_lite_aclk] \
    [get_bd_pins dma_A/m_axi_mm2s_aclk] \
    [get_bd_pins dma_B/s_axi_lite_aclk] \
    [get_bd_pins dma_B/m_axi_mm2s_aclk] \
    [get_bd_pins dma_C/s_axi_lite_aclk] \
    [get_bd_pins dma_C/m_axi_s2mm_aclk] \
    [get_bd_pins rst_ps7_100M/slowest_sync_clk]

# ---- 复位 ----
connect_bd_net [get_bd_pins ps7/FCLK_RESET0_N] \
    [get_bd_pins rst_ps7_100M/ext_reset_in]
connect_bd_net [get_bd_pins rst_ps7_100M/peripheral_aresetn] \
    [get_bd_pins gemm_top_0/ap_rst_n] \
    [get_bd_pins dma_A/axi_resetn] \
    [get_bd_pins dma_B/axi_resetn] \
    [get_bd_pins dma_C/axi_resetn]

# ---- AXI-Lite：GP0 → GEMM 控制 + 3 个 DMA 寄存器（自动复用互联）----
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/ps7/M_AXI_GP0} ddr_preserve {1} } [get_bd_intf_pins gemm_top_0/s_axi_ctrl_bus]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/ps7/M_AXI_GP0} ddr_preserve {1} } [get_bd_intf_pins dma_A/S_AXI_LITE]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/ps7/M_AXI_GP0} ddr_preserve {1} } [get_bd_intf_pins dma_B/S_AXI_LITE]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/ps7/M_AXI_GP0} ddr_preserve {1} } [get_bd_intf_pins dma_C/S_AXI_LITE]

# ---- 内存侧：DMA → HP 口（A→HP0, B→HP1, C→HP2）----
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/dma_A/M_AXI_MM2S} Slave {/ps7/S_AXI_HP0} ddr_preserve {1} } [get_bd_intf_pins ps7/S_AXI_HP0]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/dma_B/M_AXI_MM2S} Slave {/ps7/S_AXI_HP1} ddr_preserve {1} } [get_bd_intf_pins ps7/S_AXI_HP1]
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {Master {/dma_C/M_AXI_S2MM} Slave {/ps7/S_AXI_HP2} ddr_preserve {1} } [get_bd_intf_pins ps7/S_AXI_HP2]

# ---- AXI-Stream：DMA A/B → GEMM，GEMM → DMA C ----
connect_bd_intf_net [get_bd_intf_pins dma_A/M_AXIS_MM2S] [get_bd_intf_pins gemm_top_0/s_axis_A]
connect_bd_intf_net [get_bd_intf_pins dma_B/M_AXIS_MM2S] [get_bd_intf_pins gemm_top_0/s_axis_B]
connect_bd_intf_net [get_bd_intf_pins gemm_top_0/m_axis_C] [get_bd_intf_pins dma_C/S_AXIS_S2MM]

# ---- 中断：DMA A/B mm2s、DMA C s2mm、GEMM 完成 → concat → PS IRQ_F2P ----
connect_bd_net [get_bd_pins dma_A/mm2s_introut] [get_bd_pins xlconcat_0/In0]
connect_bd_net [get_bd_pins dma_B/mm2s_introut] [get_bd_pins xlconcat_0/In1]
connect_bd_net [get_bd_pins dma_C/s2mm_introut] [get_bd_pins xlconcat_0/In2]
connect_bd_net [get_bd_pins gemm_top_0/interrupt] [get_bd_pins xlconcat_0/In3]
connect_bd_net [get_bd_pins xlconcat_0/dout] [get_bd_pins ps7/IRQ_F2P]

# ---- 地址分配：AXI-Lite automation 已自动把外设分配到
#      gemm 0x40000000、dma_A/B/C 0x41E00000/0x41E10000/0x41E20000（各 64K）----
assign_bd_address

save_bd_design
validate_bd_design

# ---- 顶层封装 ----
make_wrapper -files [get_files $output_dir/${project_name}.srcs/sources_1/bd/gemm_soc/gemm_soc.bd] -top
add_files -norecurse $output_dir/${project_name}.srcs/sources_1/bd/gemm_soc/hdl/gemm_soc_wrapper.v
update_compile_order -fileset sources_1
set_property top gemm_soc_wrapper [current_fileset]

# ============================================================
# 综合 + 实现 + 比特流
# ============================================================
launch_runs synth_1 -jobs 4
wait_on_run synth_1

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

# ============================================================
# 导出三份报告到 build/gemm/
# ============================================================
open_run impl_1
report_utilization -file $gemm_out/gemm_utilization.rpt
report_timing_summary -file $gemm_out/gemm_timing.rpt
report_power -file $gemm_out/gemm_power.rpt

# 复制 bit/hwh 到 build/gemm/
file copy -force $output_dir/${project_name}.runs/impl_1/gemm_soc_wrapper.bit $gemm_out/gemm_soc.bit
file copy -force $output_dir/${project_name}.gen/sources_1/bd/gemm_soc/hw_handoff/gemm_soc.hwh $gemm_out/gemm_soc.hwh

puts "GEMM 工程重建完成：build/gemm/ 下 bit/hwh + utilization/timing/power 报告"
close_project
