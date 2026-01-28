import cv2
from ultralytics import YOLO
import os
import time

# --- CONFIGURATION ---
WIFI_ADAPTER_NAME = "Wi-Fi"   # Check 'Network Connections' if this name is wrong
MAX_BAD_BEHAVIOR_SECONDS = 5  # Seconds allowed before kill
CONFIDENCE_THRESHOLD = 0.5    # 0.5 = 50% sure

# --- COMMANDS ---
def set_wifi(state):
    """Enables or Disables Wi-Fi using Windows Netsh command."""
    status = "enable" if state else "disable"
    cmd = f'netsh interface set interface "{WIFI_ADAPTER_NAME}" {status}'
    os.system(cmd)
    
    if state:
        print(" Wi-Fi RESTORED")
    else:
        print(" Wi-Fi KILLED")

# --- LOAD AI ---
print("Loading AI Model... (Downloads on first run)")
model = YOLO('yolov8n.pt') 

# --- MAIN LOOP ---
cap = cv2.VideoCapture(0)
cap.set(3, 1280) 
cap.set(4, 720)

bad_behavior_start_time = None
wifi_is_on = True

print("--- FOCUS BOT STARTED ---")
print("Press 'q' to quit.")

try:
    while True:
        success, img = cap.read()
        if not success:
            break

        # AI Detection
        results = model(img, stream=True, verbose=False)

        person_found = False
        phone_found = False

        for r in results:
            boxes = r.boxes
            for box in boxes:
                cls_id = int(box.cls[0])
                current_class = model.names[cls_id]
                conf = box.conf[0]

                if conf > CONFIDENCE_THRESHOLD:
                    if current_class == 'person':
                        person_found = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 255, 0), 2)
                        
                    elif current_class == 'cell phone':
                        phone_found = True
                        x1, y1, x2, y2 = map(int, box.xyxy[0])
                        cv2.rectangle(img, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        cv2.putText(img, "PHONE!", (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)

        # --- JUDGE BEHAVIOR ---
        is_behaving = True
        status_msg = "FOCUSED"

        if not person_found:
            is_behaving = False
            status_msg = "USER MISSING"

        if phone_found:
            is_behaving = False
            status_msg = "PHONE DETECTED"

        # --- PUNISHMENT ---
        if is_behaving:
            bad_behavior_start_time = None
            if not wifi_is_on:
                set_wifi(True)
                wifi_is_on = True
            
            cv2.rectangle(img, (0,0), (200, 50), (0,255,0), cv2.FILLED)
            cv2.putText(img, "GOOD", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

        else:
            if bad_behavior_start_time is None:
                bad_behavior_start_time = time.time()
            
            elapsed = time.time() - bad_behavior_start_time
            remaining = MAX_BAD_BEHAVIOR_SECONDS - elapsed

            cv2.rectangle(img, (0,0), (500, 50), (0,0,255), cv2.FILLED)
            cv2.putText(img, f"{status_msg}: KILL IN {max(0, remaining):.1f}s", (10, 35), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)

            if elapsed > MAX_BAD_BEHAVIOR_SECONDS and wifi_is_on:
                set_wifi(False)
                wifi_is_on = False

        cv2.imshow("Focus Bot", img)
        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:
    print("Script closing... Restoring Wi-Fi.")
    set_wifi(True)
    cap.release()
    cv2.destroyAllWindows()