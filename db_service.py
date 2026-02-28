from flask import Flask, request, jsonify
from pymongo import MongoClient
from datetime import datetime
import certifi

app = Flask(__name__)

#    CẤU HÌNH THỐNG NHẤT   
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"

try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client["TrafficDB"]  # Đổi từ IoT_Project thành TrafficDB
    collection = db["Violations"]  # Đổi từ SensorData thành Violations
    client.admin.command('ping')
    print("Flask Server: Đã kết nối thành công đến MongoDB Atlas (TrafficDB)!")
except Exception as e:
    print(f"Lỗi kết nối MongoDB: {e}")


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
        print(f"Lỗi: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500


if __name__ == '__main__':
    # Chạy ở port 5000
    app.run(host='0.0.0.0', port=5000, debug=True)