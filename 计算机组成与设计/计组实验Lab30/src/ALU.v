//******************************************************************************
// MIPS verilog model
//
// ALU.v
//******************************************************************************

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