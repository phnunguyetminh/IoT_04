from flask import Flask, request, jsonify
from flask_cors import CORS  # <-- THÊM THƯ VIỆN NÀY ĐỂ WEB KHÔNG BỊ CHẶN
from pymongo import MongoClient
from paho.mqtt import client as mqtt_client
from datetime import datetime
import certifi
import json

app = Flask(__name__)
CORS(app)  # Cho phép mọi trang web gọi API vào server này

# ==========================================
# 1. CẤU HÌNH MONGODB & MQTT
# ==========================================
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"
MQTT_BROKER = "broker.hivemq.com"
MQTT_PORT = 1883
MQTT_TOPIC_CONTROL = "traffic/control/Random4"  # Topic để gửi lệnh cài đặt thời gian
CLIENT_ID = "flask-backend-api-001"

# Kết nối MongoDB
try:
    mongo_client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = mongo_client["TrafficDB"]
    collection = db["Violations"]
    mongo_client.admin.command('ping')
    print("✅ [MongoDB] Đã kết nối thành công đến Atlas!")
except Exception as e:
    print(f"❌ [MongoDB] Lỗi kết nối: {e}")

# Kết nối MQTT (Dành cho việc gửi lệnh từ Web xuống ESP32)
mqtt_conn = mqtt_client.Client(mqtt_client.CallbackAPIVersion.VERSION2, CLIENT_ID)
try:
    mqtt_conn.connect(MQTT_BROKER, MQTT_PORT)
    mqtt_conn.loop_start()
    print("✅ [MQTT] Đã kết nối Broker thành công!")
except Exception as e:
    print(f"❌ [MQTT] Lỗi kết nối: {e}")


# ==========================================
# 2. CÁC API DÀNH CHO TRANG CONTROL.HTML
# ==========================================

# API lấy trạng thái hiện tại của đèn (Chạy mỗi 1s trên web)
@app.route('/api/traffic', methods=['GET'])
def get_traffic_status():
    # Tạm thời trả về số liệu mặc định. Nếu bạn có lưu cấu hình vào DB thì query ở đây.
    return jsonify({
        "red_time": 40,
        "yellow_time": 4,
        "green_time": 10,
        "is_active": True
    }), 200


# API Nhận lệnh thay đổi thời gian từ nút "GỬI CÀI ĐẶT"
@app.route('/api/settings', methods=['POST'])
def update_settings():
    try:
        data = request.json
        print(f"Nhận yêu cầu cài đặt đèn từ Web: {data}")

        # Đóng gói dữ liệu thành JSON và Bắn MQTT thẳng xuống ESP32
        # Data format: {"red": 20, "yellow": 4, "green": 20}
        mqtt_conn.publish(MQTT_TOPIC_CONTROL, json.dumps(data), qos=1)

        return jsonify({"status": "success", "message": "Đã gửi cấu hình xuống hệ thống!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# API Đổi chế độ Tự động / Thủ công
@app.route('/api/mode', methods=['POST'])
def update_mode():
    try:
        data = request.json
        print(f"Nhận yêu cầu đổi chế độ: {data}")

        # Bắn tín hiệu MQTT đổi chế độ (Ví dụ: {"auto": True})
        mqtt_conn.publish(MQTT_TOPIC_CONTROL, json.dumps(data), qos=1)

        return jsonify({"status": "success", "message": "Đã đổi chế độ!"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 3. API CŨ GIỮ NGUYÊN (Lưu Vi Phạm)
# ==========================================
@app.route('/data', methods=['POST'])
def receive_data():
    try:
        data = request.json
        if not data.get("timestamp"):
            data["timestamp"] = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        print(f"Nhận dữ liệu từ Main/Webcam: {data}")
        collection.insert_one(data)
        return jsonify({"status": "success", "message": "Dữ liệu vi phạm đã lưu lên Cloud"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    print("🚀 Khởi động Server API tại http://localhost:5000")
    app.run(host='0.0.0.0', port=5000, debug=True)