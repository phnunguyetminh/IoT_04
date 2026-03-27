from flask import Flask, jsonify, request, render_template
from flask_cors import CORS
from pymongo import MongoClient
import certifi

app = Flask(__name__)

# CORS: Cho phép Frontend (cổng 5500 hoặc cổng khác) gọi API tới Backend (cổng 5000)
CORS(app) 

# ==========================================
# 1. KẾT NỐI MONGODB ATLAS
# ==========================================
MONGO_URI = "mongodb+srv://group4_user:Md97aogqciQMRnVl@esp32.gyi8obc.mongodb.net/?appName=ESP32"
try:
    client = MongoClient(MONGO_URI, tlsCAFile=certifi.where())
    db = client['TrafficDB']
    collection = db['Violations']
    users_collection = db['Users']
    print("✅ Kết nối MongoDB Atlas thành công!")
except Exception as e:
    print("❌ Lỗi kết nối MongoDB:", e)

# --- BIẾN TOÀN CỤC LƯU CẤU HÌNH ĐÈN ---
traffic_state = {
    "red_time": 40,      # Thời gian đèn Đỏ
    "yellow_time": 4,    # Thời gian đèn Vàng
    "green_time": 10,    # Thời gian đèn Xanh
    "is_active": True    # True = Auto, False = Manual
}


# ==========================================
# 2. ĐỊNH TUYẾN GIAO DIỆN (FRONTEND HTML)
# ==========================================
# LƯU Ý: Các file HTML phải được đặt trong thư mục tên là "templates" cùng cấp với file server.py
@app.route('/')
@app.route('/login.html')
def login_page():
    return render_template('login.html')

@app.route('/dashboard.html')
def dashboard_page():
    return render_template('dashboard.html')

@app.route('/control.html')
def control_page():
    return render_template('control.html')

@app.route('/violation.html')
def violation_page():
    return render_template('violation.html')

@app.route('/users.html')
def users_page():
    return render_template('users.html')


# ==========================================
# 3. API ĐIỀU KHIỂN & CẤU HÌNH (CONTROL)
# ==========================================
@app.route('/api/traffic', methods=['GET'])
def get_traffic():
    return jsonify({
        "is_active": traffic_state["is_active"],
        "red_time": traffic_state["red_time"],
        "yellow_time": traffic_state["yellow_time"],
        "green_time": traffic_state["green_time"]
    })

@app.route('/api/settings', methods=['POST'])
def update_settings():
    # Kiểm tra phân quyền Admin từ Header
    user_role = request.headers.get('X-Role')
    if user_role != 'admin':
        return jsonify({"status": "error", "message": "Bạn không có quyền Admin để đổi thời gian!"}), 403

    global traffic_state
    data = request.json
    traffic_state["red_time"] = data.get("red", 40)
    traffic_state["yellow_time"] = data.get("yellow", 4)
    traffic_state["green_time"] = data.get("green", 10)
    
    return jsonify({"status": "success", "message": "Đã cập nhật cấu hình!"})

@app.route('/api/mode', methods=['POST'])
def update_mode():
    global traffic_state
    data = request.json
    traffic_state["is_active"] = data.get("auto", True)
    return jsonify({"status": "success", "message": "Đã chuyển đổi chế độ!"})


# ==========================================
# 4. API THỐNG KÊ & LOG VI PHẠM (VIOLATIONS)
# ==========================================
@app.route('/api/violations/stats', methods=['GET'])
def get_stats():
    try:
        red_light = collection.count_documents({"type": "Vượt đèn đỏ"})
        wrong_lane = collection.count_documents({"type": "Lấn làn"})
        overspeed = collection.count_documents({"type": "Quá tốc độ"})
        return jsonify({
            "red_light": red_light,
            "wrong_lane": wrong_lane,
            "overspeed": overspeed
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

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
                    "time": "$timestamp",       
                    "plate": "$license_plate",  
                    "type": 1,
                    "owner_name": {"$ifNull": ["$user_info.name", "Khách vãng lai"]} 
                }
            }
        ]
        logs = list(collection.aggregate(pipeline))
        return jsonify(logs)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# 5. API QUẢN LÝ NGƯỜI DÙNG (USERS)
# ==========================================
@app.route('/api/users/search', methods=['GET'])
def search_user():
    query_str = request.args.get('query', '').strip()
    if not query_str:
        return jsonify({"status": "error", "message": "Vui lòng nhập thông tin để tìm"}), 400
    
    try:
        search_query = {
            "$or": [
                {"plate": {"$regex": query_str, "$options": "i"}},
                {"name": {"$regex": query_str, "$options": "i"}}
            ]
        }
        users = list(users_collection.find(search_query, {'_id': 0}))
        return jsonify(users)
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route('/api/users', methods=['POST'])
def add_user():
    data = request.json
    if not data or 'plate' not in data:
        return jsonify({"status": "error", "message": "Thiếu thông tin biển số"}), 400
    
    plate_clean = data['plate'].strip().upper()
    data['plate'] = plate_clean
    
    try:
        if users_collection.find_one({"plate": plate_clean}):
            return jsonify({"status": "error", "message": "Biển số này đã được đăng ký!"}), 400
            
        users_collection.insert_one(data)
        return jsonify({"status": "success", "message": "Thêm thông tin thành công!"})
    except Exception as e:
        return jsonify({"status": "error", "message": "Lỗi Database!"}), 500

@app.route('/api/users/<plate>', methods=['PUT'])
def update_user(plate):
    data = request.json
    plate_clean = plate.strip().upper()
    
    update_fields = {}
    if 'name' in data: update_fields['name'] = data['name']
    if 'phone' in data: update_fields['phone'] = data['phone']
    if 'type' in data: update_fields['type'] = data['type']
    
    if not update_fields:
        return jsonify({"status": "error", "message": "Không có dữ liệu để cập nhật"}), 400
        
    try:
        result = users_collection.update_one(
            {"plate": plate_clean},
            {"$set": update_fields}
        )
        if result.matched_count > 0:
            return jsonify({"status": "success", "message": f"Đã cập nhật thông tin cho xe {plate_clean}"})
        else:
            return jsonify({"status": "error", "message": "Không tìm thấy biển số này!"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": "Lỗi Database!"}), 500

@app.route('/api/users/<plate>', methods=['DELETE'])
def delete_user(plate):
    plate_clean = plate.strip().upper()
    try:
        result = users_collection.delete_one({"plate": plate_clean})
        if result.deleted_count > 0:
            return jsonify({"status": "success", "message": f"Đã xóa thành công xe có biển số {plate_clean}"})
        else:
            return jsonify({"status": "error", "message": "Không tìm thấy biển số này trong hệ thống!"}), 404
    except Exception as e:
        return jsonify({"status": "error", "message": "Lỗi Database!"}), 500


# ==========================================
# 6. TRẠNG THÁI HỆ THỐNG
# ==========================================
@app.route('/api/system/health', methods=['GET'])
def get_health():
    return jsonify({
        "esp32": {"status": "Online", "ping": 12},
        "camera": {"status": "Processing", "fps": 30}
    })


# --- KHỞI ĐỘNG SERVER ---
if __name__ == '__main__':
    print("🚀 Server Backend đang chạy tại http://localhost:5000")
    app.run(debug=True, port=5000)