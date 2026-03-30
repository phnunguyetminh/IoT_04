import time
import certifi
import threading
import queue
import json
from datetime import datetime
from paho.mqtt import client as mqtt_client
from pymongo import MongoClient

# CẤU HÌNH 
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC = "traffic/violation/Random4"
CLIENT_ID = "python-traffic-service-001"
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"

db_queue = queue.Queue()
current_light_state = 0  # 0: Xanh, 1: Vàng, 2: Đỏ
sensor_triggered = False

# KẾT NỐI MQTT (Giữ nguyên ở ngoài vì nó kết nối rất nhanh)
def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Service: Đã kết nối MQTT Broker")
            client.subscribe("traffic/status/Random4")
            client.subscribe("traffic/sensor/Random4")
        else:
            print(f"Lỗi MQTT: {rc}")

    def on_message(client, userdata, msg):
        global current_light_state, sensor_triggered
        payload = msg.payload.decode('utf-8')

        if msg.topic == "traffic/status/Random4":
            try:
                data = json.loads(payload)
                current_light_state = data.get("light", 0)
            except Exception:
                pass
        elif msg.topic == "traffic/sensor/Random4":
            if payload == "1" or payload == "DETECTED":  # Thay đổi tùy theo mạch ESP32 của bạn gửi chữ gì
                sensor_triggered = True

    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, CLIENT_ID)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client

mqtt_conn = connect_mqtt()
mqtt_conn.loop_start()

# ==========================================
# SỬA Ở ĐÂY: ĐƯA KẾT NỐI MONGODB VÀO LUỒNG NGẦM
# ==========================================
def database_worker():
    print("   [MongoDB] Luồng ngầm đang khởi động kết nối Cloud...")
    try:
        mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
        db = mongo_client['TrafficDB']
        collection = db['Violations']
        print("   [MongoDB] Đã kết nối Atlas thành công! Sẵn sàng lưu dữ liệu.")
    except Exception as e:
        print(f"Lỗi kết nối MongoDB: {e}")
        collection = None

    # Vòng lặp chờ dữ liệu
    while True:
        violation_entry = db_queue.get() 
        if violation_entry is None: break
        
        if collection is not None:
            try:
                res = collection.insert_one(violation_entry)
                print(f"   [MongoDB] Đã lưu dữ liệu Cloud! ID: {res.inserted_id}")
            except Exception as e:
                print(f"   [MongoDB] Lưu thất bại: {e}")
        
        db_queue.task_done()

# Bật luồng DB Worker lên
threading.Thread(target=database_worker, daemon=True).start()

# ==========================================

def gui_bao_cao_vi_pham(license_plate="UNKNOWN"):
    """Gửi MQTT ngay lập tức và đẩy việc lưu DB cho luồng ngầm xử lý"""
    
    # 1. Gửi MQTT tới Wokwi (Tức thời)
    mqtt_conn.publish(MQTT_TOPIC, "1", qos=0)
    print(f"📡 [MQTT] Đã báo vi phạm tới Wokwi (Xe: {license_plate})")

    thoi_gian_thuc = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    web_data = {
        "license_plate": license_plate,
        "timestamp": thoi_gian_thuc,
        "type": "Vượt đèn đỏ"
    }
    # Dòng này là "linh hồn" của WebSockets, bắn data lên Topic riêng cho Web
    mqtt_conn.publish("traffic/web_dashboard", json.dumps(web_data), qos=0)

    # 2. Đẩy dữ liệu vào Hàng Đợi
    violation_entry = {
        "device_id": CLIENT_ID,
        "type": "Vượt đèn đỏ",
        "license_plate": license_plate,
        "timestamp": datetime.now().strftime("%d/%m/%Y %H:%M:%S"),
        "status": "Đang chờ xử lý"
    }
    db_queue.put(violation_entry)

if __name__ == "__main__":
    print("🚀 Hệ thống Service đang chạy ngầm...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("👋 Đang đóng Service...")
        mqtt_conn.disconnect()