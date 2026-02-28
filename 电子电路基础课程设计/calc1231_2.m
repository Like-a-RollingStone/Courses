% 选择自由参数值
Rf_val = 10000;  % 10 kΩ
R3_val = 10000;  % 10 kΩ

% 计算其他电阻值
R1_val = (2/3) * Rf_val;
R2_val = 2 * Rf_val;
R4_val = R3_val;
R5_val = R3_val / 4;

% 生成随机测试点
num_tests = 100;
errors = zeros(num_tests, 1);
for i = 1:num_tests
    v = rand(1, 4) * 10 - 5;  % 在[-5,5]范围内随机取值
    v1 = v(1); v2 = v(2); v3 = v(3); v4 = v(4);
    
    % 计算左边
    left_val = ((1/Rf_val + 1/R1_val + 1/R2_val) / (1/R3_val + 1/R4_val + 1/R5_val)) * ...
               (v3/R3_val + v4/R4_val) * Rf_val - (v1/R1_val + v2/R2_val) * Rf_val;
    
    % 计算右边
    right_val = -1.5*v1 - 0.5*v2 + 0.5*v3 + 0.5*v4;
    
    errors(i) = abs(left_val - right_val);
end

disp(left_val);
disp(right_val);
