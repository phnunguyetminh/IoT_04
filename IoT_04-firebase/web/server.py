from flask import Flask, jsonify, request # Đã thêm 'request' vào đây
from flask_cors import CORS
from pymongo import MongoClient
import certifi
import time

app = Flask(__name__)
# CORS là bùa hộ mệnh để Trang Web (Cổng 5500) lấy được dữ liệu từ Python (Cổng 5000)
CORS(app) 

# KẾT NỐI MONGODB ATLAS Y CHANG CODE CỦA BÀ
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"
client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
db = client['TrafficDB']
collection = db['Violations']

# Khai báo Collection Users
users_collection = db['Users']

# --- KHAI BÁO BIẾN TOÀN CỤC LƯU TRỮ CẤU HÌNH (Đã xóa bỏ giả lập đếm ngược) ---
traffic_state = {
    "red_time": 40,      # Cài đặt thời gian đèn Đỏ
    "yellow_time": 4,    # Cài đặt thời gian đèn Vàng
    "green_time": 10,    # Cài đặt thời gian đèn Xanh
    "is_active": True    # Chế độ Auto (True) / Manual (False)
}

# 1. API TRẢ VỀ CẤU HÌNH ĐÈN GIAO THÔNG (KHÔNG TỰ ĐẾM NGƯỢC NỮA)
@app.route('/api/traffic', methods=['GET'])
def get_traffic():
    # Chỉ trả về các thông số cài đặt để Web hiển thị vào ô Input
    return jsonify({
        "is_active": traffic_state["is_active"],
        "red_time": traffic_state["red_time"],
        "yellow_time": traffic_state["yellow_time"],
        "green_time": traffic_state["green_time"]
    })

# API NHẬN LỆNH LƯU CÀI ĐẶT THỜI GIAN TỪ TRANG CONTROL
@app.route('/api/settings', methods=['POST'])
def update_settings():
    global traffic_state
    data = request.json
    traffic_state["red_time"] = data.get("red", 40)
    traffic_state["yellow_time"] = data.get("yellow", 4)
    traffic_state["green_time"] = data.get("green", 10)
    
    return jsonify({"status": "success", "message": "Đã cập nhật cấu hình!"})

# API NHẬN LỆNH ĐỔI CHẾ ĐỘ AUTO/MANUAL TỪ TRANG CONTROL
@app.route('/api/mode', methods=['POST'])
def update_mode():
    global traffic_state
    data = request.json
    traffic_state["is_active"] = data.get("auto", True)
    
    return jsonify({"status": "success"})
# ... (Giữ nguyên các API Thống kê và Quản lý Users bên dưới của bạn) ...

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


# 2.5 API TRẢ VỀ DANH SÁCH CHI TIẾT VI PHẠM CHO TRANG VIOLATION
@app.route('/api/violations/list', methods=['GET'])
def get_violations_list():
    try:
        pipeline = [
            {"$sort": {"_id": -1}},
            {"$limit": 50},
            {
                "$lookup": {
                    "from": "Users",
                
                    "localField": "license_plate", 
                    "foreignField": "plate",       
                    "as": "user_info"
                }
            },
            {
                "$unwind": {
                    "path": "$user_info",
                    "preserveNullAndEmptyArrays": True
                }
            },
            {
                "$project": {
                    "_id": 0,
                    # CHUYỂN ĐỔI TÊN TRƯỜNG ĐỂ GIAO DIỆN HTML HIỂU ĐƯỢC
                    "time": "$timestamp",       # Đọc 'timestamp' từ DB và gán vào biến 'time'
                    "plate": "$license_plate",  # Đọc 'license_plate' từ DB và gán vào biến 'plate'
                    "type": 1,
                    "owner_name": {"$ifNull": ["$user_info.name", "Khách vãng lai"]} 
                }
            }
        ]
        
        logs = list(collection.aggregate(pipeline))
        return jsonify(logs)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

# 3. API TRẠNG THÁI HỆ THỐNG
@app.route('/api/system/health', methods=['GET'])
def get_health():
    return jsonify({
        "esp32": {"status": "Online", "ping": 12},
        "camera": {"status": "Processing", "fps": 30}
    })

@app.route('/api/users/<plate>', methods=['DELETE'])
def delete_user(plate):
    # Đảm bảo in hoa và xóa khoảng trắng để khớp với dữ liệu lúc lưu
    plate_clean = plate.strip().upper()
    
    # Thực hiện lệnh xóa trong MongoDB
    result = users_collection.delete_one({"plate": plate_clean})
    
    if result.deleted_count > 0:
        return jsonify({"status": "success", "message": f"Đã xóa thành công xe có biển số {plate_clean}"})
    else:
        return jsonify({"status": "error", "message": "Không tìm thấy biển số này trong hệ thống!"}), 404

# --- API QUẢN LÝ NGƯỜI DÙNG ---

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.json
    if not data or 'plate' not in data:
        return jsonify({"status": "error", "message": "Thiếu thông tin biển số"}), 400
    
    # Chuẩn hóa biển số (viết hoa toàn bộ, xóa khoảng trắng thừa)
    plate_clean = data['plate'].strip().upper()
    data['plate'] = plate_clean
    
    # Kiểm tra trùng lặp biển số
    if users_collection.find_one({"plate": plate_clean}):
        return jsonify({"status": "error", "message": "Biển số này đã được đăng ký!"}), 400
        
    users_collection.insert_one(data)
    return jsonify({"status": "success", "message": "Thêm thông tin thành công!"})

@app.route('/api/users/search', methods=['GET'])
def search_user():
    # Lấy từ khóa (có thể là tên hoặc biển số)
    query_str = request.args.get('query', '').strip()
    if not query_str:
        return jsonify({"status": "error", "message": "Vui lòng nhập thông tin để tìm"}), 400
    
    # Dùng toán tử $or của MongoDB để tìm biển số HOẶC tên (không phân biệt hoa thường)
    search_query = {
        "$or": [
            {"plate": {"$regex": query_str, "$options": "i"}},
            {"name": {"$regex": query_str, "$options": "i"}}
        ]
    }
    
    users = list(users_collection.find(search_query, {'_id': 0}))
    return jsonify(users)


@app.route('/api/users/<plate>', methods=['PUT'])
def update_user(plate):
    data = request.json
    plate_clean = plate.strip().upper()
    
    # Chỉ cập nhật Tên, SĐT, Loại xe (Biển số là khóa chính nên không cho sửa)
    update_fields = {}
    if 'name' in data: update_fields['name'] = data['name']
    if 'phone' in data: update_fields['phone'] = data['phone']
    if 'type' in data: update_fields['type'] = data['type']
    
    if not update_fields:
        return jsonify({"status": "error", "message": "Không có dữ liệu để cập nhật"}), 400
        
    # Cập nhật vào MongoDB
    result = users_collection.update_one(
        {"plate": plate_clean},
        {"$set": update_fields}
    )
    
    if result.matched_count > 0:
        return jsonify({"status": "success", "message": f"Đã cập nhật thông tin cho xe {plate_clean}"})
    else:
        return jsonify({"status": "error", "message": "Không tìm thấy biển số này!"}), 404

# --- KHỞI ĐỘNG SERVER (Luôn để ở cuối cùng) ---
if __name__ == '__main__':
    print("🚀 Server đang chạy tại http://localhost:5000")
    app.run(debug=True, port=5000)