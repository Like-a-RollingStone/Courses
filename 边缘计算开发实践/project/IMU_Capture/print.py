import serial
import time

# 配置串口参数
serial_port = 'COM5'  # 替换为你的串口名称，例如 'COM3'（Windows）或 '/dev/ttyACM0'（Linux/macOS）
baud_rate = 9600      # 与 Arduino 的波特率一致
output_file = 'space.csv'  # 保存数据的文件名

# 初始化串口
try:
    ser = serial.Serial(serial_port, baud_rate, timeout=1)
    print(f"Connected to {serial_port} at {baud_rate} baud.")
except serial.SerialException as e:
    print(f"Error opening serial port: {e}")
    exit()

# 等待 Arduino 初始化
time.sleep(2)  # 给 Arduino 一些时间重置和初始化

# 打开文件保存数据（可选）
with open(output_file, 'w') as f:
    
    try:
        while True:
            # 读取串口的一行数据
            if ser.in_waiting > 0:
                line = ser.readline().decode('utf-8').strip()
                if line:  # 确保不是空行
                    print(f"Received: {line}")
                    f.write(line + '\n')  # 保存到文件
    except KeyboardInterrupt:
        print("Stopping data collection.")
    except serial.SerialException as e:
        print(f"Serial error: {e}")
    finally:
        ser.close()  # 关闭串口
        print("Serial port closed.")