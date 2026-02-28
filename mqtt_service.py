import time
import certifi
from datetime import datetime
from paho.mqtt import client as mqtt_client
from pymongo import MongoClient

# CẤU HÌNH 
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "traffic/violation/Random4"
CLIENT_ID = "python-traffic-service-001"
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"

# KẾT NỐI MONGODB
try:
    mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = mongo_client['TrafficDB']
    collection = db['Violations']
    print("Service: Đã kết nối MongoDB Atlas")
except Exception as e:
    print(f"Lỗi kết nối MongoDB: {e}")
    collection = None


# KẾT NỐI MQTT 
def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Service: Đã kết nối MQTT Broker")
        else:
            print(f"Lỗi MQTT: {rc}")

    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, CLIENT_ID)
    client.on_connect = on_connect
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client


mqtt_conn = connect_mqtt()
mqtt_conn.loop_start()


# HÀM XỬ LÝ VI PHẠM 
def gui_bao_cao_vi_pham(license_plate="UNKNOWN"):
    """Hàm này sẽ gửi tín hiệu tới Wokwi và lưu dữ liệu lên MongoDB"""

    # 1. Gửi MQTT tới Wokwi
    mqtt_conn.publish(MQTT_TOPIC, "1", qos=1)
    print(f"📡 [MQTT] Đã báo vi phạm tới Wokwi (Xe: {license_plate})")

    # 2. Lưu dữ liệu lên Cloud
    if collection is not None:
        violation_entry = {
            "device_id": CLIENT_ID,
            "type": "Vượt đèn đỏ",
            "license_plate": license_plate,
            "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
            "status": "Đang chờ xử lý"
        }
        try:
            res = collection.insert_one(violation_entry)
            print(f"[MongoDB] Đã lưu dữ liệu! ID: {res.inserted_id}")
        except Exception as e:
            print(f"[MongoDB] Lưu thất bại: {e}")


# GIỮ CHƯƠNG TRÌNH CHẠY (Nếu chạy độc lập file này)
if __name__ == "__main__":
    print("🚀 Hệ thống Service đang chạy ngầm...")
    try:
        while True:
            time.sleep(1)  # Vòng lặp giữ kết nối
    except KeyboardInterrupt:
        print("👋 Đang đóng Service...")
        mqtt_conn.disconnect()