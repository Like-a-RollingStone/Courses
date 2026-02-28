#import "@local/tplt:0.3.0": *
#show: BL

#let course = [计算机组成与设计]
#let teacher = [唐奕、屈民军]
#let proj = [实验30 基于RV32I指令集的RISC-V微处理器设计]
#let proj-short = [RISC-V微处理器设计]

#zju-cover(
  course: course,
  proj-name: [Lab30 RISC-V微处理器设计],
  teacher: teacher,
)


#import "@preview/itemize:0.2.0" as el  
#show: el.default-enum-list 

#import "@preview/codelst:2.0.2":sourcecode

#set math.equation(numbering: "(30.1)")
#show math.equation.where(block: true): it => {
  if it.has("label") {
    if "-" == str(it.label) {
      counter(math.equation).update(n => n - 1)
      math.equation(it.body, block: true, numbering: none)
      return
    } else if "::" in str(it.label) {
      let (a, b) = str(it.label).split("::")
      counter(math.equation).update(n => n - 2)
      [#math.equation(it.body, block: true, numbering: _ => "(" + b + ")")#label(a)]
      return
    }
  }
  it
}

#show: RP.with(
  course: course,
  proj-name: proj-short,
)

/*
#exp-info-chart(
  course: course,
  exp-cate: [设计实验],
  teacher: teacher,

  exp-name: proj,
  where: [ ],
)
*/
#import "@preview/numbly:0.1.0": numbly
/*
#set heading(numbering: numbly(
  "{1}    ",
  "{1}.{2} ",
  "{1}.{2}.{3} ",
))
*/
#set par(first-line-indent: (amount: 2em, all: true))

#set enum(indent:2em)
#set list(indent:2em)

#set math.cases(gap: 0.7em)

#outline()

#pagebreak()
= 实验目的


1. 熟悉 RISC-V 指令系统。
2. 了解提高 CPU 性能的方法。
3. 掌握流水线 RISC-V 微处理器的工作原理。
4. 理解数据冒险、控制冒险的概念以及流水线冲突的解决方法。
5. 掌握流水线 RISC-V 微处理器的测试方法。
6. 了解用软件实现数字系统的方法。

= 实验任务与要求
== 基本要求
设计一个流水线 RISC-V 微处理器，具体要求如下所述。
1. 至少运行下列 RV32I 核心指令。
- 算术运算指令： add, sub, addi
- 逻辑运算指令： and, or, xor, slt, sltu, andi, ori, xori, slti, sltiu
- 移位指令： sll, srl, sra, slli, srli, srai
- 条件分支指令： beq, bne, blt, bge, bltu, bgeu
- 无条件跳转指令： jal, jalr
- 数据传送指令： lw, sw, lui, auipc
- 空指令： nop
2. 采用 5 级流水线技术，对数据冒险实现转发或阻塞功能。
3. 在 Nexys Video 开发系统中实现微处理器，要求 CPU 的运行速度大于25MHz。
== 扩展要求

- 要求设计的微处理器还能运行 lb, lh, lhu, lbu, lhu, lwu, sb, sh 或 sd 等字节、半字和双字数据传送指令。
- 要求设计的 CPU 增加异常（exception）、自陷（trap）、中断（interrupt）等处理方案。

= 实验设备

- 装有 Vivado 和 ModelSim SE 软件的计算机。
- Nexys Video 开发板一套。
- 带有 HDMI 接口的显示器一台。

= 实验内容
1. 从网络下载相关文件。
2. 编写指令译码单元 Decode 模块的 Verilog HDL 代码，并用 ModelSim 进行功能仿真。
3. 编写寄存器堆 Register 模块的 Verilog HDL 代码。
4. 编写 ID 模块 Verilog HDL 代码， ID.v 文件已给端口列表。
5. 编写 ALU 模块的 Verilog HDL 代码并用 ModelSim 进行功能仿真。
6. 编写执行单元 EX 模块的 Verilog HDL 代码， EX.v 文件已给端口列表。
7. 编写 IF 模块的 Verilog HDL 代码并用 ModelSim 进行功能仿真。
8. 打开 Vivado 文件夹下的 Risc5CPU.xpr 工程，生成符合 CPU 要求的数据存储器IP 内核。
9. 编写 CPU 顶层的 Verilog HDL 代码，并用 ModelSim 进行功能仿真。注意：由于存在 IP 内核，仿真时，需加仿真库，方法参考实验 3. 根据表 30.11 验证仿真结果。表格中显示的数据均为十六进制，表格中“-”表示此处值无意义。
10. 再次打开 Vivado 文件夹下的 Risc5CPU.xpr 工程，添加流水线 CPU 设计的全部代码，然后综合、实现和下载至 Nexys Video 开发板。
11. 连接带有 HDMI 接口的显示器，进行测试。首先将 SW0 置于低电平，使 RISC-VCPU 工作在“单步”运行模式。复位后，每按一下上边按键， RISC-V CPU 运行一步，记录下显示器上的结果，对照表 30.11 验证设计是否正确。

表30.11将在实验结果部分展示。




= 实验过程
== 指令译码模块(ID)
=== 寄存器堆(Registers)子模块
寄存器堆由 32 个 32 位寄存器组成，这些寄存器通过寄存器号进行读写存取。寄存器堆的原理框图如下图所示。因为读取寄存器不会更改其内容，故只需提供寄存器号即可读出该寄存器内容。读取端口采用数据选择器即可实现读取功能。应注意的是，0号寄存器为常数 0。
#image("寄存器堆原理框图.png",width:80%)

对于往寄存器里写数据，需要目标寄存器号（WriteRegister）、待写入数据（WriteData）、写允许信号（RegWrite）三个变量。上图中 5 位二进制译码器完成地址译码，其输出控制目标寄存器的写使能信号 EN，决定将数据 WriteData 写入哪个寄存器。
注意：用Verilog HDL 设计描述寄存器堆时，用存储器变量定义 32 个 32 位寄存器更方便。下面为描述寄存器堆核心语句。
#sourcecode[
```v
reg [31:0] regs [31:0]; // 定义 32*32 存储器变量
assign ReadData1 = (ReadRegister1 == 5'b0) ? 32'b0 : regs[ReadRegister1]; // 端口1读
assign ReadData2 = (ReadRegister2 == 5'b0) ? 32'b0 : regs[ReadRegister2]; // 端口2读
always @ (posedge clk) if (RegWrite) regs[WriteRegister] <= WriteData; // 数据写入
```]

在流水线型 CPU 设计中，寄存器堆设计还应解决三阶数据相关的数据转发问题。当满足三阶数据相关条件时，寄存器具有 Read After Write 特性。设计时，只需要在上图设计寄存器堆的基础上添加少量电路就可实现 Read After Write 特性，如下图所示。图中的 RBW_Registers 模块就是实现的 Read Before Write 寄存器堆。图中转发检测电路的输出表达式为：

$ "rs1Sel" = "RegWrite" \&\& ("WriteAddr"! = 0) \&\& ("WriteAddr" == "rs1Addr") $ <30.1>
$ "rs2Sel" = "RegWrite" \&\& ("WriteAddr"! = 0) \&\& ("WriteAddr" == "rs2Addr") $ <30.2>
#image("RAW寄存器堆.png",width: 80%)


#sourcecode[
```v
`timescale 1ns / 1ps
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
```
]

*代码设计解析*

寄存器堆部分首先用二维寄存器数组实现32×32通用寄存器文件，并对x0寄存器做特殊处理保证其始终为0。

在此基础上RAWregister模块通过rs1Sel、rs2Sel控制信号在满足RegWrite且写地址与读地址相等时直接旁路写回数据，从而实现Read-Before-Write的数据前推，在不改变时钟结构的前提下降低了三阶数据相关引起的流水线停顿。



=== 指令译码(Decode)及立即数产生电路子模块
Decode 模块包括译码部分，主要功能是对指令进行译码，将指令的操作码和立即数提取出来，还包括 ALUcode 的生成，用于 ALU 模块的控制和立即数产生电路的设计，其设计原理如下所示。
RISC-V 将指令分为 R_type、 I_type、 S_type、 U_type、 SB_type、 U_type 等六类。从电路设计角度看，根据操作数的来源和立即数构成方式不同，再次细分指令如下：

-  R_type 类：操作码（opcode，简称 op）为 7’h33， R 类的所有指令，两个操作数分别为 rs1 和 rs2；

-  I_type 类：操作码 7’h13， I 类的算术逻辑运算指令和移位指令，两个操作数分别为 rs1 和立即数 imm；

-  LW 指令：操作码 7’h03， I 类的数据传送指令 lw，两个操作数分别为 rs1 和立即数 imm；

-  JALR 指令：操作码 7’h67， I 类的无条件分支指令 jalr，两个操作数分别为 PC 和常数 4；

-  SW 指令：操作码 7’h23， S 类的数据传送指令 sw，两个操作数分别为 rs1 和立即数 imm；

-  SB_type 类：操作码 7’h63， SB 类的所有指令，两个操作数分别为 PC 和立即数imm；

-  LUI 指令：操作码 7’h37， U 类的数据传送指令 lui，只有一个操作数（立即数 imm）；

-  AUIPC 指令：操作码 7’h17， U 类的数据传送指令 auipc，两个操作数分别为 PC和立即数 imm；

-  JAL 指令：操作码 7’h6f， U 类的无条件分支指令 jal，两个操作数分别为 PC 和常数 4。

因此，设置 R_type、 I_type、 SB_type、 LW、 JALR、 SW、 LUI、 AUIPC和 JAL 等变量来表示指令类型，各变量的值由下式决定：

$ "R_type" = ("op" == "R_type_op")\
"I_type" = ("op" == "I_type_op")\
"SB_type" = ("op" == "SB_type_op")\
"LW" = ("op" == "LW_op")\
"JALR" = ("op" == "JALR_op")\
"SW" = ("op" == "SW_op")\
"LUI" = ("op" == "LUI_op")\
"AUIPC" = ("op" == "AUIPC_op")\
"JAL" = ("op" == "JAL_op") $

1. 只有 LW 指令读取存储器且回写数据取自存储器，所以有：
$ "MemtoRead" = "LW"\
"MemRead" = "LW" $
2. 只有 SW 指令会对存储器写数据，所以有
$ "MemWrite" = "SW" $
3. 需要进行回写的指令类型有 R_type、 I_type、 LW、 JALR、 LUI、 AUIPC 和 JAL。所以有：
$ "RegWrite" = "R_type" || "I_type" || "LW" || "JALR" || "LUI" || "AUIPC" || "JAL" $
4. 只有 JALR 和 JAL 两条无条件分支指令，所以有：
$ "Jump" = "JALR" || "JAL" $
5. 操作数 A 和 B 的选择信号的确定
分析各类指令，可得到表 30.4 操作数选择的功能表。
#image("表30.4.png",width:80%)

从上表可获得 ALUSrcA_id 和 ALUSrcB_id[1:0] 表达式：
$ "ALUSrcA" = "JALR" || "JAL" || "AUIPC" \
"ALUSrcB[1]" = "JAL" || "JALR" \
"ALUSrcB[0]" =~ ("R_type" || "JAL" || "JALR") $

6. ALUCode 的确定
除了条件分支指令，其它指令都需要 ALU 执行运算，共有 11 种不同运算，ALUCode信号需用 4 位二进制表示。最主要为加法运算，设为默认算法，ALUCode 的功能表如下所示。注意：表中`funct7[6]`与`funct6[5]`在指令中为同一位置，即`instruction[30]`。
#image("表30.5.png",width:88%)

7. 立即数产生电路 (ImmGen) 设计
L_type、 SB_type、 LW、 JALR、 SW、 LUI、 AUIPC 和 JAL 这几类指令均用到立即数。
由于 L_type 的算术逻辑运算与移位运算指令的立即数构成方法不同，这里再设定一个变量 Shift 来区分两者。 Shift=1 表示移位运算，否则为算术逻辑运算。 Shift 值由式 (30.11) 计算。

$ "Shift" = ("funct3" == 1) || ("funct3" == 5) $ <eq:some::30.11>
立即数构成和扩展方法如下所示。
#image("表30.6.png",width:80%)

#sourcecode[
```v
//**********************************************************************
// //
// Decode.v
//**********************************************************************

module Decode(   
	// Outputs
	MemtoReg, RegWrite, MemWrite, MemRead,ALUCode,ALUSrcA,ALUSrcB,Jump,JALR,Imm,offset,
	// Inputs
    Instruction);
	input [31:0]   Instruction;	// current instruction
	output		   MemtoReg;		// use memory output as data to write into register
	output		   RegWrite;		// enable writing back to the register
	output		   MemWrite;		// write to memory
	output         MemRead;
	output [3:0]   ALUCode;         // ALU operation select
	output         ALUSrcA;
	output [1:0]   ALUSrcB;
	output         Jump;
	output         JALR;
	output[31:0]   Imm,offset;
	
//**********************************************************************
//  instruction type decode
//**********************************************************************
	parameter  R_type_op=   7'b0110011;
	parameter  I_type_op=   7'b0010011;
	parameter  SB_type_op=  7'b1100011;
	parameter  LW_op=       7'b0000011;
	parameter  JALR_op=     7'b1100111;
	parameter  SW_op=       7'b0100011;
	parameter  LUI_op=      7'b0110111;
	parameter  AUIPC_op=    7'b0010111;	
	parameter  JAL_op=      7'b1101111;	
//
  //
    parameter  ADD_funct3 =     3'b000 ;
    parameter  SUB_funct3 =     3'b000 ;
    parameter  SLL_funct3 =     3'b001 ;
    parameter  SLT_funct3 =     3'b010 ;
    parameter  SLTU_funct3 =    3'b011 ;
    parameter  XOR_funct3 =     3'b100 ;
    parameter  SRL_funct3 =     3'b101 ;
    parameter  SRA_funct3 =     3'b101 ;
    parameter  OR_funct3 =      3'b110 ;
    parameter  AND_funct3 =     3'b111;
    //
    parameter  ADDI_funct3 =     3'b000 ;
    parameter  SLLI_funct3 =     3'b001 ;
    parameter  SLTI_funct3 =     3'b010 ;
    parameter  SLTIU_funct3 =    3'b011 ;
    parameter  XORI_funct3 =     3'b100 ;
    parameter  SRLI_funct3 =     3'b101 ;
    parameter  SRAI_funct3 =     3'b101 ;
    parameter  ORI_funct3 =      3'b101 ;
    parameter  ANDI_funct3 =     3'b111;
    //
    parameter	 alu_add=  4'b0000;
    parameter	 alu_sub=  4'b0001;
    parameter	 alu_lui=  4'b0010;
    parameter	 alu_and=  4'b0011;
    parameter	 alu_xor=  4'b0100;
    parameter	 alu_or =  4'b0101;
    parameter 	 alu_sll=  4'b0110;
    parameter	 alu_srl=  4'b0111;
    parameter	 alu_sra=  4'b1000;
    parameter	 alu_slt=  4'b1001;
    parameter	 alu_sltu= 4'b1010; 

//**********************************************************************
// instruction field
//**********************************************************************
	wire [6:0]		op;
	wire  	 	    funct76_65;
	wire [2:0]		funct3;
	assign op			= Instruction[6:0];
	assign funct76_65		= Instruction[30];
 	assign funct3		= Instruction[14:12];
	
	//细分指令类型
    wire R_type, I_type, SB_type, LW, SW, LUI, AUIPC, JAL;
    assign R_type = (op == R_type_op);
    assign I_type = (op == I_type_op);
    assign SB_type = (op == SB_type_op);
    assign LW = (op == LW_op);
    assign JALR = (op == JALR_op);
    assign SW = (op == SW_op);
    assign LUI = (op == LUI_op);
    assign AUIPC = (op == AUIPC_op);
    assign JAL = (op == JAL_op);
  //只有LW读取内存且回写数据取自寄存器
    assign MemtoReg = LW;
    assign MemRead = LW;
  //只有SW写内存
    assign MemWrite = SW;
  //需要写回的指令
    assign RegWrite = R_type || I_type || LW || JALR || LUI || AUIPC || JAL;
  //无条件跳转
    assign Jump = JAL || JALR;
  //操作数A和B的选择信号的确定，来自表30.4
    assign ALUSrcA = JALR || JAL || AUIPC;
    assign ALUSrcB[1]=JAL || JALR;
    assign ALUSrcB[0]=~(R_type || JAL || JALR);


//ALUcode的确定，来自表30.5
    reg [3:0] ALUCode_temp;
    always @(*) begin
        casez ({R_type,I_type,LUI,funct3,funct76_65})
            7'b100_000_0: ALUCode_temp = 4'd0; //加
            7'b100_000_1: ALUCode_temp = 4'd1; //减
            7'b100_001_0: ALUCode_temp = 4'd6; //左移
            7'b100_010_0: ALUCode_temp = 4'd9; //A<B?1:0
            7'b100_011_0: ALUCode_temp = 4'd10; //A<B?1:0（无符号）
            7'b100_100_0: ALUCode_temp = 4'd4; //异或
            7'b100_101_0: ALUCode_temp = 4'd7; //右移
            7'b100_101_1: ALUCode_temp = 4'd8; //算术右移
            7'b100_110_0: ALUCode_temp = 4'd5; //或
            7'b100_111_0: ALUCode_temp = 4'd3; //与
        //Immediate
            7'b010_000_?: ALUCode_temp = 4'd0; //加
            7'b010_001_?: ALUCode_temp = 4'd6; //左移
            7'b010_010_?: ALUCode_temp = 4'd9; //A<B?1:0
            7'b010_011_?: ALUCode_temp = 4'd10; //A<B?1:0（无符号）
            7'b010_100_?: ALUCode_temp = 4'd4; //异或
            7'b010_101_0: ALUCode_temp = 4'd7; //右移
            7'b010_101_1: ALUCode_temp = 4'd8; //算术右移
            7'b010_110_?: ALUCode_temp = 4'd5; //或
            7'b010_111_?: ALUCode_temp = 4'd3; //与
            7'b001_???_?: ALUCode_temp = 4'd2; //送数：ALUResult=B
        //其它
            default: ALUCode_temp = 4'd0; //加
        endcase
    end
    assign ALUCode = ALUCode_temp;

    //立即数
    //设置Shift信号
    wire Shift;
    assign Shift=(funct3==3'b001)||(funct3==3'b101);
    
    reg [31:0] Imm_temp,offset_temp;
    //Imm产生方法，来自表30.6a
    always @(*) begin
        if (I_type==1 && Shift==1)begin
          Imm_temp = { 27'd0, Instruction[24:20] }; //shift
        end
        else if (I_type==1 && Shift==0)begin
          Imm_temp = { {20{Instruction[31]}}, Instruction[31:20] }; //immediate
        end
        else if (LW==1) begin
          Imm_temp = { {20{Instruction[31]}}, Instruction[31:20] }; //load
        end
        else if (SW==1)begin
          Imm_temp = { {20{Instruction[31]}}, Instruction[31:25], Instruction[11:7] }; //store
        end
        else if (LUI==1)begin
          Imm_temp = { Instruction[31:12], 12'd0 }; //LUI
        end
        else if (AUIPC==1)begin
          Imm_temp = { Instruction[31:12], 12'd0 }; //AUIPC
        end
        else begin
          Imm_temp = 32'b0;//default
        end
    end
    //offset产生方法，来自表30.6b
    always @(*) begin
        if (JALR==1) begin
          offset_temp = { {20{Instruction[31]}}, Instruction[31:20] }; //JALR
        end
        else if (JAL==1) begin
          offset_temp = { {11{Instruction[31]}}, Instruction[31], Instruction[19:12], Instruction[20], Instruction[30:21], 1'b0 }; //JAL
        end
        else if (SB_type==1) begin
          offset_temp = { {19{Instruction[31]}}, Instruction[31], Instruction[7], Instruction[30:25], Instruction[11:8], 1'b0 }; //SB
        end
        else begin
          offset_temp = 32'b0; //default
        end
    end
    
    
    assign Imm=Imm_temp;
    assign offset=offset_temp;
	 
endmodule
```
]

*代码设计解析*


首先从指令的低7位提取opcode、第30位提取funct7[6]、第[14:12]位提取funct3，这三个字段构成译码的主要依据。

随后与预定义的操作码常量比较生成R_type、I_type、SB_type等九个指令类型信号，每个信号仅在对应指令类型时为高，便于后续用组合逻辑直接推导控制信号。在控制信号生成部分，MemtoReg和MemRead只在LW时置1，MemWrite只在SW时置1，RegWrite则涵盖所有需要写回寄存器的指令类型（R_type、I_type、LW、JALR、LUI、AUIPC、JAL），Jump信号由JAL和JALR两类无条件跳转指令触发；操作数选择信号ALUSrcA在PC相关指令（JALR、JAL、AUIPC）时为1表示选PC，ALUSrcB[1:0]通过两级组合区分寄存器rs2、立即数Imm和常数4三种来源，这套控制信号确保了各类指令在流水线后续级能以统一的数据通路执行。

ALUCode的生成采用casez结构，将R_type、I_type、LUI三个类型标志与funct3、funct7[6]拼接成7位判断码，通过模式匹配为11种不同运算分配4位编码；特别地，LUI指令编码为alu_lui使ALU直接输出B操作数，移位类I指令根据funct7[6]区分逻辑右移与算术右移，而默认情况统一为加法。

立即数生成分为Imm和offset两路：Imm路径用Shift信号区分I_type中的移位指令（零扩展5位移位量）与算术逻辑指令（符号扩展12位立即数），同时处理LW/SW的12位偏移、LUI/AUIPC的高20位拼接；offset路径专门服务于跳转与分支，对JALR做符号扩展12位、对JAL按UJ格式重排20位并左移1位、对SB_type按SB格式重排12位并左移1位，末位补0保证跳转地址字对齐。

整个设计通过将指令格式差异集中在这两个always块中处理，使得后续EX级可以用统一的加法器完成地址计算，同时译码级的组合逻辑延迟被限制在casez查找表和立即数拼接路径上。


* 仿真验证 *


运行已经给出的Decode模块的仿真代码：
#image("仿真结果/decode.png")
结果如图所示，该模块正常运行。


=== 分支检测(Branch Test)电路
分支检测电路主要用于判断分支条件是否成立，在 Verilog HDL 可以用比较运算符号“>”、“<”和“==”描述，但要注意符号数和无符号数的处理方法不同。在这里，我们用加法器来实现。
1. 用一个 32 位加法器完成 $"rs1Data" + (-"rs2Data") + 1$ $("即" "rs1Data" - "rs2Data")$，设结果为 $"sum[31:0]"$。

2. 确定比较运算的结果。对于比较运算来说，如果最高位不同，即 $"rs1Data[31]" eq.not "rs2Data[31]"$，可根据 rs1Data[31]、 rs2Data[31] 决定比较结果，但是应注意符号数、无符号数的最高位 rs1Data[31]、 rs2Data[31] 代表意义不同。若两数最高位相同，则两数之差不会溢出，所以比较运算结果可由两个操作数之差的符号位 $"sum[31]"$ 决定。

在符号数比较运算中， $"rs1Data" < "rs2Data"$ 有以下两种情况：
1. rs1Data 为负数，rs2Data 为 0 或正数：$ "(rs1Data[31]" \&\& (~ "rs2Data[31]")) $

2. rs1Data、rs2Data 符号相同，sum 为负： $ ("rs1Data[31]" ~ "rs2Data[31]") \&\& "sum[31]" $

因此，符号数 $"rs1Data" < "rs2Data"$ 比较运算结果为：
$ "isLT" = ("rs1Data[31]" \&\& (~ "rs2Data[31]")) || (("rs1Data[31]" ~ "rs2Data[31]") \&\& "sum"[31]) $

同样地，无符号数比较运算中，$"rs1Data" < "rs2Data"$ 有以下两种情况：
1. rs1Data 最高位为0、 rs2Data 最高位为1：$ (~ "rs1Data[31]") \&\& "rs2Data[31]" $

2. rs1Data、rs2Data 最高位相同，sum为负：$ ("rs1Data[31]"~"rs2Data[31]") \& \& "sum[31]" $

因此，无符号数比较运算结果为：
$ "isLTU" = ((~ "rs1Data[31]") \&\& "rs2Data[31]") || (("rs1Data[31]" ~ "rs2Data[31]") \&\& "sum[31]" $

最后用数据选择器, 即可完成分支检测。


$ "Branch" = cases(
  &not ("sum[31 : 0]") \,&"SB_type" &and ("funct3" &== "beq_funct3"),
  &("sum[31 : 0]")\,   &"SB_type" &and ("funct3" &== "bne_funct3"),
  &"isLT"   \,          &"SB_type" &and ("funct3" &== "blt_funct3"),
  &not"isLT"\,          &"SB_type"&and ("funct3" &== "bge_funct3"),
  &"isLTU"    \,       &"SB_type" & and ("funct3" &== "bltu_funct3"),
  &not"isLTU" \,        &"SB_type" &and ("funct3" &== "bgeu_funct3"),
  &0   \,              &"others"
)
$

#sourcecode[
```v
module BranchTest (
    input wire [31:0] rs1Data,
    input wire [31:0] rs2Data,
    input wire SB_type,
    input wire [2:0] funct3,
    output wire Branch
);
    // 比较两个操作数的大小
    wire isLT, isLTU;
    wire [31:0] sum;
    assign sum = rs1Data + ~rs2Data + 1;
    assign isLT = rs1Data[31] && (~rs2Data[31]) || (rs1Data[31] ~^ rs2Data[31]) && sum[31];
    assign isLTU = (~rs1Data[31]) && rs2Data[31] || (rs1Data[31] ~^ rs2Data[31]) && sum[31];
    reg Branch_temp;

    // 定义 funct3 的值
    localparam beq_funct3 = 3'b000;
    localparam bne_funct3 = 3'b001;
    localparam blt_funct3 = 3'b100;
    localparam bge_funct3 = 3'b101;
    localparam bltu_funct3 = 3'b110;
    localparam bgeu_funct3 = 3'b111;
    // 分支检测（30.14）
    always @(*) begin
        if (SB_type == 1 && funct3 == beq_funct3) begin
            Branch_temp = ~(|sum[31:0]);
        end
        else if (SB_type == 1 && funct3 == bne_funct3) begin
            Branch_temp = |sum[31:0];
        end
        else if (SB_type == 1 && funct3 == blt_funct3) begin
            Branch_temp = isLT;
        end
        else if (SB_type == 1 && funct3 == bge_funct3) begin
            Branch_temp = ~isLT;
        end
        else if (SB_type == 1 && funct3 == bltu_funct3) begin
            Branch_temp = isLTU;
        end
        else if (SB_type == 1 && funct3 == bgeu_funct3) begin
            Branch_temp = ~isLTU;
        end
        else begin
            Branch_temp = 0;
        end
    end
    // 赋值输出信号
    assign Branch = Branch_temp;
endmodule
```
]
*代码设计解析*


利用加法器计算rs1Data-rs2Data得到sum，并从符号位组合出有符号比较结果isLT和无符号比较结果isLTU，在此基础上根据SB_type和funct3区分六类分支指令，对应生成是否跳转的Branch信号。由于整个比较过程完全是组合逻辑，Branch 信号可以在 ID/EX 之间尽早形成，与分支偏移量一起参与 PC 选择，从而兼顾了控制路径的时序和硬件资源的复用。


=== 冒险检测(Hazard Detector)功能电路
由前面分析可知，冒险成立的条件为：

1. 上一条指令必须是 lw 指令$("MemRead_ex=1")$；

2. 两条指令读写同一个寄存器$("rdAddr_ex"="rs1Addr_id" "或" "rdAddr_ex"="rs2Addr_id")$。

当冒险成立应清空 ID/EX 寄存器并且阻塞流水线 ID 级、 IF 级流水线，所以有：
$ "Stall"=(("rdAddr_ex" == "rs1Addr_id") || ("rdAddr_ex" == "rs2Addr_id")) \&\& "MemRead_ex" $
$ "IFWrite" = ~ "Stall" $
在用 VerilogHDL 描述 ID 模块时，冒险检测功能电路（Hazard Detector）等功能单元比较简单，直接在 ID 顶层描述。


=== ID顶层
已经给出ID顶层接口如下：
#image("表30.3.png",width:88%)
参考总电路图，ID模块总体电路如下：
#image("ID顶层.png",width:64%)
最终设计ID顶层如下：

#sourcecode[
```v
module ID(clk,Instruction_id, PC_id, RegWrite_wb, rdAddr_wb, RegWriteData_wb, MemRead_ex, 
          rdAddr_ex, MemtoReg_id, RegWrite_id, MemWrite_id, MemRead_id, ALUCode_id, 
			 ALUSrcA_id, ALUSrcB_id,  Stall, Branch, Jump, IFWrite,  JumpAddr, Imm_id,
			 rs1Data_id, rs2Data_id,rs1Addr_id,rs2Addr_id,rdAddr_id);
    input clk;
    input [31:0] Instruction_id;
    input [31:0] PC_id;
    input RegWrite_wb;
    input [4:0] rdAddr_wb;
    input [31:0] RegWriteData_wb;
    input MemRead_ex;
    input [4:0] rdAddr_ex;
    output MemtoReg_id;
    output RegWrite_id;
    output MemWrite_id;
    output MemRead_id;
    output [3:0] ALUCode_id;
    output ALUSrcA_id;
    output [1:0]ALUSrcB_id;
    output Stall;
    output Branch;
    output Jump;
    output IFWrite;
    output [31:0] JumpAddr;
    output [31:0] Imm_id;
    output [31:0] rs1Data_id;
    output [31:0] rs2Data_id;
	output[4:0] rs1Addr_id, rs2Addr_id, rdAddr_id;
 
    //内部信号定义
    wire JALR;
    wire [31:0]offset_id;
    wire SB_type_id;
    wire [2:0] funct3_id;
    assign SB_type_id = (Instruction_id[6:0] == 7'b1100011);
    assign funct3_id = Instruction_id[14:12];

    assign rs1Addr_id = Instruction_id[19:15];
    assign rs2Addr_id = Instruction_id[24:20];
    assign rdAddr_id = Instruction_id[11:7];
    //实例化RAW寄存器堆模块
    RAWregister registers(
        .clk(clk),
        .rs1Addr(rs1Addr_id),
        .rs2Addr(rs2Addr_id),
        .WriteAddr(rdAddr_wb),
        .RegWrite(RegWrite_wb),
        .WriteData(RegWriteData_wb),
        .rs1Data(rs1Data_id),
        .rs2Data(rs2Data_id)
    );
    //实例化译码模块
    Decode Decode_inst(
        .Instruction(Instruction_id),
        .JALR(JALR),
        .MemtoReg(MemtoReg_id),
        .RegWrite(RegWrite_id),
        .MemWrite(MemWrite_id),
        .MemRead(MemRead_id),
        .ALUCode(ALUCode_id),
        .ALUSrcA(ALUSrcA_id),
        .ALUSrcB(ALUSrcB_id),
        .Imm(Imm_id),
        .Jump(Jump),
        .offset(offset_id)
    );
    //实例化分支测试模块
     BranchTest BranchTest_inst(
        .rs1Data(rs1Data_id),
        .rs2Data(rs2Data_id),
        .SB_type(SB_type_id),
        .funct3(funct3_id),
        .Branch(Branch)
    );
    //计算跳转地址
    assign JumpAddr = (JALR == 1) ? (rs1Data_id + offset_id) : (PC_id + offset_id);
    //冒险检测电路
    assign Stall = ((rdAddr_ex == rs1Addr_id) || (rdAddr_ex == rs2Addr_id)) && MemRead_ex && (rdAddr_ex != 5'b0);
    assign IFWrite = ~Stall; 


 
endmodule
```
]
*代码设计解析*


通过RAWregister实现寄存器堆与写回级的紧耦合，先完成读寄存器和三阶数据前推，再由Decode模块产生控制信号和立即数、偏移量，同时将rs1/rs2/rd地址和PC等信息送入后级。

BranchTest根据解码出的SB_type和funct3在ID级及早判断分支是否成立，结合JALR/JAL产生的Jump和offset计算JumpAddr，从而尽量减少错误取指带来的流水线冲刷。Stall与IFWrite逻辑在检测到load-use冒险且rd≠x0时阻塞前两级，实现了对数据冒险的硬件屏蔽。


== 执行模块(EX)
=== ALU子模块
算术逻辑运算单元（ALU）提供 CPU 的基本运算能力，如加、减、与、或、比较、移位等。具体而言， ALU 输入为两个操作数 A、 B 和控制信号 ALUCode，由控制信号ALUCode 决定采用何种运算，运算结果为 ALUResult。 ALU 的功能表如下图所示。
#image("表30.8.png",width:80%)

如图所示， ALU 需执行多种运算，为了提高运算速度，本设计可同时进行各种运算，再根据 ALUCode 信号选出所需结果。 ALU 的基本结构如下图所示。
#image("ALU结构图.png",width:65%)


*加、减电路的设计考虑：*

减法、比较（slt、 sltu）均可用加法器和必要辅助电路来实现。图 30.10 中的 Binvert信号控制加减运算：若 Binvert 信号为低电平，则实现加法运算： sum=A+B；若 Binvert信号为高电平，则电路为减法运算 sum=A-B。除加法外，减法、比较和分支指令都应使电路工作在减法状态，所以：

$ "Binvert" =~ ("ALUCode" == 0) $

最后要强调的是，32 位加法器的运算速度决定了RISC-V微处理器的时钟信号频率的高低，因此设计一个高速的32位加法器尤为重要。32位加法器可采用实验8介绍的进位选择加法器。

*比较电路的设计考虑：*

比较电路的设计方法已经在分支检测电路介绍，参考式 (30.12) 和式 (30.13) 可确定
slt 和 sltu 两条件的比较结果。

*算术右移运算电路的设计考虑：*

算术右移对有符号数而言，移出的高位补符号位而不是 0。每右移一位相当于除以 2。例如，有符号数负数 101001100(-76) 算术右移两位结果为 111010001(-19)，正数01100111(103) 算术右移一位结果为 000110011(51)。Verilog HDL 的算术右移的运算符是“»”。

要实现算术右移应注意，被移位的对象必须定义是 reg 类型，但是在 sra 指令，被移位的对象操作数 A 为输入信号，不能定义为 reg 类型。因此，必须引入 reg 类型中间变量 A_reg，相应的 Verilog HDL 语句为

#sourcecode[
```v
reg signed[31:0] A_reg;
always @(*) begin A_reg = A; end
```]
引入 reg 类型的中间变量 A_reg 后，就可对 A_reg 进行算术右移操作。

最终设计ALU模块如下：

#sourcecode[
```Verilog
module ALU (
	// Outputs
	   ALUResult,
	// Inputs
	   ALUCode, A, B);
	input [3:0]	ALUCode;				// Operation select
	input [31:0]	A, B;
	output [31:0]	ALUResult;
	
// Decoded ALU operation select (ALUsel) signals
   parameter	 alu_add=  4'b0000;
   parameter	 alu_sub=  4'b0001;
   parameter	 alu_lui=  4'b0010;
   parameter	 alu_and=  4'b0011;
   parameter	 alu_xor=  4'b0100;
   parameter	 alu_or =  4'b0101;
   parameter 	 alu_sll=  4'b0110;
   parameter	 alu_srl=  4'b0111;
   parameter	 alu_sra=  4'b1000;
   parameter	 alu_slt=  4'b1001;
   parameter	 alu_sltu= 4'b1010; 	

   //定义内部信号
   wire Binvert;
   wire [31:0] b, sum, d3, d4, d5, d6, d7, d8, d9, d10;
   reg signed [31:0] A_reg;
   reg [31:0] out;
   //加减控制  
   assign Binvert = ~(ALUCode==0);
   //位拓展
   assign b = {32{Binvert}} ^ B;
   //加法器
   adder_32bits adder_32bits_ALUinst (
      .a(A),
      .b(b),
      .ci(Binvert),
      .s(sum),
      .co()
   );
   
//   //d3 and
//   assign d3 = A & B;
//   //d4 xor
//   assign d4 = A ^ B;
//   //d5 or
//   assign d5 = A | B;
//   //d6 sll
//   assign d6 = A << B[4:0];
//   //d7 srl
//   assign d7 = A >> B[4:0];
   
   //d8 sra
   always @(*) begin 
       A_reg = A; 
   end
   assign d8 = A_reg >>> B[4:0];
   //d9 slt
   assign d9 = A[31] && (~B[31]) || (A[31]~^B[31]) && sum[31];
   //d10 sltu
   assign d10 = (~A[31]) && B[31] || (A[31]~^B[31]) && sum[31];

   //选择输出
    always @(*) begin
        case (ALUCode)
            alu_add, alu_sub: out = sum;
            alu_lui:          out = B;
            alu_and:          out = A & B;
            alu_xor:          out = A ^ B;
            alu_or:           out = A | B;
            alu_sll:          out = (A << B[4:0]);
            alu_srl:          out = (A >> B[4:0]);
            alu_sra:          out = d8; 
            alu_slt:          out = d9; 
            alu_sltu:         out = d10;
            default:          out = sum;
        endcase
    end
   //赋值输出
   assign ALUResult = out;
endmodule
```
]
*代码设计解析*


ALU内部以加法器为核心，通过Binvert控制信号和按位取反加一，实现加法、减法和比较等运算的统一实现，并复用sum的符号位构造有符号、无符号比较结果。

算术右移部分先将输入A复制到有符号寄存器A_reg，再使用>>>运算保证符号位扩展正确，而其它与、或、异或和移位等操作则由组合逻辑直接完成，最后为了简化代码结构，用case函数根据ALUCode在各运算结果中选择输出。在此过程中部分运算定义了中间变量以提高可读性。

*仿真结果*

运行已经给出的ALU模块的仿真代码：
#image("仿真结果/ALU仿真.png")
运行结果如图所示，说明ALU模块正常工作。

=== 数据前推电路
操作数 A 和 B 分别由数据选择器决定，数据选择器地址信号 ForwardA、 ForwardB的含义如图所示。
#image("表30.9.png",width:90%)
由前面介绍的一、二阶数据相关判断条件，不难得到：

$ "ForwardA[0]" = "RegWrite_wb" \& ("rdAddr_wb" ≠ 0) \& ("rdAddr_mem" ≠ "rs1Addr_ex") \ \& ("rdAddr_wb" == "rs1Addr_ex")\
"ForwardA[1]" = "RegWrite_mem" \& ("rdAddr_mem" ≠ 0) \& ("rdAddr_mem" == "rs1Addr_ex")\
"ForwardB[0]" = "RegWrite_wb" \& ("rdAddr_wb" ≠ 0) \& ("rdAddr_mem" ≠ "rs2Addr_ex") \ \& ("rdAddr_wb" == "rs2Addr_ex")\
"ForwardB[1]" = "RegWrite_mem" \& ("rdAddr_mem" ≠ 0) \& ("rdAddr_mem" == "rs2Addr_ex") $

这一部分直接在顶层中集成即可。

=== EX顶层
EX模块顶层接口定义如下：
#image("表30.7.png",width:80%)
根据接口定义、电路图，最终设计如下代码：
#sourcecode[
```v
`timescale 1ns / 1ps
module EX(ALUCode_ex, ALUSrcA_ex, ALUSrcB_ex,Imm_ex, rs1Addr_ex, rs2Addr_ex, rs1Data_ex, 
          rs2Data_ex, PC_ex, RegWriteData_wb, ALUResult_mem,rdAddr_mem, rdAddr_wb, 
		  RegWrite_mem, RegWrite_wb, ALUResult_ex, MemWriteData_ex, ALU_A, ALU_B);
    input [3:0] ALUCode_ex;
    input ALUSrcA_ex;
    input [1:0] ALUSrcB_ex;
    input [31:0] Imm_ex;
    input [4:0]  rs1Addr_ex;
    input [4:0]  rs2Addr_ex;
    input [31:0] rs1Data_ex;
    input [31:0] rs2Data_ex;
	input [31:0] PC_ex;
    input [31:0] RegWriteData_wb;
    input [31:0] ALUResult_mem;
	input [4:0] rdAddr_mem;
    input [4:0] rdAddr_wb;
    input RegWrite_mem;
    input RegWrite_wb;
    output [31:0] ALUResult_ex;
    output [31:0] MemWriteData_ex;
    output [31:0] ALU_A;
    output [31:0] ALU_B;
    
    //数据前推电路
    wire [1:0] ForwardA, ForwardB;
    assign ForwardA[0] = RegWrite_wb && (rdAddr_wb != 0) && (rdAddr_mem != rs1Addr_ex) && (rdAddr_wb == rs1Addr_ex);
    assign ForwardA[1] = RegWrite_mem && (rdAddr_mem != 0) && (rdAddr_mem == rs1Addr_ex);
    assign ForwardB[0] = RegWrite_wb && (rdAddr_wb != 0) && (rdAddr_mem != rs2Addr_ex) && (rdAddr_wb == rs2Addr_ex);
    assign ForwardB[1] = RegWrite_mem && (rdAddr_mem != 0) && (rdAddr_mem == rs2Addr_ex);
    //数据转发MUX结果
    reg [31:0] Amux_out,Bmux_out;
    always @(*) begin
        case(ForwardA)
            2'b00: Amux_out = rs1Data_ex;
            2'b01: Amux_out = RegWriteData_wb;
            2'b10: Amux_out = ALUResult_mem;
            2'b11: Amux_out = ALUResult_mem;
            default: Amux_out = rs1Data_ex;
        endcase
    end
    
        always @(*) begin
        case(ForwardB)
            2'b00: Bmux_out = rs2Data_ex;
            2'b01: Bmux_out = RegWriteData_wb;
            2'b10: Bmux_out = ALUResult_mem;
            2'b11: Bmux_out = ALUResult_mem;
            default: Bmux_out = rs2Data_ex;
        endcase
    end

    // ALU操作数MUX
    assign ALU_A = ALUSrcA_ex ? PC_ex : Amux_out;
    reg [31:0] ALU_B_reg;
    
    always @(*) begin
        case(ALUSrcB_ex)
            2'b00: ALU_B_reg = Bmux_out;
            2'b01: ALU_B_reg = Imm_ex;
            2'b10: ALU_B_reg = 32'd4;
            default: ALU_B_reg = Bmux_out;
        endcase
    end
    
    assign ALU_B = ALU_B_reg;
    
    assign MemWriteData_ex = Bmux_out;//MemWriteData_ex输出
    //实例化ALU
    ALU ALU_inst(
        .ALUCode(ALUCode_ex),
        .A(ALU_A),
        .B(ALU_B),
        .ALUResult(ALUResult_ex)
    );    
endmodule

```
]
*代码设计解析*


首先依据ForwardA和ForwardB对EX、MEM、WB三级的写回结果进行数据前推，通过Amux_out和Bmux_out选择最新的操作数值，从而消除一、二阶数据相关。

再利用ALUSrcA_ex和ALUSrcB_ex在寄存器数据、Imm、PC和常数4之间选择ALU_A、ALU_B，实现普通算术逻辑运算与PC相对地址计算的统一；同时将Bmux_out直接作为MemWriteData_ex送往数据存储器，保证写内存总是使用经过前推后的最新B操作数。配合 ID_EX、EX_MEM 等流水线寄存器，这种前推结构保证大多数算术和逻辑相关都能在不插入气泡的情况下消除，而对于无法前推的 load-use 场景则依赖 ID 级 Stall 逻辑阻塞。


== 数据储存器模块(DataRAM)

数据存储器可用 Xilinx 的 IP 内核实现。考虑到 FPGA 的资源，数据存储器可设计为容量为 64×32 bit 的单端口 RAM，输出采用组合输出（Non Registered）。
#image("IP核.png",width:80%)
直接在 vivado 工程中，通过 IP Catalog，选择 RAM，并设置参数，生成 IP核。参数选择 32 位宽， 64 个存储单元，single port RAM, non registered 输出。之后，直接在 CPU 顶层模块中实例化数据存储器模块即可。

定义成功后source界面如下：
#image("source界面.png",width: 60%)

== 取指令级模块(IF)
IF 模块由指令指针寄存器（PC）、指令存储器子模块（Instruction ROM）、指令指针选择器（MUX）和一个 32 位加法器组成，IF 模块接口信息如图所示。
#image("表30.10.png",width: 88%)
指令存储器为组合存储器，可用 Verilog HDL 设计一个查找表阵列 ROM。考虑到FPGA 的资源，该 ROM 容量可设计为 64×32bit指令存储器模块 InstructionROM.v 已经提供，只需在顶层模块中实例化即可。内存放一段简单测试程序的机器码，对应的测试程序为：

#sourcecode[
```Verilog
/*---------------------------------------------------------------------
        lui X30,0x3000
        jalr X31 later(X0)
earlier:sw  X28, 0C(X0) 
		lw  X29, 04(X6) 
		slli  X5, X29, 2  		//数据冒险
		lw   X28, 04(X6) 
		sltu X28,X6,X7	
done:   jal X31,done 
later:	bne X0, X0, end  		// 分支条件不成立
        addi X5, X30, 42         
		add  X6, X0, X31
		sub X7, X5, X6		     //操作A一阶数据相关，操作B二阶数据相关
		or	 X28, X7, X5  		//操作A一阶数据相关，操作B三阶数据相关
        beq X0, X0, earlier		// 分支条件成立
end:    nop

--------------------------------------------------------------------*/
module InstructionROM(addr,dout);
	input [5 : 0] addr;
	output [31 : 0] dout;
	reg [31 : 0] dout;
	always @(*)
		case (addr)
			6'd0:   dout=32'h0000_3f37 ;//           lui X30,0x3000
			6'd1:   dout=32'h0200_0fE7 ;//           jalr X31 later(X0)
			6'd2:   dout=32'h01c0_2623 ;// earlier: sw  X28, 0C(X0) 
			6'd3:   dout=32'h0043_2e83 ;//           lw  X29, 4(X6) 
			6'd4:   dout=32'h002e_9293 ;//           sll  X5, X29, 2 
			6'd5:   dout=32'h0043_2e03 ;//           lw   X28, 4(X6)
			6'd6:   dout=32'h0073_3e33 ;//		     sltu X28,X6,X7 
			6'd7:   dout=32'h0000_0fef ;//	done:   jal X31,done
			6'd8:   dout=32'h0000_1c63 ;//	later:	bne X0, X0, end  		// 分支条件不成立
			6'd9:   dout=32'h042f_0293;//	        addi X5, X30, 42
			6'd10:  dout=32'h01f0_0333 ;//          add  X6, X0, X31 
			6'd11:  dout=32'h4062_83b3 ;//           sub X7, X5, X6
			6'd12:  dout=32'h0053_ee33 ;//       	or	 X28, X7, X5 
			6'd13:  dout=32'hfc00_0ae3 ;//          beq X0, X0, earlier
			6'd14: dout=32'h00000000 ;// end:  	nop
			default:dout=32'h00000000 ;//nop
		endcase	
endmodule
```
]
这些程序与表30.11的验证表格每一行对应。

=== IF顶层
已知IF顶层接口如下：
#image("表30.10.png",width: 80%)
设计 IF 模块如下所示：

#sourcecode[
```v
`timescale 1ns / 1ps
module IF(clk, reset, Branch,Jump, IFWrite, JumpAddr, Instruction_if, PC, IF_flush);
    input clk;
    input reset;
    input Branch;
    input Jump;
    input IFWrite;
    input [31:0] JumpAddr;
    output [31:0] Instruction_if;
    output [31:0] PC;
    output IF_flush;

    // PC寄存器
    reg [31:0] PC_in, PC_out;
    wire PCSource;
    assign PCSource = Jump || Branch;
    assign IF_flush = PCSource;
    // 计算PC_in的值
    always @(*) begin
        if (PCSource) begin
            PC_in = JumpAddr;
        end else begin
            PC_in = PC + 32'h00000004;
        end
    end
    // 在时钟上升沿时触发
    always @(posedge clk) begin
        if (reset) begin
            PC_out <= 32'b0; // 复位时将PC值重置为0
        end else if (IFWrite) begin
            PC_out <= PC_in; // 使能信号有效时更新PC值
        end else begin
            PC_out <= PC_out; // 使能信号无效时保持PC值不变
        end
    end
    assign PC = PC_out;
    //InstructionROM
    InstructionROM InstructionROM_ints(
        .addr(PC[7:2]),
        .dout(Instruction_if)
    );


endmodule

```
]
*代码设计解析*

IF模块内部用PCSource=Jump||Branch统一处理无条件跳转和条件分支，一旦分支或跳转成立即选择JumpAddr作为下一条指令地址，并通过IF_flush清空后续级以减少控制冒险。

PC寄存器在reset时清零，在IFWrite为高时才更新PC_in，从而与ID级的Stall逻辑配合实现对取指阶段的阻塞。

最后通过InstructionROM以PC[7:2]作为地址按字对齐读出指令，构成了简单清晰的取指流水级。IF_flush 与 IF_ID 寄存器的 reset 结合使用，可以在分支或跳转成立的那个时钟边沿将已经取到但错误的指令整体清空，只保留新路径上的指令流。

*仿真结果*

运行已经给出的IF模块的仿真代码：
#image("仿真结果/IF仿真.png")
可以看到所有指令被正常取出，说明该模块设计无误。


== 流水线寄存器设计
流水线寄存器负责将流水线的各部分分开，共有 IF/ID、ID/EX、EX/MEM、MEM/WB四组，对四组流水线寄存器要求不完全相同，因此设计也有不同考虑。EX/MEM、MEM/WB两组流水线寄存器只是普通的 D 型寄存器。当流水线发生数据冒险时，需要清空 ID/EX流水线寄存器而插入一个气泡，因此 ID/EX 流水线寄存器是一个带同步清零功能的 D型寄存器。当流水线发生数据冒险时，需要阻塞 IF/ID 流水线寄存器；若跳转指令或分支成立，则还需要清空 ID/EX 流水线寄存器。因此， IF/ID 流水线寄存器除同步清零功能外，还需要具有保持功能（即具有使能 EN 信号输入）。

设计流水线寄存器模块代码如下：

#sourcecode[
```Verilog
// IFID寄存器模块
module IF_ID (
    input clk,                // 时钟信号
    input reset,              // 复位信号，高电平有效
    input EN,                 // 使能信号
    input [31:0] Instruction_if, // 输入指令
    input [31:0] PC_if,       // 输入PC值
    output reg [31:0] Instruction_id, // 输出指令
    output reg [31:0] PC_id   // 输出PC值
);

    // 在时钟上升沿时触发
    always @(posedge clk) begin
        if (reset) begin
            Instruction_id <= 32'b0; // 复位
            PC_id <= 32'b0;          
        end else if (EN) begin
            Instruction_id <= Instruction_if; // 使能信号有效时更新
            PC_id <= PC_if;                   
        end else begin
            Instruction_id <= Instruction_id; // 使能信号无效时保持
            PC_id <= PC_id;                  
        end
    end

endmodule


//IDEX寄存器模块
module ID_EX (
    input clk,                // 时钟信号
    input reset,              // 复位信号，高电平有效
    input [31:0] PC_id,       // 输入PC值
    input [31:0] rs1Data_id,  // 输入源寄存器1数据
    input [31:0] rs2Data_id,  // 输入源寄存器2数据
    input [31:0] Imm_id,      // 输入立即数
    input [4:0] rdAddr_id,        // 输入目的寄存器地址
    input [4:0] rs1Addr_id,       // 输入源寄存器1地址
    input [4:0] rs2Addr_id,       // 输入源寄存器2地址
    input [3:0] ALUCode_id,   // 输入ALU控制信号
    input ALUSrcA_id,         // 输入ALU源操作数A选择信号
    input [1:0] ALUSrcB_id,   // 输入ALU源操作数B选择信号
    input MemRead_id,         // 输入内存读信号
    input MemWrite_id,        // 输入内存写信号
    input RegWrite_id,        // 输入寄存器写信号
    input MemtoReg_id,  // 输入内存到寄存器信号


    output reg [31:0] PC_ex,          // 输出PC值
    output reg [31:0] rs1Data_ex,     // 输出源寄存器1数据
    output reg [31:0] rs2Data_ex,     // 输出源寄存器2数据
    output reg [31:0] Imm_ex,         // 输出立即数
    output reg [4:0] rdAddr_ex,           // 输出目的寄存器地址
    output reg [4:0] rs1Addr_ex,          // 输出源寄存器1地址
    output reg [4:0] rs2Addr_ex,          // 输出源寄存器2地址
    output reg [3:0] ALUCode_ex,      // 输出ALU控制信号
    output reg ALUSrcA_ex,            // 输出ALU源操作数A选择信号
    output reg [1:0] ALUSrcB_ex,      // 输出ALU源操作数B选择信号
    output reg MemRead_ex,            // 输出内存读信号
    output reg MemWrite_ex,           // 输出内存写信号
    output reg RegWrite_ex,           // 输出寄存器写信号
    output reg MemtoReg_ex      // 输出内存到寄存器信号
);


    // 在时钟上升沿时触发
    always @(posedge clk) begin
        if (reset) begin
            PC_ex <= 32'b0;          // 复位
            rs1Data_ex <= 32'b0;     
            rs2Data_ex <= 32'b0;     
            Imm_ex <= 32'b0;        
            rdAddr_ex <= 5'b0;       
            rs1Addr_ex <= 5'b0;      
            rs2Addr_ex <= 5'b0;     
            ALUCode_ex <= 4'b0;      
            ALUSrcA_ex <= 1'b0;     
            ALUSrcB_ex <= 2'b0;    
            MemRead_ex <= 1'b0;      
            MemWrite_ex <= 1'b0;   
            RegWrite_ex <= 1'b0;     
            MemtoReg_ex <= 1'b0;     
        end else begin
            PC_ex <= PC_id;          // 更新
            rs1Data_ex <= rs1Data_id; 
            rs2Data_ex <= rs2Data_id; 
            Imm_ex <= Imm_id;         
            rdAddr_ex <= rdAddr_id;  
            rs1Addr_ex <= rs1Addr_id;
            rs2Addr_ex <= rs2Addr_id; 
            ALUCode_ex <= ALUCode_id;
            ALUSrcA_ex <= ALUSrcA_id;
            ALUSrcB_ex <= ALUSrcB_id; 
            MemRead_ex <= MemRead_id;
            MemWrite_ex <= MemWrite_id; 
            RegWrite_ex <= RegWrite_id; 
            MemtoReg_ex <= MemtoReg_id;
        end
    end

endmodule



// EXMEM寄存器模块
module EX_MEM (
    input clk,                // 时钟信号
    input MemWrite_ex,        // 输入内存写信号
    input RegWrite_ex,        // 输入寄存器写信号
    input MemtoReg_ex,        // 输入内存到寄存器信号
    input [31:0] ALUResult_ex,// 输入ALU计算结果
    input [31:0] MemWriteData_ex, // 输入内存数据
    input [4:0] rdAddr_ex,    // 输入目的寄存器地址
    input reset,

    output reg MemWrite_mem,  // 输出内存写信号
    output reg RegWrite_mem,  // 输出寄存器写信号
    output reg MemtoReg_mem,  // 输出内存到寄存器信号
    output reg [31:0] ALUResult_mem, // 输出ALU计算结果
    output reg [31:0] MemWriteData_mem, // 输出内存数据
    output reg [4:0] rdAddr_mem // 输出目的寄存器地址
);


    always @(posedge clk) begin
        if (reset) begin
            MemWrite_mem <= 0;       // 更新
            RegWrite_mem <= 0;       
            MemtoReg_mem <= 0;       
            ALUResult_mem <= 0;    
            MemWriteData_mem <= 0; 
            rdAddr_mem <= 0; 
        end else begin
            MemWrite_mem <= MemWrite_ex;       // 更新
            RegWrite_mem <= RegWrite_ex;       
            MemtoReg_mem <= MemtoReg_ex;       
            ALUResult_mem <= ALUResult_ex;    
            MemWriteData_mem <= MemWriteData_ex; 
            rdAddr_mem <= rdAddr_ex; 
        end
    end
    
endmodule


// MEMWB寄存器模块
module MEM_WB (
    input clk,                // 时钟信号
    input RegWrite_mem,       // 输入寄存器写信号
    input MemtoReg_mem,       // 输入内存到寄存器信号
    input [31:0] ALUResult_mem, // 输入ALU计算结果
    input [31:0] MemDout_mem, // 输入内存数据
    input [4:0] rdAddr_mem,   // 输入目的寄存器地址
    input reset,

    output reg RegWrite_wb,   // 输出寄存器写信号
    output reg MemtoReg_wb,   // 输出内存到寄存器信号
    output reg [31:0] ALUResult_wb, // 输出ALU计算结果
    output reg [31:0] MemDout_wb, // 输出内存数据
    output reg [4:0] rdAddr_wb // 输出目的寄存器地址
);

    // 在时钟上升沿时触发
    always @(posedge clk) begin
        if (reset) begin
            RegWrite_wb <= 0;       // 更新
            MemtoReg_wb <= 0;       
            ALUResult_wb <= 0;     
            MemDout_wb <= 0;         
            rdAddr_wb <= 0;
        end else begin
            RegWrite_wb <= RegWrite_mem;       // 更新
            MemtoReg_wb <= MemtoReg_mem;       
            ALUResult_wb <= ALUResult_mem;     
            MemDout_wb <= MemDout_mem;         
            rdAddr_wb <= rdAddr_mem;
        end           
    end

endmodule

```
]
*代码设计解析*


四组流水线寄存器分别承担指令和控制信号在各级间的可靠传递。IF_ID在支持reset清零的同时增加EN使能信号，用于在数据冒险时冻结IF/ID级；ID_EX在reset时将所有控制和数据信号清零，相当于插入气泡，保证异常状态不会传播到后级；EX_MEM和MEM_WB则作为普通寄存器，将ALU结果、访存数据及写回控制信号顺序传送到MEM、WB级，为顶层CPU模块按图连接各级并观察关键内部信号提供了结构化的时序边界。

通过在顶层将 IF_flush 与 Stall 分别接入 IF_ID 和 ID_EX 的复位与使能端，整个流水线在面对控制冒险时以清空前两级、数据冒险时以冻结前两级的方式插入气泡，使复杂的时序与数据相关在结构上都被约束到这几级寄存器上，便于分析和调试。

== CPU顶层模块
CPU顶层结构如下所示：
#image("顶层结构.png")

按照原理框图连接各模块即可。为了测试方便，可将关键变量输出，关键变量有：指令指针 PC、指令码 Instruction_id、流水线插入气泡标志 Stall、分支标志 JumpFlag即 Jump, Branch、 ALU 输入输出（ALU_A、 ALU_B、 ALUResult_ex）和数据存储器的输出 MemDout_mem。

按照顺序连接各个接口和模块，最终实现整个CPU的顶层模块：

#sourcecode[
```Verilog
`timescale 1ns / 1ps
module Risc5CPU(clk, reset, JumpFlag, Instruction_id, ALU_A, 
                     ALU_B, ALUResult_ex, PC, MemDout_mem, Stall
                     //,
                     //Imm_id_test, Imm_ex_test, ALUSrcB_ex_test
                     );
    input clk;
    input reset;
    output[1:0] JumpFlag;
    output [31:0] Instruction_id;
    output [31:0] ALU_A;
    output [31:0] ALU_B;
    output [31:0] ALUResult_ex;
    output [31:0] PC;
    output [31:0] MemDout_mem;
    output Stall;

    //测试output
   // output [31:0] Imm_id_test,Imm_ex_test;
    //output [1:0] ALUSrcB_ex_test;

    //IF模块
    wire Branch, Jump, IFWrite, IF_flush;
    wire [31:0] JumpAddr,Instruction_if;
    assign JumpFlag[1] = Jump;
    assign JumpFlag[0] = Branch;
    // wire [31:0] PC;//已经在顶层定义

    IF IF_inst(
        .clk(clk),
        .reset(reset),
        .Branch(Branch),
        .Jump(Jump),
        .IFWrite(IFWrite),
        .JumpAddr(JumpAddr),
        .Instruction_if(Instruction_if),
        .PC(PC),
        .IF_flush(IF_flush)
    );

    //IFID寄存器
    wire [31:0] PC_id;
    // wire [31:0] Instruction_id;//已经在顶层定义
    IF_ID IF_ID_inst(
        .clk(clk),
        .reset(IF_flush || reset),
        .EN(IFWrite),
        .Instruction_if(Instruction_if),
        .PC_if(PC),
        .Instruction_id(Instruction_id),
        .PC_id(PC_id)
    );

    //ID模块
    //输入信号
    wire RegWrite_wb;
    wire [4:0] rdAddr_wb;
    wire [31:0] RegWriteData_wb;
    wire MemRead_ex;
    wire [4:0] rdAddr_ex;
    //输出信号
    wire MemtoReg_id;
    wire RegWrite_id;
    wire MemWrite_id;
    wire MemRead_id;
    wire [3:0] ALUCode_id;
    wire ALUSrcA_id;
    wire [1:0]ALUSrcB_id;
    // wire Stall;//已经在顶层定义
    wire [31:0] Imm_id;
    wire [31:0] rs1Data_id;
    wire [31:0] rs2Data_id;
    wire[4:0] rs1Addr_id,rs2Addr_id,rdAddr_id;

    ID ID_inst(
        .clk(clk),
        .Instruction_id(Instruction_id),
        .PC_id(PC_id),
        .RegWrite_wb(RegWrite_wb),
        .rdAddr_wb(rdAddr_wb),
        .RegWriteData_wb(RegWriteData_wb),
        .MemRead_ex(MemRead_ex),
        .rdAddr_ex(rdAddr_ex),
        .MemtoReg_id(MemtoReg_id),
        .RegWrite_id(RegWrite_id),
        .MemWrite_id(MemWrite_id),
        .MemRead_id(MemRead_id),
        .ALUCode_id(ALUCode_id),
        .ALUSrcA_id(ALUSrcA_id),
        .ALUSrcB_id(ALUSrcB_id),
        .Stall(Stall),
        .Branch(Branch),
        .Jump(Jump),
        .IFWrite(IFWrite),
        .JumpAddr(JumpAddr),
        .Imm_id(Imm_id),
        .rs1Data_id(rs1Data_id),
        .rs2Data_id(rs2Data_id),
        .rs1Addr_id(rs1Addr_id),
        .rs2Addr_id(rs2Addr_id),
        .rdAddr_id(rdAddr_id)
    );

    //IDEX寄存器
    wire [31:0] PC_ex;
    wire [31:0] rs1Data_ex;
    wire [31:0] rs2Data_ex;
    wire [31:0] Imm_ex;
    // wire [4:0] rdAddr_ex;//已经在ID模块定义
    wire [4:0] rs1Addr_ex;
    wire [4:0] rs2Addr_ex;
    wire [3:0] ALUCode_ex;
    wire ALUSrcA_ex;
    wire [1:0] ALUSrcB_ex;
    // wire MemRead_ex;//已经在ID模块定义
    wire MemWrite_ex;
    wire RegWrite_ex;
    wire MemtoReg_ex;

    ID_EX ID_EX_inst(
        .clk(clk),
        .reset(reset || Stall),
        .PC_id(PC_id),
        .rs1Data_id(rs1Data_id),
        .rs2Data_id(rs2Data_id),
        .Imm_id(Imm_id),
        .rdAddr_id(rdAddr_id),
        .rs1Addr_id(rs1Addr_id),
        .rs2Addr_id(rs2Addr_id),
        .ALUCode_id(ALUCode_id),
        .ALUSrcA_id(ALUSrcA_id),
        .ALUSrcB_id(ALUSrcB_id),
        .MemRead_id(MemRead_id),
        .MemWrite_id(MemWrite_id),
        .RegWrite_id(RegWrite_id),
        .MemtoReg_id(MemtoReg_id),
        .PC_ex(PC_ex),
        .rs1Data_ex(rs1Data_ex),
        .rs2Data_ex(rs2Data_ex),
        .Imm_ex(Imm_ex),
        .rdAddr_ex(rdAddr_ex),
        .rs1Addr_ex(rs1Addr_ex),
        .rs2Addr_ex(rs2Addr_ex),
        .ALUCode_ex(ALUCode_ex),
        .ALUSrcA_ex(ALUSrcA_ex),
        .ALUSrcB_ex(ALUSrcB_ex),
        .MemRead_ex(MemRead_ex),
        .MemWrite_ex(MemWrite_ex),
        .RegWrite_ex(RegWrite_ex),
        .MemtoReg_ex(MemtoReg_ex)
    );

    //EX模块
    // wire [31:0] ALUResult_ex;//已经在顶层定义
    wire [31:0] MemWriteData_ex;
    // wire [31:0] ALU_A;//已经在顶层定义
    // wire [31:0] ALU_B;//已经在顶层定义
    // wire [31:0] RegWriteData_wb;//已经在ID模块定义
    wire [31:0] ALUResult_mem;
    wire [4:0] rdAddr_mem;
    // wire [4:0] rdAddr_wb;//已经在ID模块定义
    wire RegWrite_mem;
    // wire RegWrite_wb;//已经在ID模块定义

    EX EX_inst(
        .ALUCode_ex(ALUCode_ex),
        .ALUSrcA_ex(ALUSrcA_ex),
        .ALUSrcB_ex(ALUSrcB_ex),
        .Imm_ex(Imm_ex),
        .rs1Addr_ex(rs1Addr_ex),
        .rs2Addr_ex(rs2Addr_ex),
        .rs1Data_ex(rs1Data_ex),
        .rs2Data_ex(rs2Data_ex),
        .PC_ex(PC_ex),
        .RegWriteData_wb(RegWriteData_wb),
        .ALUResult_mem(ALUResult_mem),
        .rdAddr_mem(rdAddr_mem),
        .rdAddr_wb(rdAddr_wb),
        .RegWrite_mem(RegWrite_mem),
        .RegWrite_wb(RegWrite_wb),
        .ALUResult_ex(ALUResult_ex),
        .MemWriteData_ex(MemWriteData_ex),
        .ALU_A(ALU_A),
        .ALU_B(ALU_B)
    );

    //EXMEM寄存器
    wire MemWrite_mem;
    // wire RegWrite_mem;//已经在EX模块定义
    wire MemtoReg_mem;
    // wire [31:0] ALUResult_mem;//已经在EX模块定义
    wire [31:0] MemWriteData_mem;
    // wire [4:0] rdAddr_mem;//已经在EX模块定义

    EX_MEM EX_MEM_inst(
        .clk(clk),
        .MemWrite_ex(MemWrite_ex),
        .RegWrite_ex(RegWrite_ex),
        .MemtoReg_ex(MemtoReg_ex),
        .ALUResult_ex(ALUResult_ex),
        .MemWriteData_ex(MemWriteData_ex),
        .rdAddr_ex(rdAddr_ex),
        .reset(reset),
        .MemWrite_mem(MemWrite_mem),
        .RegWrite_mem(RegWrite_mem),
        .MemtoReg_mem(MemtoReg_mem),
        .ALUResult_mem(ALUResult_mem),
        .MemWriteData_mem(MemWriteData_mem),
        .rdAddr_mem(rdAddr_mem)
    );

    //MEM模块
    wire [31:0] MemDout_mem;
    DataRAM DataRAM_inst(
        .a(ALUResult_mem[7:2]),
        .d(MemWriteData_mem),
        .clk(clk),
        .we(MemWrite_mem),
        .spo(MemDout_mem)
    );

    //MEMWB寄存器
    // wire RegWrite_wb;//已经在ID模块定义
    wire MemtoReg_wb;
    wire [31:0] ALUResult_wb;
    wire [31:0 ]MemDout_wb;
    // wire [4:0] rdAddr_wb;//已经在ID模块定义

    MEM_WB MEM_WB_inst(
        .clk(clk),
        .RegWrite_mem(RegWrite_mem),
        .MemtoReg_mem(MemtoReg_mem),
        .ALUResult_mem(ALUResult_mem),
        .MemDout_mem(MemDout_mem),
        .rdAddr_mem(rdAddr_mem),
        .reset(reset),
        .RegWrite_wb(RegWrite_wb),
        .MemtoReg_wb(MemtoReg_wb),
        .ALUResult_wb(ALUResult_wb),
        .MemDout_wb(MemDout_wb),
        .rdAddr_wb(rdAddr_wb)
    );

    //WB模块
    assign RegWriteData_wb=MemtoReg_wb?MemDout_wb:ALUResult_wb;

    //测试信号赋值
    assign Imm_id_test=Imm_id;
    assign ALUSrcB_ex_test=ALUSrcB_ex;
    assign Imm_ex_test=Imm_ex;

endmodule

```
]


= 实验结果
== 仿真结果
使用如下的代码进行仿真测试， CPU 将会运行 instructionsROM 中的指令，将仿真得到的信号值与预期值进行比较，以验证 CPU 的正确性。
#sourcecode[
```Verilog
initial
begin
// Initialize Inputs
clk = 0;
reset = 1;
// Wait 100 ns for global reset to finish
#100
#51 reset=0;
#2200 $finish;
end
always #20 clk=~clk;
```
]
预期结果在下表30.11中已经给出。
#image("仿真结果验证表格.png",width: 80%)
得到的仿真结果如下：
#image("仿真结果/最终1.png")
#image("仿真结果/最终2.png")
对比各个信号的电平变化，发现结果一致，说明我们的设计无误。


== 硬件测试结果
再次打开 Vivado 文件夹下的 Risc5CPU.xpr 工程，添加流水线 CPU 设计的全部代码，然后综合、实现和下载至 Nexys Video 开发板。连接带有 HDMI 接口的显示器，进行测试。首先将 SW0 置于低电平，使 RISC-VCPU 工作在“单步”运行模式。复位后，每按一下上边按键， RISC-V CPU 运行一步，记录下显示器上的结果，对照 CPU 行为级仿真预期结果验证设计是否正确。

给开发板上电、连数据线、HDMI线，最后的硬件连接如下：
#image("硬件连接.jpg",width: 70%)
将程序烧到开发板上按下按钮，显示器画面如下：
#image("显示.jpg",width: 70%)
由于篇幅原因，这里只展示其中一步。

按下上边按键， RISC-V CPU 运行一步，显示器画面发生一次变化。对照表30.11的结果和旁边显示器的仿真结果可以对照仿真结果与实际结果，发现程序可以正常运行。反复按按钮直到程序进入循环，如果结果均一致则说明设计大功告成。

由于开发板按钮没有做消抖功能，可能会出现显示器页面连续变化的情况。这时只能按下中间+上边按钮使得程序归零，从头重新运行观察。


= 思考题
*如下两条指令，条件分支指令试图读取上一条指令的目标寄存器，插入气泡或数据转发都无法解决流水线冲突问题。为什么在大多 CPU 架构中，都不去解决这一问题？这一问题应在什么层面中解决？*
#sourcecode[
    ```
    lw x28, 04(x6)
    beq x28,x29,Loop
    ```
]
`lw` 指令从内存中加载数据到寄存器 `X28`，而下一条 `beq` 指令需要使用 `X28` 的值进行条件判断。由于 `lw` 指令的结果还未写回寄存器，`beq` 指令无法立即获取到正确的 `X28` 值，导致数据冒险。
通常不直接在硬件层面解决这种问题的原因如下：
#enum(
  [*原因*：在硬件层面解决这种问题需要增加额外的逻辑电路来处理数据冒险。
  在此案例中，需要单独设计一个数据前推模块，对分支指令相关问题进行处理和连线。这需要从各个寄存器连接到分支检测模块，会引入复杂的转发逻辑和流水线暂停机制，可能导致数据通路过长，引入更多的干扰，带来更高的成本。即使在硬件层面解决了这种问题，也会引入流水线暂停，并没有显著提高运行速度。],
  [*解决方法*：对于分支问题，现代编译器可以通过指令调度和优化技术来避免这种数据冒险问题，使得解决问题的成本大大降低。例如，编译器可以在 `lw` 和 `beq` 指令之间插入其他无关指令，或者重新安排这些指令的顺序以避免数据冒险。此外，程序员也可以通过手动插入 `NOP` 指令或重新安排指令顺序来避免数据冒险。],
)

综上所述，大多数 CPU 架构选择在软件层面解决这种数据冒险问题，而不是在硬件层面直接处理，因为修改硬件的收益并不显著，而且从软件层面解决成本更低。

