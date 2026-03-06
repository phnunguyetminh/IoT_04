#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <WiFi.h>
#include "time.h"
#include <PubSubClient.h> 

// 1. KHAI BÁO CẤU HÌNH
const char* ssid       = "Wokwi-GUEST"; 
const char* password   = "";
const char* mqtt_server = "broker.hivemq.com"; 
const char* mqtt_topic  = "traffic/violation/Random4";

// Khai báo chân
const int TRIG_PIN = 5;
const int ECHO_PIN = 18;
const int LED_RED = 14;
const int LED_YELLOW = 27;
const int LED_GREEN = 26;
const int BUZZER = 13;

// 2. KHAI BÁO BIẾN TOÀN CỤC
WiFiClient espClient;
PubSubClient client(espClient);
LiquidCrystal_I2C lcd(0x27, 16, 2);

int violationCount = 0;
int timerCounter = 0;
int trafficState = 0; 
int activeGreenTime = 10;
int activeRedTime   = 40;
int TIME_YELLOW = 4;

bool wifiConnected = false;
bool isObjectDetected = false;
bool showViolationMessage = false;
unsigned long previousMillis = 0;
unsigned long violationDisplayStart = 0;

// 3. CÁC HÀM HỖ TRỢ 

void updateLCDViolation() {
  lcd.setCursor(11, 1); 
  lcd.print("V:");
  lcd.print(violationCount);
}

// Hàm callback nhận tin nhắn từ Python
void callback(char* topic, byte* payload, unsigned int length) {
  // Biến payload thành chuỗi chữ (String) để dễ đọc
  payload[length] = '\0'; 
  String msg = String((char*)payload);
  
  // 1. NẾU NHẬN LỆNH ĐỔI THỜI GIAN TỪ WEB (Kênh traffic/command/Random4)
  if (String(topic) == "traffic/command/Random4") {
    int r, y, g;
    // Tách chuỗi "40,4,10" thành 3 số nguyên r, y, g
    if (sscanf((char*)payload, "%d,%d,%d", &r, &y, &g) == 3) {
      activeRedTime = r;
      TIME_YELLOW = y;
      activeGreenTime = g;
      Serial.println("✅ Đã cập nhật thời gian từ Web!");
    }
  }
  Serial.println("\n--- CO TIN HIEU TU PYTHON ---");
  if (trafficState == 2) { 
    violationCount++;
    showViolationMessage = true;
    violationDisplayStart = millis();
    updateLCDViolation();
    tone(BUZZER, 1000, 200);
    Serial.println("Ket qua: VI PHAM!");
  } else {
    Serial.println("Ket qua: Bo qua (Dang den xanh/vang)");
  }
}

void reconnect() {
  while (!client.connected()) {
    Serial.print("Dang ket noi MQTT...");
    if (client.connect("ESP32_Traffic_Wokwi_User")) {
      Serial.println("OK");
      client.subscribe(mqtt_topic); // Kênh hiện tại (traffic/violation/Random4)
      client.subscribe("traffic/command/Random4"); // THÊM DÒNG NÀY ĐỂ NHẬN LỆNH CÀI ĐẶT
    } else {
      Serial.print("Loi: "); Serial.print(client.state());
      delay(5000);
    }
  }
}

void changeState(int state) {
  digitalWrite(LED_RED, LOW);
  digitalWrite(LED_YELLOW, LOW);
  digitalWrite(LED_GREEN, LOW);
  
  switch (state) {
    case 0: digitalWrite(LED_GREEN, HIGH); timerCounter = activeGreenTime; break;
    case 1: digitalWrite(LED_YELLOW, HIGH); timerCounter = TIME_YELLOW; break;
    case 2: digitalWrite(LED_RED, HIGH); timerCounter = activeRedTime; break;
  }
  
  if (!showViolationMessage) {
    lcd.setCursor(0, 0);
    if (state == 0) lcd.print("DEN: XANH (DI)  ");
    else if (state == 1) lcd.print("DEN: VANG (CHAM)");
    else lcd.print("DEN: DO (DUNG)  ");
  }
}

// 4. HÀM SETUP
void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n--- KHOI DONG ---");

  // Khai báo chân Pin
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  pinMode(LED_RED, OUTPUT);
  pinMode(LED_YELLOW, OUTPUT);
  pinMode(LED_GREEN, OUTPUT);
  pinMode(BUZZER, OUTPUT);

  lcd.init();
  lcd.backlight();
  
  lcd.setCursor(0, 0);
  lcd.print("Connecting WiFi...");

  // Cấu hình WiFi chuẩn hơn
  WiFi.mode(WIFI_STA); // Đảm bảo ESP32 ở chế độ Station
  WiFi.begin(ssid, password);
  
  Serial.print("Connecting to WiFi");
  // Tăng thời gian chờ lên (ví dụ 40 lần ~ 20 giây)
  int retry = 0;
  while (WiFi.status() != WL_CONNECTED && retry < 40) {
    delay(500);
    Serial.print(".");
    retry++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    wifiConnected = true;
    Serial.println("\nWiFi OK!");
    Serial.print("IP Address: "); Serial.println(WiFi.localIP());
    
    client.setServer(mqtt_server, 1883);
    client.setCallback(callback);
  } else {
    // Nếu vẫn lỗi, in ra trạng thái để chẩn đoán
    Serial.printf("\nWiFi Failed! Status: %d\n", WiFi.status());
    lcd.clear();
    lcd.print("WiFi Error!");
    delay(2000);
  }

  lcd.clear();
  changeState(0);
}

// --- THÊM LẠI HÀM CẢM BIẾN ---
void checkSensor() {
  digitalWrite(TRIG_PIN, LOW); delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  long duration = pulseIn(ECHO_PIN, HIGH);
  int distance = duration * 0.034 / 2;

  if (distance > 0 && distance < 50) {
    if (!isObjectDetected) {
      violationCount++;
      showViolationMessage = true;
      violationDisplayStart = millis();
      isObjectDetected = true; // Chống đếm trùng
      updateLCDViolation();
      tone(BUZZER, 1000, 200);
      Serial.println("-> VI PHAM tu Cam bien Sieu am!");
    }
  } else {
    isObjectDetected = false;
  }
}

void loop() {
  if (wifiConnected) {
    if (!client.connected()) reconnect();
    client.loop();
  }

  unsigned long currentMillis = millis();
  if (currentMillis - previousMillis >= 1000) {
    previousMillis = currentMillis;
    timerCounter--;

    // --- THÊM 3 DÒNG NÀY ĐỂ BẮN DỮ LIỆU LÊN WEB ---
    char statusPayload[50];
    sprintf(statusPayload, "{\"light\":%d,\"time\":%d}", trafficState, timerCounter);
    client.publish("traffic/status/Random4", statusPayload);
    // ----------------------------------------------
    
    lcd.setCursor(0, 1);
    lcd.print("T:");
    if(timerCounter < 10) lcd.print("0");
    lcd.print(timerCounter);
    lcd.print("s      ");
    updateLCDViolation();

    if (timerCounter < 0) {
      trafficState++;
      if (trafficState > 2) trafficState = 0;
      changeState(trafficState);
    }
  }

  // --- QUAN TRỌNG: GỌI CẢM BIẾN KHI ĐÈN ĐỎ ---
  if (trafficState == 2) {
    checkSensor(); 
  }

  // Hien thi tin nhan vi pham
  if(showViolationMessage){
    lcd.setCursor(0,0);
    lcd.print("Co nguoi vuot   "); 
    if(millis() - violationDisplayStart > 2000){
      showViolationMessage = false;

      lcd.setCursor(0, 0);
      if (trafficState == 0) lcd.print("DEN: XANH (DI) ");
      else if (trafficState == 1) lcd.print("DEN: VANG (CHAM)");
      else if (trafficState == 2) lcd.print("DEN: DO (DUNG)");
    }
  }
}