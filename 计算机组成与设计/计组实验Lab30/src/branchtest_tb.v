`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2025/11/22 19:45:59
// Design Name: 
// Module Name: branchtest_tb
// Project Name: 
// Target Devices: 
// Tool Versions: 
// Description: 
// 
// Dependencies: 
// 
// Revision:
// Revision 0.01 - File Created
// Additional Comments:
// 
//////////////////////////////////////////////////////////////////////////////////

`timescale 1ns / 1ps

module BranchTest_tb;

    // 1. 信号定义
    reg [31:0] rs1Data;
    reg [31:0] rs2Data;
    reg SB_type;
    reg [2:0] funct3;
    wire Branch;

    // 2. 实例化待测模块
    BranchTest uut (
        .rs1Data(rs1Data),
        .rs2Data(rs2Data),
        .SB_type(SB_type),
        .funct3(funct3),
        .Branch(Branch)
    );

    // 定义 funct3 参数方便阅读
    localparam BEQ  = 3'b000;
    localparam BNE  = 3'b001;
    localparam BLT  = 3'b100;
    localparam BGE  = 3'b101;
    localparam BLTU = 3'b110;
    localparam BGEU = 3'b111;

    // 3. 自动化测试任务 (Task)
    // 这是一个帮手工具，用来简化代码
    task check_branch;
        input [31:0] val1;
        input [31:0] val2;
        input [2:0]  f3;
        input        expected_result;
        input [8*10:1] test_name; // 测试名称字符串
        begin
            rs1Data = val1;
            rs2Data = val2;
            funct3  = f3;
            SB_type = 1; // 始终开启分支指令类型
            #10; // 等待逻辑稳定
            if (Branch === expected_result) begin
                $display("[PASS] %s: %h vs %h, Op=%b, Got=%b", test_name, val1, val2, f3, Branch);
            end else begin
                $display("[FAIL] %s: %h vs %h, Op=%b, Expected=%b, Got=%b", test_name, val1, val2, f3, expected_result, Branch);
            end
        end
    endtask

    // 4. 测试流程
    initial begin
        $display("========== BranchTest Simulation Start ==========");
        
        // -----------------------------------------------------
        // 测试 BEQ (相等) 和 BNE (不相等)
        // -----------------------------------------------------
        // 10 == 10 -> BEQ 应跳(1), BNE 不跳(0)
        check_branch(32'd10, 32'd10, BEQ, 1, "BEQ_Equal");
        check_branch(32'd10, 32'd10, BNE, 0, "BNE_Equal");
        
        // 10 != 20 -> BEQ 不跳(0), BNE 应跳(1)
        check_branch(32'd10, 32'd20, BEQ, 0, "BEQ_NotEqual");
        check_branch(32'd10, 32'd20, BNE, 1, "BNE_NotEqual");

        // -----------------------------------------------------
        // 测试 BLT/BGE (有符号数比较)
        // -----------------------------------------------------
        // 10 < 20 (正数比正数)
        check_branch(32'd10, 32'd20, BLT, 1, "BLT_Pos_Pos");
        check_branch(32'd10, 32'd20, BGE, 0, "BGE_Pos_Pos");

        // -10 < 10 (负数比正数) -> -10 的补码是 FFFFFFF6
        check_branch(-32'd10, 32'd10, BLT, 1, "BLT_Neg_Pos");
        
        // 10 > -10 (正数比负数)
        check_branch(32'd10, -32'd10, BLT, 0, "BLT_Pos_Neg");
        check_branch(32'd10, -32'd10, BGE, 1, "BGE_Pos_Neg");

        // -----------------------------------------------------
        // 测试 BLTU/BGEU (无符号数比较)
        // -----------------------------------------------------
        // 注意：在无符号状态下-1 (0xFFFFFFFF) 是最大的数
        
        // 10 < 20 (普通情况)
        check_branch(32'd10, 32'd20, BLTU, 1, "BLTU_Small_Big");

        // 10 < -1 (即 10 < 4294967295) -> 应该成立
        check_branch(32'd10, -32'd1, BLTU, 1, "BLTU_Pos_MaxU");

        // -1 > 10 (即 MaxU > 10) -> BLTU 应该为 0
        check_branch(-32'd1, 32'd10, BLTU, 0, "BLTU_MaxU_Pos");
        check_branch(-32'd1, 32'd10, BGEU, 1, "BGEU_MaxU_Pos");

        // -----------------------------------------------------
        // 测试非分支指令 (SB_type = 0)
        // -----------------------------------------------------
        SB_type = 0;
        rs1Data = 32'd10;
        rs2Data = 32'd10;
        funct3 = BEQ;
        #10;
        if (Branch == 0) $display("[PASS] ");
        else $display("[FAIL] ");

        $stop;
    end

endmodule