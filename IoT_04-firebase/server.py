from flask import Flask, jsonify, request
from flask_cors import CORS
from pymongo import MongoClient
import certifi
from paho.mqtt import client as mqtt_client
import json

app = Flask(__name__)
CORS(app)

# --- 1. CẤU HÌNH MONGODB ---
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['TrafficDB']
collection = db['Violations']

# --- 2. CẤU HÌNH MQTT ĐỂ NGHE DỮ LIỆU TỪ WOKWI ---
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
# Topic này phải khớp với Topic mà ESP32 trong Wokwi đang Publish lên
MQTT_TOPIC_STATUS = "traffic/status/Random4" 

# Biến toàn cục để lưu trạng thái đèn lấy từ MQTT
traffic_data = {
    "current_light": 0,
    "timer": 0,
    "is_active": True
}

current_configs = {
    "red": 30,
    "yellow": 3,
    "green": 15
}

def connect_mqtt():
    def on_connect(client, userdata, flags, rc, properties=None):
        if rc == 0:
            print("Server đã kết nối MQTT và đang đợi tin từ Wokwi...")
            client.subscribe(MQTT_TOPIC_STATUS)
        else:
            print(f"Lỗi kết nối MQTT: {rc}")

    def on_message(client, userdata, msg):
        global traffic_data
        try:
            # Giả sử Wokwi gửi tin nhắn dạng JSON: {"light": 0, "sec": 15}
            payload = json.loads(msg.payload.decode())
            traffic_data["current_light"] = payload.get("light", 0)
            traffic_data["timer"] = payload.get("sec", 0)
        except:
            # Nếu Wokwi chỉ gửi số giây đơn thuần
            try:
                traffic_data["timer"] = int(msg.payload.decode())
            except:
                pass

    client = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect(MQTT_BROKER, MQTT_PORT)
    return client

# Chạy MQTT trong một luồng riêng
mqtt_conn = connect_mqtt()
mqtt_conn.loop_start()

# --- 3. CÁC API TRẢ DỮ LIỆU CHO WEB ---

@app.route('/api/traffic', methods=['GET'])
def get_traffic():
    response = traffic_data.copy()
    response.update(current_configs)
    # Giờ đây dữ liệu này sẽ thay đổi liên tục theo MQTT
    return jsonify(response)

@app.route('/api/violations/stats', methods=['GET'])
def get_stats():
    red_light = collection.count_documents({"type": "Vượt đèn đỏ"})
    wrong_lane = collection.count_documents({"type": "Lấn làn"})
    overspeed = collection.count_documents({"type": "Quá tốc độ"})
    return jsonify({
        "red_light": red_light,
        "wrong_lane": wrong_lane,
        "overspeed": overspeed
    })

@app.route('/api/system/health', methods=['GET'])
def get_health():
    return jsonify({
        "esp32": {"status": "Online", "ping": 15},
        "camera": {"status": "Processing", "fps": 28}
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    global current_configs
    data = request.json
    current_configs = data
    # Chuyển JSON thành chuỗi "red,yellow,green" để ESP32 dễ đọc
    msg = f"{data['red']},{data['yellow']},{data['green']}"
    mqtt_conn.publish("traffic/control/settings", msg)
    print(f"Đã gửi cài đặt mới xuống Wokwi: {msg}")
    return jsonify({"status": "success"})

@app.route('/api/mode', methods=['POST'])
def update_mode():
    data = request.json
    # data['auto'] sẽ là True hoặc False
    msg = "AUTO" if data['auto'] else "MANUAL"
    mqtt_conn.publish("traffic/control/mode", msg)
    return jsonify({"status": "success"})

@app.route('/api/violations/list', methods=['GET'])
def get_violation_list():
    try:
        # Lấy tất cả dữ liệu, bỏ qua trường _id vì nó không định dạng JSON được
        violations = list(collection.find({}, {'_id': 0}))
        print(f"Đã tìm thấy {len(violations)} bản ghi") # Xem ở Terminal Python
        return jsonify(violations)
    except Exception as e:
        print(f"Lỗi MongoDB: {e}")
        return jsonify([])

if __name__ == '__main__':
    app.run(debug=False, port=5000) # Tắt debug=True khi dùng MQTT loop