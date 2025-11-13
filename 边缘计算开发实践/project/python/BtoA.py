import asyncio
from bleak import BleakScanner, BleakClient

# === 配置 ===
USERA_NAME = "UserA BLE"
USERB_NAME = "UserB BLE"
CHAR_UUID = "0007"   # 两个设备使用同一个特征UUID

# === 主逻辑 ===
async def main():
    print("🔍 正在扫描 BLE 设备...")
    devices = await BleakScanner.discover(timeout=8.0)

    userA_dev = next((d for d in devices if d.name == USERA_NAME), None)
    userB_dev = next((d for d in devices if d.name == USERB_NAME), None)

    if not userA_dev or not userB_dev:
        print("❌ 未找到 UserA 或 UserB")
        if not userA_dev:
            print("   ⚠️ 未找到:", USERA_NAME)
        if not userB_dev:
            print("   ⚠️ 未找到:", USERB_NAME)
        return

    print(f"✅ 找到 UserA: {userA_dev.address}")
    print(f"✅ 找到 UserB: {userB_dev.address}")

    # 同时连接两个设备
    async with BleakClient(userA_dev.address) as userA, BleakClient(userB_dev.address) as userB:
        print("✅ 已连接 UserA 与 UserB")

        # 定义当 UserB 有通知时的回调函数
        async def on_userb_data(sender, data):
            try:
                msg = data.decode()
                print(f"📬 从 UserB 收到: '{msg}'")

                # 将数据转发给 UserA
                await userA.write_gatt_char(CHAR_UUID, data)
                print(f"➡️ 已转发给 UserA: '{msg}'")

            except Exception as e:
                print(f"⚠️ 数据转发出错: {e}")

        # 启用 UserB 的通知
        await userB.start_notify(CHAR_UUID, lambda s, d: asyncio.create_task(on_userb_data(s, d)))
        print("📡 正在监听 UserB 通知并转发至 UserA...（Ctrl+C 退出）")

        # 主循环保持连接
        while userA.is_connected and userB.is_connected:
            await asyncio.sleep(60.0)

# === 入口 ===
if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 程序已退出")
