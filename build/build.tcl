#!/usr/bin/env tcl
# Vivado 非项目模式构建脚本
# 用法: vivado -mode batch -source build.tcl
# 目标器件: xc7z020clg400-1 (PYNQ-Z2)

set project_name inmp441
set part xc7z020clg400-1
set output_dir ./output

file mkdir $output_dir

# 创建工程
create_project $project_name $output_dir -part $part -force

# 添加源码
add_files -norecurse ../src/fpga/i2s_mems_rx.v
add_files -fileset constrs_1 -norecurse ../src/fpga/inmp441_pmodb.xdc

# ============================================================
# 创建块图 (Block Design)
# ============================================================
create_bd_design "system"

# 创建 Zynq PS
create_bd_cell -type ip -vlnv xilinx.com:ip:processing_system7:5.5 processing_system7_0
apply_bd_automation -rule xilinx.com:bd_rule:processing_system7 -config {
    make_external "FIXED_IO, DDR"
    apply_board_preset "1"
    Master "Disable"
    Slave "Disable"
} [get_bd_cells processing_system7_0]

# 配置 PS: FCLK0 = 100MHz, M_AXI_GP0 使能
set_property -dict [list \
    CONFIG.FCLK_CLK0_FREQ {100000000} \
    CONFIG.M_AXI_GP0_FREQMHZ {100} \
] [get_bd_cells processing_system7_0]

# 创建 AXI DMA
create_bd_cell -type ip -vlnv xilinx.com:ip:axi_dma:7.1 axi_dma_0
set_property -dict [list \
    CONFIG.c_include_sg {0} \
    CONFIG.c_sg_include_stscntrl_strm {0} \
    CONFIG.c_include_mm2s {0} \
    CONFIG.c_include_s2mm {1} \
    CONFIG.c_s2mm_burst_size {256} \
    CONFIG.c_m_axi_s2mm_data_width {32} \
    CONFIG.c_s_axis_s2mm_tdata_width {32} \
] [get_bd_cells axi_dma_0]

# 创建 I2S 接收核 (自定义 IP)
create_bd_cell -type module -reference i2s_mems_rx i2s_mems_rx_0

# 创建复位
create_bd_cell -type ip -vlnv xilinx.com:ip:proc_sys_reset:5.0 proc_sys_reset_0

# 连接时钟
connect_bd_net [get_bd_pins processing_system7_0/FCLK_CLK0] \
    [get_bd_pins processing_system7_0/M_AXI_GP0_ACLK] \
    [get_bd_pins axi_dma_0/s_axi_lite_aclk] \
    [get_bd_pins axi_dma_0/m_axi_s2mm_aclk] \
    [get_bd_pins axi_dma_0/s_axis_s2mm_aclk] \
    [get_bd_pins i2s_mems_rx_0/aclk] \
    [get_bd_pins proc_sys_reset_0/slowest_sync_clk]

# 连接复位
connect_bd_net [get_bd_pins processing_system7_0/FCLK_RESET0_N] \
    [get_bd_pins proc_sys_reset_0/ext_reset_in]
connect_bd_net [get_bd_pins proc_sys_reset_0/peripheral_aresetn] \
    [get_bd_pins axi_dma_0/axi_resetn] \
    [get_bd_pins i2s_mems_rx_0/aresetn]

# 连接 AXI Lite (PS → DMA 寄存器)
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {
    Clk_master {Auto}
    Clk_slave {Auto}
    Clk_xbar {Auto}
    Master {/processing_system7_0/M_AXI_GP0}
    Slave {/axi_dma_0/S_AXI_LITE}
    ddr_preserve {1}
} [get_bd_intf_pins axi_dma_0/S_AXI_LITE]

# 连接 AXI Master (DMA → DDR)
apply_bd_automation -rule xilinx.com:bd_rule:axi4 -config {
    Clk_master {Auto}
    Clk_slave {Auto}
    Clk_xbar {Auto}
    Master {/axi_dma_0/M_AXI_S2MM}
    Slave {/processing_system7_0/S_AXI_HP0}
    ddr_preserve {1}
} [get_bd_intf_pins processing_system7_0/S_AXI_HP0]

# 连接 AXI-Stream (I2S → DMA S2MM)
connect_bd_intf_net [get_bd_intf_pins i2s_mems_rx_0/m_axis] \
    [get_bd_intf_pins axi_dma_0/S_AXIS_S2MM]

# 导出 I2S 外部引脚 (BCLK, WS, SD)
make_bd_pins_external [get_bd_pins i2s_mems_rx_0/bclk]
make_bd_pins_external [get_bd_pins i2s_mems_rx_0/ws]
make_bd_pins_external [get_bd_pins i2s_mems_rx_0/sd]

# 保存块图
save_bd_design
validate_bd_design

# 生成顶层封装
make_wrapper -files [get_files $output_dir/${project_name}.srcs/sources_1/bd/system/system.bd] -top
add_files -norecurse $output_dir/${project_name}.srcs/sources_1/bd/system/hdl/system_wrapper.v
update_compile_order -fileset sources_1
set_property top system_wrapper [current_fileset]

# ============================================================
# 综合 + 实现 + 生成比特流
# ============================================================
launch_runs synth_1 -jobs 4
wait_on_run synth_1

launch_runs impl_1 -to_step write_bitstream -jobs 4
wait_on_run impl_1

# 导出报告
open_run impl_1
report_utilization -file $output_dir/utilization.rpt
report_timing_summary -file $output_dir/timing.rpt
report_power -file $output_dir/power.rpt

# 复制 bit 和 hwh
file copy -force $output_dir/${project_name}.runs/impl_1/system_wrapper.bit ../inmp441.bit
file copy -force $output_dir/${project_name}.srcs/sources_1/bd/system/hw_handoff/system.hwh ../inmp441.hwh

puts "构建完成: inmp441.bit, inmp441.hwh"
close_project
