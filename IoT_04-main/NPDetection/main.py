import cv2
import numpy as np
import threading
import queue
import time
import math
from ultralytics import YOLO
from collections import deque
from sort.sort import *
from util import get_car, read_license_plate
import mqtt_service

# CẤU HÌNH
VIDEO_PATH = './test2.mp4'
VEHICLE_CLASSES = [2, 3, 5, 7]
MOVEMENT_THRESHOLD = 15  # Ngưỡng dịch chuyển (pixel). Di chuyển ít hơn mức này = Đang dừng
FRAMES_TO_TRACK = 10     # Lưu tọa độ của 10 khung hình gần nhất để so sánh
car_positions = {}       # Từ điển lưu lịch sử vị trí của từng xe: {car_id: [(x,y), (x,y)...]}

# 1. CLASS ĐỌC VIDEO ĐA LUỒNG (Chống lag buffer)
class VideoStreamWidget:
    def __init__(self, src):
        self.src = src
        self.cap = cv2.VideoCapture(src)
        self.ret, self.frame = self.cap.read()
        self.stopped = False

        # Lấy FPS gốc của video. Nếu là webcam (src=0) có thể trả về 0, ta lấy mặc định là 30.
        self.fps = self.cap.get(cv2.CAP_PROP_FPS)
        if self.fps == 0 or np.isnan(self.fps):
            self.fps = 30.0

            # Tính thời gian cần chờ giữa mỗi frame (Víss dụ 30 FPS -> chờ ~0.033 giây)
        self.frame_delay = 1.0 / self.fps

        # Khởi động luồng đọc frame liên tục
        self.thread = threading.Thread(target=self.update, daemon=True)
        self.thread.start()

    def update(self):
        while not self.stopped:
            start_time = time.time()  # Ghi nhận thời gian bắt đầu đọc frame

            ret, frame = self.cap.read()

            # Nếu hết video và nguồn là file (chữ), thì lặp lại từ đầu
            if not ret and isinstance(self.src, str):
                self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                continue

            self.ret = ret
            self.frame = frame

            # Tính toán thời gian thực tế đã trôi qua khi đọc frame
            elapsed_time = time.time() - start_time

            # Trừ hao thời gian đọc để tính thời gian cần ngủ chính xác
            sleep_time = self.frame_delay - elapsed_time

            if sleep_time > 0:
                time.sleep(sleep_time)  # Ép video chạy đúng tốc độ gốc
            else:
                time.sleep(0.001)  # Chống treo CPU nếu máy xử lý quá chậm

    def read(self):
        # Trả về bản sao của frame mới nhất để an toàn cho đa luồng
        return self.ret, self.frame.copy() if self.ret else None

    def release(self):
        self.stopped = True
        self.cap.release()

# 2. KHỞI TẠO HÀNG ĐỢI OCR & LUỒNG XỬ LÝ OCR
ocr_queue = queue.Queue()

def ocr_worker_thread():
    """Luồng ngầm chỉ chuyên đọc chữ OCR và gửi dữ liệu"""
    while True:
        data = ocr_queue.get()
        if data is None: break

        cid, frame_crop = data
        lp_text, lp_score = read_license_plate(frame_crop)

        if lp_text:
            print(f"🚨 Phát hiện xe {lp_text} vi phạm! (ID: {cid})")
            mqtt_service.gui_bao_cao_vi_pham(lp_text)
        else:
            print(f"⚠️ Không thể đọc rõ biển số xe ID: {cid}")

        ocr_queue.task_done()

# Khởi động luồng OCR
threading.Thread(target=ocr_worker_thread, daemon=True).start()

# ==========================================
# KHỞI TẠO MÔ HÌNH VÀ CAMERA
# ==========================================
print("ĐANG TẢI MÔ HÌNH AI...")
coco_model = YOLO('yolov8n.pt')
lp_detector = YOLO('./models/license_plate_detector.pt')
mot_tracker = Sort()

print("ĐANG MỞ LUỒNG CAMERA...")
stream_vid = VideoStreamWidget(VIDEO_PATH)
stream_cam = VideoStreamWidget(0)

time.sleep(1) # Chờ camera khởi động
if not stream_vid.ret:
    print(f"LỖI: Không thể đọc file {VIDEO_PATH}")
    exit()

print("HỆ THỐNG SẴN SÀNG. Nhấn 'S' để báo vi phạm, 'Q' để thoát.")

# ==========================================
# VÒNG LẶP CHÍNH (MAIN LOOP)
# ==========================================
# ==========================================
# VÒNG LẶP CHÍNH (MAIN LOOP)
# ==========================================
while True:
    ret_vid, frame_vid = stream_vid.read()
    ret_cam, frame_cam = stream_cam.read()

    if not ret_vid: continue

    # 1. XỬ LÝ AI YOLO
    detections = coco_model(frame_vid, verbose=False)[0]
    detections_list = []
    for d in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = d
        if int(class_id) in VEHICLE_CLASSES:
            detections_list.append([x1, y1, x2, y2, score])

    # Đã dọn dẹp phần lặp code ở đây
    if len(detections_list) > 0:
        track_ids = mot_tracker.update(np.asarray(detections_list))
    else:
        track_ids = mot_tracker.update(np.empty((0, 5)))

    # --- LƯU VỊ TRÍ TÂM XE (Lọc xe đứng yên) ---
    active_ids = []
    for track in track_ids:
        x1, y1, x2, y2, car_id = track
        car_id = int(car_id)
        active_ids.append(car_id)

        cx = (x1 + x2) / 2
        cy = (y1 + y2) / 2

        if car_id not in car_positions:
            car_positions[car_id] = deque(maxlen=FRAMES_TO_TRACK)
        car_positions[car_id].append((cx, cy))

    for cid in list(car_positions.keys()):
        if cid not in active_ids:
            del car_positions[cid]
    # -----------------------------------------------

    current_frame_results = {}
    lp_detections = lp_detector(frame_vid, verbose=False)[0]

    for lp in lp_detections.boxes.data.tolist():
        x1, y1, x2, y2, score, _ = lp
        xcar1, ycar1, xcar2, ycar2, car_id = get_car(lp, track_ids)

        if car_id != -1:
            cv2.rectangle(frame_vid, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame_vid, f"ID: {int(car_id)}", (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            padding = 5
            h, w = frame_vid.shape[:2]
            y1_p = max(0, int(y1) - padding)
            y2_p = min(h, int(y2) + padding)
            x1_p = max(0, int(x1) - padding)
            x2_p = min(w, int(x2) + padding)

            current_frame_results[car_id] = {
                'box': [x1, y1, x2, y2],
                'frame_crop': frame_vid[y1_p:y2_p, x1_p:x2_p].copy()
            }

    # ==========================================================
    # 2. HIỂN THỊ TRẠNG THÁI ĐÈN LÊN GÓC MÀN HÌNH (RẤT QUAN TRỌNG ĐỂ DEBUG)
    # ==========================================================
    light_state = getattr(mqtt_service, 'current_light_state', 0)

    if light_state == 0:
        cv2.putText(frame_vid, "TRANG THAI: DEN XANH", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 3)
    elif light_state == 1:
        cv2.putText(frame_vid, "TRANG THAI: DEN VANG", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 3)
    elif light_state == 2:
        cv2.putText(frame_vid, "TRANG THAI: DEN DO", (20, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)

    # HIỂN THỊ CỬA SỔ
    cv2.namedWindow('VIDEO PHAN TICH', cv2.WINDOW_NORMAL)
    cv2.resizeWindow('VIDEO PHAN TICH', 800, 500)
    cv2.imshow('VIDEO PHAN TICH', frame_vid)

    if ret_cam and frame_cam is not None:
        cv2.putText(frame_cam, "LIVE WEBCAM", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.namedWindow('WEBCAM GIAM SAT', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('WEBCAM GIAM SAT', 640, 480)
        cv2.imshow('WEBCAM GIAM SAT', frame_cam)

    # ==========================================================
    # 3. LOGIC KÍCH HOẠT TỰ ĐỘNG BẰNG CẢM BIẾN (CHỈ LÚC ĐÈN ĐỎ)
    # ==========================================================
    key = cv2.waitKey(1) & 0xFF
    if key == ord('q') or key == ord('Q'):
        break

    # Kiểm tra: Đèn phải ĐỎ (2) và Cảm biến bị chắn (True)
    if light_state == 2 and getattr(mqtt_service, 'sensor_triggered', False):

        # Khóa cò ngay lập tức để không bị chụp liên thanh
        mqtt_service.sensor_triggered = False

        if not current_frame_results:
            print("⚠️ Cảm biến báo vượt, nhưng AI chưa nhìn rõ xe nào!")
        else:
            print(f"🚨 PHÁT HIỆN VƯỢT ĐÈN ĐỎ! Tiến hành lọc {len(current_frame_results)} xe...")

            for cid, data in current_frame_results.items():
                is_moving = True

                # Lọc xe đang dừng đỗ
                if cid in car_positions and len(car_positions[cid]) >= 3:
                    start_pos = car_positions[cid][0]
                    end_pos = car_positions[cid][-1]

                    distance = math.hypot(end_pos[0] - start_pos[0], end_pos[1] - start_pos[1])
                    if distance < MOVEMENT_THRESHOLD:
                        is_moving = False

                if is_moving:
                    ocr_queue.put((cid, data['frame_crop']))
                    print(f"   -> Đang đọc biển số xe ID: {cid}...")
                else:
                    print(f"   -> 🛑 Bỏ qua xe ID: {cid} vì đang dừng đỗ đúng luật.")

# Giải phóng
stream_vid.release()
stream_cam.release()
cv2.destroyAllWindows()