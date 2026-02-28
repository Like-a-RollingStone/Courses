% 定义并联电阻函数
parallel = @(Ra, Rb) ((Ra) .* (Rb)) ./ ((Ra) + (Rb));

rbe = @(ib)(0.0026/ib);

% 输入参数
beta = input('β = ');         

% 电阻网络
Rb   = input('Rb =  ');
R2   = input('R_2 = ');
R3   = input('R_3 = ');
R4   = input('R_4 = ');
R5   = input('R_5 = ');
R6   = input('R_6 = ');
Rc2  = input('R_c2 = ');
Rd   = input('R_d = ');

% 直流参数
ibq2 = beta/(beta+1) * (20-0.7)/(2 * R3);
icq2 = beta*ibq2;
ucq2 = 10-icq2 * Rc2;
ueq6 = ucq2-0.7-0.7;
ieq6 = ueq6/R4;
ibq6 = ieq6/(beta + 1);
ibq5 = ieq6/((beta+1)^2);
icq5 = beta*ibq5;
ubq7 = 10-icq5*R2;
ueq7 = ubq7 - 0.7;
ubq8 = ueq7 -2*R5;
ueq8 = ubq8 -0.7;
ieq8 = ueq8/R6;
ibq8 = ieq8/(beta+1);
ibq7 = (2+ibq8)/(beta+1);


% 小信号输入电阻 (r_pi)
r_pi2 = rbe(ibq2);
r_pi1 = r_pi2;
r_pi5 = rbe(ibq5);
r_pi6 = rbe(ibq6);
r_pi7 = rbe(ibq7);
r_pi8 = rbe(ibq8);
r_e7 = r_pi7/(beta+1);


%核心计算
Ri=2*(r_pi2+Rb);

R_i2 = r_pi5 + (beta + 1) * (r_pi6 + (beta + 1) * R4);

inner_parallel = parallel(Rd, r_pi8 + (beta + 1) * R6);
R_i3 = r_pi7 + (beta + 1) * (R5 + inner_parallel);

R_parallel1 = parallel(Rc2, R_i2);
A_v1 = 0.5 * beta * R_parallel1 / (r_pi1 + r_pi2);

R_parallel2 = parallel(R2, R_i3);
A_v2 = -beta^2 * R_parallel2 / R_i2;

A_v = A_v2 * A_v1;

% 分步计算 Ro
R2_div_beta_plus_1 = R2 / (beta + 1);

inner_sum = R5 + r_e7 + R2_div_beta_plus_1;

Rd_parallel_inner = parallel(Rd, inner_sum);

numerator = r_pi8 + Rd_parallel_inner;

divided_by_beta_plus_1 = numerator / (beta + 1);

Ro = parallel(R6, divided_by_beta_plus_1);




% 输出结果
disp(Ri);
disp(Ro);
disp(A_v);


