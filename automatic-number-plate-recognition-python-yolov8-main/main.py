import cv2
import numpy as np
from ultralytics import YOLO
from sort.sort import *
from util import get_car, read_license_plate
import mqtt_service 

# CẤU HÌNH
VIDEO_PATH = './test.mp4'
VEHICLE_CLASSES = [2, 3, 5, 7]

# KHỞI TẠO MÔ HÌNH AI
print("ĐANG TẢI MÔ HÌNH AI")
coco_model = YOLO('yolov8n.pt')
lp_detector = YOLO('./models/license_plate_detector.pt')
mot_tracker = Sort()

# MỞ 2 NGUỒN HÌNH ẢNH SONG SONG
cap_video = cv2.VideoCapture(VIDEO_PATH)
cap_webcam = cv2.VideoCapture(0)  # Mở kết nối Webcam

if not cap_video.isOpened():
    print(f"LỖI: Không thể mở file video tại {VIDEO_PATH}")
    exit()

if not cap_webcam.isOpened():
    print("Cảnh báo: Không tìm thấy Webcam. Cửa sổ Webcam sẽ không hiện.")

print("HỆ THỐNG SẴN SÀNG. Nhấn 'S' để báo vi phạm, 'Q' để thoát.")

while True:
    # Đọc khung hình từ cả 2 nguồn
    ret_vid, frame_vid = cap_video.read()
    ret_cam, frame_cam = cap_webcam.read()

    if not ret_vid:
        print("🏁 Kết thúc video test.mp4.")
        break

    # 1. XỬ LÝ AI TRÊN VIDEO (TEST.MP4)
    detections = coco_model(frame_vid, verbose=False)[0]
    detections_list = []
    for d in detections.boxes.data.tolist():
        x1, y1, x2, y2, score, class_id = d
        if int(class_id) in VEHICLE_CLASSES:
            detections_list.append([x1, y1, x2, y2, score])

    if len(detections_list) > 0:
        track_ids = mot_tracker.update(np.asarray(detections_list))
    else:
        track_ids = mot_tracker.update(np.empty((0, 5)))

    current_frame_results = {}

    lp_detections = lp_detector(frame_vid, verbose=False)[0]
    for lp in lp_detections.boxes.data.tolist():
        x1, y1, x2, y2, score, _ = lp
        xcar1, ycar1, xcar2, ycar2, car_id = get_car(lp, track_ids)

        if car_id != -1:
            # Vẽ khung lên video
            cv2.rectangle(frame_vid, (int(x1), int(y1)), (int(x2), int(y2)), (0, 255, 0), 2)
            cv2.putText(frame_vid, f"ID: {int(car_id)}", (int(x1), int(y1) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

            current_frame_results[car_id] = {
                'box': [x1, y1, x2, y2],
                'frame_crop': frame_vid[int(y1):int(y2), int(x1):int(x2)]
            }

    # 2. HIỂN THỊ SONG SONG 2 CỬA SỔ
    # Cửa sổ 1: Video phân tích AI
    cv2.imshow('VIDEO PHAN TICH (Nhan S de bao vi pham)', frame_vid)

    # Cửa sổ 2: Webcam trực tiếp
    if ret_cam:
        cv2.putText(frame_cam, "LIVE WEBCAM", (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
        cv2.imshow('WEBCAM GIAM SAT', frame_cam)

    # 3. XỬ LÝ PHÍM BẤM
    key = cv2.waitKey(1) & 0xFF

    if key == ord('s') or key == ord('S'):
        if not current_frame_results:
            print("Không tìm thấy biển số nào trong video để báo cáo!")
        else:
            print(f" Đang trích xuất OCR cho {len(current_frame_results)} xe...")
            for cid, data in current_frame_results.items():
                lp_gray = cv2.cvtColor(data['frame_crop'], cv2.COLOR_BGR2GRAY)
                lp_text, lp_score = read_license_plate(lp_gray)

                if lp_text:
                    print(f"Phát hiện xe {lp_text} vi phạm!")
                    # GỌI HÀM TỪ FILE Script_Webcam.py BẠN VỪA GỬI
                    mqtt_service.gui_bao_cao_vi_pham(lp_text)
                else:
                    print(f"Không thể đọc rõ biển số xe ID: {cid}")

    elif key == ord('q') or key == ord('Q'):
        break

# Giải phóng toàn bộ camera và video
cap_video.release()
if cap_webcam.isOpened():
    cap_webcam.release()
cv2.destroyAllWindows()