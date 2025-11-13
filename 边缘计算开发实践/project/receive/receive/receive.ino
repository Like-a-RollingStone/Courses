#include <ArduinoBLE.h>

BLEService signalService("680d65c7-3a0a-4023-a05a-6aaf2f22441c");
BLECharacteristic signalChar("0007", BLERead | BLENotify | BLEWrite , 20);

void setup() {
  Serial.begin(9600);
  // while (!Serial);

  Serial.println("🚀 启动 BLE 外设：UserA BLE");

  if (!BLE.begin()) {
    Serial.println("❌ 启动 BLE 失败！");
    while (1);
  }

  BLE.setLocalName("UserA BLE");
  BLE.setAdvertisedService(signalService);

  signalService.addCharacteristic(signalChar);
  BLE.addService(signalService);

  BLE.advertise();

  Serial.println("📡 等待电脑通过 BLE 连接并发送数据...");
}

void loop() {
  BLEDevice central = BLE.central();

  if (central) {
    Serial.print("✅ 已连接至中央设备：");
    Serial.println(central.address());

    while (central.connected()) {
      BLEDevice central = BLE.central();
      if (signalChar.written()) {
        int length = signalChar.valueLength();        // 获取实际字节长度
        String value = String((const char*)signalChar.value(), length);
        Serial.println(value);
      }
    }

    Serial.println("🔌 中央设备断开连接");
  }
}
