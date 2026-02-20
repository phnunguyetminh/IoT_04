from flask import Flask, jsonify
from flask_cors import CORS
from pymongo import MongoClient
import certifi

app = Flask(__name__)
# CORS là bùa hộ mệnh để Trang Web (Cổng 5500) lấy được dữ liệu từ Python (Cổng 5000)
CORS(app) 

# KẾT NỐI MONGODB ATLAS Y CHANG CODE CỦA BÀ
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['TrafficDB']
collection = db['Violations']

# 1. API TRẢ VỀ THÔNG TIN ĐÈN (Tạm giả lập, sau này kết nối MQTT vô đây luôn)
@app.route('/api/traffic', methods=['GET'])
def get_traffic():
    return jsonify({
        "current_light": 0, # 0: Xanh, 1: Vàng, 2: Đỏ
        "timer": 15,
        "is_active": True
    })

# 2. API TRẢ VỀ THỐNG KÊ VI PHẠM (ĐẾM TRỰC TIẾP TỪ MONGODB)
@app.route('/api/violations/stats', methods=['GET'])
def get_stats():
    # Đếm số lượng từng loại vi phạm trong Collection
    red_light = collection.count_documents({"type": "Vượt đèn đỏ"})
    wrong_lane = collection.count_documents({"type": "Lấn làn"})
    overspeed = collection.count_documents({"type": "Quá tốc độ"})
    
    return jsonify({
        "red_light": red_light,
        "wrong_lane": wrong_lane,
        "overspeed": overspeed
    })

# 3. API TRẠNG THÁI HỆ THỐNG
@app.route('/api/system/health', methods=['GET'])
def get_health():
    return jsonify({
        "esp32": {"status": "Online", "ping": 12},
        "camera": {"status": "Processing", "fps": 30}
    })

if __name__ == '__main__':
    print("🚀 Server đang chạy tại http://localhost:5000")
    app.run(debug=True, port=5000)