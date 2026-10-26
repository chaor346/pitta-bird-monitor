`timescale 1ns / 1ps
// ============================================================================
// I2S MEMS RX Testbench
// 验证 i2s_mems_rx 核：
//   - bclk / ws 由核自己生成（PL），testbench 只模拟 INMP441 驱动 sd
//   - 标准 I2S、24bit、MSB-first；核在左槽 phase1..24、右槽 phase33..56 采样
//   - 核把 24bit 符号扩展为 32bit，按 [L,R] 顺序输出到 AXI4-Stream
//   - m_axis_tlast 恒为 0
// 数据为确定性的"槽序号"模式，校验端按接收 beat 序号推算期望值，无并发竞争。
// 仿真需同时编译 src/fpga/i2s_mems_rx.v（见 sim/README.md）
// ============================================================================
module i2s_mems_rx_tb;

    parameter CLK_PERIOD = 10;
    parameter N_PAIRS    = 12;        // 校验 12 对 [L,R]
    parameter BACKPRESSURE = 1;       // 1=启用 AXI-Stream 反压（25% 周期 tready=0）

    reg aclk;
    initial aclk = 0;
    always #(CLK_PERIOD/2) aclk = ~aclk;

    reg aresetn;

    wire bclk, ws;                    // 核生成
    reg  sd;                          // testbench 驱动

    wire [31:0] m_axis_tdata;
    wire        m_axis_tvalid, m_axis_tlast;
    reg         m_axis_tready;

    // 反压计数器：每 4 个周期拉低 1 次 tready
    integer bp_cnt = 0;
    always @(posedge aclk) begin
        if (!aresetn) begin
            m_axis_tready <= 1;
            bp_cnt <= 0;
        end else if (BACKPRESSURE) begin
            bp_cnt <= bp_cnt + 1;
            // 每 4 拍里第 0 拍拉低，其余拉高；模拟下游偶尔堵
            m_axis_tready <= (bp_cnt[1:0] != 2'b00);
        end else begin
            m_axis_tready <= 1;
        end
    end

    reg [23:0] shifter;
    integer    bitpos;
    reg        ws_prev;
    integer    slot_no;

    integer frame_cnt;
    integer error_cnt;

    // 槽序号 -> 24bit 数据：左槽(ws=0) 0x100000+slot，右槽(ws=1) 0xE00000+slot
    function [23:0] slot_data;
        input integer sn;
        input         w;
        begin
            if (w == 1'b0) slot_data = 24'h100000 + sn;
            else           slot_data = 24'hE00000 + sn;
        end
    endfunction
    function [31:0] sign_extend;
        input [23:0] v;
        sign_extend = {{8{v[23]}}, v};
    endfunction

    i2s_mems_rx #(.SAMPLE_HZ(32000)) dut (
        .aclk(aclk), .aresetn(aresetn),
        .bclk(bclk), .ws(ws), .sd(sd),
        .m_axis_tdata(m_axis_tdata),
        .m_axis_tvalid(m_axis_tvalid),
        .m_axis_tready(m_axis_tready),
        .m_axis_tlast(m_axis_tlast)
    );

    // ------------------------------------------------------------------------
    // 模拟 INMP441：bclk 下降沿 #2 后更新 sd（核在上升沿采样）
    // 复位时 ws_prev=x，强制复位后第一个槽（ws 无下降沿）也能正确同步
    // ------------------------------------------------------------------------
    always @(negedge bclk) begin
        #2;
        if (aresetn && (ws !== ws_prev)) begin
            // 槽开始的这个下降沿：仅加载，R0 是 phase0 不采样
            if (ws_prev === 1'bx) slot_no = 0;
            else                  slot_no = slot_no + 1;
            shifter = slot_data(slot_no, ws);
            bitpos = 0;
        end else if (aresetn && bitpos < 24) begin
            // 随后 24 个下降沿：依次发 b23..b0，对应核 phase1..24
            sd = shifter[23];
            shifter = {shifter[22:0], 1'b0};
            bitpos = bitpos + 1;
        end
        ws_prev = ws;
    end

    // ------------------------------------------------------------------------
    // AXI4-Stream 接收校验：第 frame_cnt 个 beat 即槽 frame_cnt
    // ------------------------------------------------------------------------
    always @(posedge aclk) begin
        if (aresetn && m_axis_tvalid && m_axis_tready) begin
            if (m_axis_tlast !== 1'b0) begin
                $display("ERROR: tlast 应恒0, beat=%0d", frame_cnt);
                error_cnt = error_cnt + 1;
            end
            if (frame_cnt == 0) begin
                // beat0：复位后首个左槽，SD 驱动尚未与核自生成的 ws 完成沿同步，预期为空(0)
                if (m_axis_tdata !== 32'h00000000) begin
                    $display("ERROR: 启动空槽 beat0 期望=0 实际=%h", m_axis_tdata);
                    error_cnt = error_cnt + 1;
                end
            end else if (m_axis_tdata !== sign_extend(slot_data(frame_cnt, ws))) begin
                $display("ERROR: beat=%0d ws=%b 期望=%h 实际=%h",
                         frame_cnt, ws,
                         sign_extend(slot_data(frame_cnt, ws)), m_axis_tdata);
                error_cnt = error_cnt + 1;
            end
            frame_cnt = frame_cnt + 1;
        end
    end

    initial begin
        aresetn     = 0;
        m_axis_tready = 1;
        sd          = 0;
        shifter     = 0;
        bitpos      = 0;
        ws_prev     = 1'bx;        // 关键：强制首槽同步
        slot_no     = 0;
        frame_cnt   = 0;
        error_cnt   = 0;

        #(CLK_PERIOD*20);
        aresetn = 1;
        $display("=== 仿真开始（BACKPRESSURE=%0d）===", BACKPRESSURE);

        // 等 N_PAIRS 对发送并经 FIFO 排空（每槽 31.25us，反压下留足余量）
        #3000000;   // 3 ms

        $display("=== 仿真结束 ===");
        $display("接收 beats: %0d", frame_cnt);
        $display("错误数: %0d", error_cnt);
        if (error_cnt == 0 && frame_cnt >= N_PAIRS*2)
            $display("测试结果: PASS");
        else
            $display("测试结果: FAIL");
        $finish;
    end

    initial begin
        #(CLK_PERIOD*2000000);
        $display("ERROR: 仿真超时");
        $finish;
    end

endmodule
