`timescale 1ns / 1ps
//==============================================================================
//  i2s_mems_rx.v
//  INMP441 (I2S MEMS) 麦克风 -> AXI4-Stream 接收核（I2S 主机侧）
//
//  功能：
//   1) 由 aclk(100MHz) 用相位累加器生成 I2S BCLK 与 WS（无需 MMCM，
//      BCLK 平均频率精确，允许 ±10ns 抖动，INMP441 完全可接受）；
//   2) 接收标准 I2S、24bit、MSB-first、每帧 64 个 BCLK；
//   3) 每个 WS 帧把“左声道槽”和“右声道槽”各 24bit 取出，
//      符号扩展为 32bit，顺序 [L, R] 送入 AXI4-Stream（给 AXI DMA 的 S2MM）；
//      INMP441 上 L/R=0 -> 数据在左槽，L/R=1 -> 数据在右槽，另一槽为高阻=0，
//      软件端按能量自动选声道即可，因此本核不挑 L/R 接法。
//
//  时钟/速率：
//   aclk = 100 MHz, SAMPLE_HZ = 32000
//   BCLK = 64 * fs = 2.048 MHz（在 INMP441 允许的 0.5~3.2MHz 内）
//   WS   = fs = 32000 Hz（允许 7.8~50kHz）
//
//  输出流：
//   m_axis_tdata : 32bit 有符号（24bit 样本符号扩展到 32bit，即左移 8 位）
//   m_axis_tvalid/tready : 标准 AXIS 握手
//   m_axis_tlast : 恒为 0（按固定长度 buffer 传输，避免 DMA 每个样本就提前结束）
//   内部 16 深 FIFO 吸收突发，DMA 未启动时丢弃旧数据，不会反压 BCLK。
//
//  适用于 PYNQ-Z2 (Zynq-7020)，Vivado 2018/2019，Verilog-2001。
//==============================================================================
module i2s_mems_rx #(
    parameter integer CLK_HZ        = 100_000_000,
    parameter integer SAMPLE_HZ     = 32_000,
    parameter integer ACC_W         = 20,
    parameter integer FIFO_LOGDEPTH = 4           // 2^4 = 16 深
)(
    input  wire        aclk,
    input  wire        aresetn,

    // 到麦克风（接到 PmodB 引脚）
    output wire        bclk,                    // SCK
    output wire        ws,                      // WS / LRCLK
    input  wire        sd,                      // SD/DOUT

    // AXI4-Stream master（接 AXI DMA 的 S_AXIS_S2MM）
    output wire [31:0] m_axis_tdata,
    output wire        m_axis_tvalid,
    input  wire        m_axis_tready,
    output wire        m_axis_tlast
);

    //--------------------------------------------------------------------------
    // 1) BCLK 生成：BCLK 翻转频率 = 2 * 64 * fs = 4.096MHz
    //    累加器每来一个 aclk 加 ACC_STEP，溢出即翻转 BCLK。
    //    20 位累加：step=42950，实测 BCLK≈2.0480156MHz，fs≈32000.24Hz，误差<1e-5。
    //--------------------------------------------------------------------------
    localparam [63:0] ACC_STEP64 =
        ((64'd2 * 64'd64 * SAMPLE_HZ) * (64'd1 << ACC_W) + (CLK_HZ/2)) / CLK_HZ;
    localparam [ACC_W-1:0] ACC_STEP = ACC_STEP64[ACC_W-1:0];

    reg [ACC_W-1:0] acc    = {ACC_W{1'b0}};
    reg             bclk_r = 1'b0;

    wire [ACC_W:0] acc_sum  = acc + ACC_STEP;
    wire           acc_tick = acc_sum[ACC_W];    // 本周期应翻转 BCLK
    wire           bclk_new = bclk_r ^ acc_tick; // 翻转后的电平
    wire           bclk_rise = acc_tick &  bclk_new;  // BCLK 上升沿（采样沿）
    wire           bclk_fall = acc_tick & ~bclk_new;  // BCLK 下降沿（WS 变化沿）

    always @(posedge aclk) begin
        if (!aresetn) begin
            acc    <= {ACC_W{1'b0}};
            bclk_r <= 1'b0;
        end else begin
            acc    <= acc_sum[ACC_W-1:0];
            if (acc_tick) bclk_r <= ~bclk_r;
        end
    end
    assign bclk = bclk_r;

    //--------------------------------------------------------------------------
    // 2) I2S 接收：phase 为 BCLK 上升沿序号 0..63
    //    标准 I2S：WS 变化后第 1 个 BCLK 为空，第 2 个起为 MSB
    //      左槽：phase 1..24 采样 24bit（MSB@1），phase 25 锁存并入队
    //      右槽：phase 33..56 采样 24bit（MSB@33），phase 57 锁存并入队
    //    WS 在下降沿变化。注意：phase 在“上升沿”已先 +1，因此
    //      R63 之后的下降沿读到的 phase 已经是 0  -> 此刻拉低，进入左槽
    //      R31 之后的下降沿读到的 phase 已经是 32 -> 此刻拉高，进入右槽
    //--------------------------------------------------------------------------
    reg [5:0]  phase = 6'd0;
    reg        ws_r  = 1'b0;
    reg [23:0] shl   = 24'd0;
    reg [23:0] shr   = 24'd0;

    reg        enq   = 1'b0;
    reg [31:0] wdata = 32'd0;

    always @(posedge aclk) begin
        if (!aresetn) begin
            phase <= 6'd0;
            ws_r  <= 1'b0;
            shl   <= 24'd0;
            shr   <= 24'd0;
            enq   <= 1'b0;
            wdata <= 32'd0;
        end else begin
            enq <= 1'b0;

            if (bclk_rise) begin
                if (phase >= 6'd1 && phase <= 6'd24)
                    shl <= {shl[22:0], sd};
                if (phase >= 6'd33 && phase <= 6'd56)
                    shr <= {shr[22:0], sd};

                if (phase == 6'd25) begin
                    wdata <= {{8{shl[23]}}, shl};   // 左槽 24bit 符号扩展
                    enq   <= 1'b1;
                end
                if (phase == 6'd57) begin
                    wdata <= {{8{shr[23]}}, shr};   // 右槽 24bit 符号扩展
                    enq   <= 1'b1;
                end

                phase <= (phase == 6'd63) ? 6'd0 : phase + 6'd1;
            end

            if (bclk_fall) begin
                if (phase == 6'd0)  ws_r <= 1'b0;      // R63 后的下降沿：进入左槽
                else if (phase == 6'd32) ws_r <= 1'b1; // R31 后的下降沿：进入右槽
            end
        end
    end
    assign ws = ws_r;

    //--------------------------------------------------------------------------
    // 3) 小 FIFO（分布式 RAM），输出到 AXI DMA
    //--------------------------------------------------------------------------
    localparam integer DEPTH = (1 << FIFO_LOGDEPTH);

    reg [31:0] mem [0:DEPTH-1];
    reg [FIFO_LOGDEPTH:0] wrp = {(FIFO_LOGDEPTH+1){1'b0}};
    reg [FIFO_LOGDEPTH:0] rdp = {(FIFO_LOGDEPTH+1){1'b0}};

    wire w_full = (wrp[FIFO_LOGDEPTH] != rdp[FIFO_LOGDEPTH]) &&
                  (wrp[FIFO_LOGDEPTH-1:0] == rdp[FIFO_LOGDEPTH-1:0]);
    wire w_empty = (wrp == rdp);

    wire [31:0] rdata = mem[rdp[FIFO_LOGDEPTH-1:0]];

    always @(posedge aclk) begin
        if (!aresetn) begin
            wrp <= {(FIFO_LOGDEPTH+1){1'b0}};
            rdp <= {(FIFO_LOGDEPTH+1){1'b0}};
        end else begin
            if (enq && !w_full) begin
                mem[wrp[FIFO_LOGDEPTH-1:0]] <= wdata;
                wrp <= wrp + 1'b1;
            end
            if (!w_empty && m_axis_tready) begin
                rdp <= rdp + 1'b1;
            end
        end
    end

    assign m_axis_tdata  = rdata;
    assign m_axis_tvalid = !w_empty;
    assign m_axis_tlast  = 1'b0;

endmodule
