import string
import easyocr
import cv2
import numpy as np
import re

# Khởi tạo mô hình OCR 1 lần duy nhất để tối ưu tốc độ
reader = easyocr.Reader(['en'], gpu=False)  # Đổi thành gpu=True nếu có card đồ họa rời


def format_vn_license_plate(raw_text):
    """Hàm hậu xử lý: Ép chuẩn định dạng biển số Việt Nam"""
    text = raw_text.upper()
    text = re.sub(r'[^A-Z0-9]', '', text)

    if len(text) < 7 or len(text) > 9:
        return None

    chars = list(text)
    dict_char_to_int = {'O': '0', 'Q': '0', 'I': '1', 'Z': '2', 'B': '8', 'S': '5', 'G': '6'}
    dict_int_to_char = {'0': 'O', '1': 'I', '2': 'Z', '8': 'B', '5': 'S'}

    # 2 ký tự đầu là số (Mã tỉnh)
    for i in range(2):
        if chars[i] in dict_char_to_int:
            chars[i] = dict_char_to_int[chars[i]]

    # Ký tự thứ 3 là chữ (Series)
    if chars[2] in dict_int_to_char:
        chars[2] = dict_int_to_char[chars[2]]

    cleaned_text = "".join(chars)

    # Định dạng lại
    if len(cleaned_text) == 8:
        return f"{cleaned_text[:3]}-{cleaned_text[3:]}"
    elif len(cleaned_text) == 9:
        return f"{cleaned_text[:3]}-{cleaned_text[3:6]}.{cleaned_text[6:]}"

    return cleaned_text


def read_license_plate(license_plate_crop):
    """Hàm chính: Đọc chữ từ ảnh biển số, hỗ trợ tự động gom dòng cho biển 1 hàng & 2 hàng"""

    # 1. TIỀN XỬ LÝ ẢNH
    # Thêm viền trắng (padding) để AI không bị lẹm chữ ở sát mép ảnh
    pad = 10
    lp_padded = cv2.copyMakeBorder(license_plate_crop, pad, pad, pad, pad, cv2.BORDER_CONSTANT, value=[255, 255, 255])

    # Phóng to và chuyển xám (Bỏ nhị phân hóa để giữ nguyên nét chữ mờ)
    lp_resized = cv2.resize(lp_padded, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_CUBIC)
    lp_gray = cv2.cvtColor(lp_resized, cv2.COLOR_BGR2GRAY)

    # 1.1 Áp dụng CLAHE (Cân bằng sáng chói/bóng râm)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    lp_gray = clahe.apply(lp_gray)

    # 1.2 Áp dụng Sharpening Kernel (Làm sắc nét chữ bị mờ)
    kernel = np.array([[0, -1, 0],
                       [-1, 5, -1],
                       [0, -1, 0]])
    lp_sharpened = cv2.filter2D(lp_gray, -1, kernel)

    # 2. ĐỌC CHỮ (OCR)
    # text_threshold=0.2 để đọc được chữ mờ, mag_ratio=1.5 giúp phóng to thông minh nội tại
    detections = reader.readtext(lp_gray,
                                 allowlist='0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ',
                                 text_threshold=0.2,
                                 mag_ratio=1.5,
                                 contrast_ths=0.1,
                                 adjust_contrast=0.5)

    if not detections:
        return None, None

    # 3. THUẬT TOÁN PHÂN LOẠI 1 HÀNG / 2 HÀNG
    # Sắp xếp tạm tất cả các hộp text theo chiều dọc (Tọa độ Y từ trên xuống)
    detections.sort(key=lambda x: x[0][0][1])

    rows = []
    current_row = [detections[0]]

    for i in range(1, len(detections)):
        prev_box = current_row[-1][0]
        curr_box = detections[i][0]

        prev_y_min = prev_box[0][1]
        prev_y_max = prev_box[2][1]
        prev_height = prev_y_max - prev_y_min
        curr_y_min = curr_box[0][1]

        # Nếu độ lệch Y giữa 2 hộp chữ nhỏ hơn 1/2 chiều cao -> Cùng 1 hàng
        if abs(curr_y_min - prev_y_min) < prev_height * 0.5:
            current_row.append(detections[i])
        else:
            # Nếu lệch nhiều -> Hộp chữ rớt xuống hàng thứ 2
            rows.append(current_row)
            current_row = [detections[i]]

    rows.append(current_row)

    # 4. RÁP CHỮ
    full_text = ""
    total_score = 0
    total_boxes = 0

    # Duyệt qua từng hàng, sắp xếp chữ từ trái qua phải (Tọa độ X) rồi ghép lại
    for row in rows:
        row.sort(key=lambda x: x[0][0][0])
        for detection in row:
            bbox, text, score = detection
            full_text += text
            total_score += score
            total_boxes += 1

    avg_score = total_score / total_boxes if total_boxes > 0 else 0

    # 5. HẬU XỬ LÝ ĐỊNH DẠNG
    final_text = format_vn_license_plate(full_text)

    if final_text:
        return final_text, avg_score
    else:
        return None, None


def get_car(license_plate, vehicle_track_ids):
    """Lấy tọa độ và ID của xe chứa biển số (Dùng cho Tracking)"""
    x1, y1, x2, y2, score, class_id = license_plate

    foundIt = False
    car_indx = -1
    for j in range(len(vehicle_track_ids)):
        xcar1, ycar1, xcar2, ycar2, car_id = vehicle_track_ids[j]

        if x1 > xcar1 and y1 > ycar1 and x2 < xcar2 and y2 < ycar2:
            car_indx = j
            foundIt = True
            break

    if foundIt:
        return vehicle_track_ids[car_indx]

    return -1, -1, -1, -1, -1