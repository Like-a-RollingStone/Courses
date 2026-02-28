`timescale 1ns / 1ps
//////////////////////////////////////////////////////////////////////////////////
// Company: 
// Engineer: 
// 
// Create Date: 2025/11/22 12:26:37
// Design Name: 
// Module Name: register_32bit
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


module register_32bit(
    input wire clk,
    input [4:0] ReadRegister1, ReadRegister2,//读取寄存器的地址
    input [4:0] WriteRegister, //写入寄存器的地址
    input RegWrite, //写使能信号
    input [31:0] WriteData, //写入数据
    output [31:0] ReadData1, ReadData2 //读取数据
);
    reg[31:0] regs[31:0];//定义32*32存储器变量

    
    assign ReadData1 = (ReadRegister1==5'b0) ? 32'b0 : regs[ReadRegister1];//x0寄存器始终为0,端口1数据读出
    assign ReadData2 = (ReadRegister2==5'b0) ? 32'b0 : regs[ReadRegister2];//x0寄存器始终为0,端口2数据读出
    always @(posedge clk) begin//数据写入
        if(RegWrite) begin
            regs[WriteRegister] <= WriteData;
        end
    end
endmodule


module RAWregister(
    input wire clk,
    input [4:0] rs1Addr,rs2Addr,//读取寄存器的地址`
    input [4:0] WriteAddr, //写入寄存器的地址
    input RegWrite, //写使能信号
    input [31:0] WriteData, //写入数据
    output [31:0] rs1Data, rs2Data //读取数据
);
    wire rs1Sel, rs2Sel;
    assign rs1Sel = RegWrite && (WriteAddr != 5'b0) && (WriteAddr == rs1Addr);//30.1
    assign rs2Sel = RegWrite && (WriteAddr != 5'b0) && (WriteAddr == rs2Addr);//30.2
    wire [31:0] RBW_rdData1, RBW_rdData2;
    
    register_32bit RBWregister(
        .clk(clk),
        .ReadRegister1(rs1Addr),
        .ReadRegister2(rs2Addr),
        .WriteRegister(WriteAddr),
        .RegWrite(RegWrite),
        .WriteData(WriteData),
        .ReadData1(RBW_rdData1),
        .ReadData2(RBW_rdData2)
    );    
    assign rs1Data = rs1Sel ? WriteData : RBW_rdData1;
    assign rs2Data = rs2Sel ? WriteData : RBW_rdData2;
endmodule