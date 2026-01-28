import cv2
import numpy as np
import mediapipe as mp
import time
import math
import pytesseract
import speech_recognition as sr
import threading
from PIL import Image

# --- CONFIGURATION ---
# Ensure Tesseract is installed at this path
pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'

# --- TIMING ---
BOX_LOCK_TIME = 0.6         
BOX_COOLDOWN = 7.0          
MOVE_COOLDOWN = 2.0         
HOVER_TO_ACTIVATE = 0.5     
WORD_CONVERT_DELAY = 1.2    

# --- VISUALS ---
CASUAL_FONT = cv2.FONT_HERSHEY_SCRIPT_SIMPLEX 
FIXED_FONT_SCALE = 1.0      
LINE_SPACING = 35           
BRUSH_SIZE = 8
POINTER_SIZE = 6

# Colors
PURPLE = (255, 0, 255); BLUE = (255, 0, 0); GREEN = (0, 255, 0)
RED = (0, 0, 255); ERASER = (0, 0, 0); WHITE = (255, 255, 255)
SAFE_COLOR = (0, 255, 0); GOLD = (0, 215, 255); CYAN = (255, 255, 0)
GREY = (100, 100, 100); DARK_GRAY = (40, 40, 40)

# --- STATE ---
current_stroke = [] 
undo_stack = []
voice_boxes = [] 

draw_color = PURPLE
is_writing = False
is_moving_box = False
moving_box_idx = -1

# Gestures
is_two_handed = False
box_stable_start = 0
last_box_time = 0
last_move_time = 0          
prev_box_coords = (0,0,0,0)

# Timers
hover_start = 0
action_timer = 0
word_min_x, word_max_x = 10000, 0
word_min_y, word_max_y = 10000, 0
prev_x, prev_y = 0, 0
prev_hover_x, prev_hover_y = 0, 0
saved_feedback_timer = 0

# --- SETUP ---
# INTERNAL PROCESSING RESOLUTION (Keep low for speed)
PROC_W, PROC_H = 640, 480
# DISPLAY RESOLUTION (High for viewing)
DISP_W, DISP_H = 1280, 720

cap = cv2.VideoCapture(0)
cap.set(3, PROC_W)
cap.set(4, PROC_H)

success, img = cap.read()
if not success: 
    print("Error: Camera not found")
    exit()

mp_hands = mp.solutions.hands
hands = mp_hands.Hands(max_num_hands=2, model_complexity=0, min_detection_confidence=0.7)
mp_draw = mp.solutions.drawing_utils

img_canvas = np.zeros((PROC_H, PROC_W, 3), np.uint8)   
text_canvas = np.zeros((PROC_H, PROC_W, 3), np.uint8)  
temp_canvas = np.zeros((PROC_H, PROC_W, 3), np.uint8)  

# --- SMOOTHING (Gap Filling) ---
def calculate_smooth_curve(points, steps=10):
    if len(points) < 4: return points
    smooth_points = []
    for i in range(len(points) - 3):
        p0, p1, p2, p3 = points[i], points[i+1], points[i+2], points[i+3]
        for t in np.linspace(0, 1, steps):
            t2 = t*t; t3 = t2*t
            x = 0.5 * ((2*p1[0]) + (-p0[0]+p2[0])*t + (2*p0[0]-5*p1[0]+4*p2[0]-p3[0])*t2 + (-p0[0]+3*p1[0]-3*p2[0]+p3[0])*t3)
            y = 0.5 * ((2*p1[1]) + (-p0[1]+p2[1])*t + (2*p0[1]-5*p1[1]+4*p2[1]-p3[1])*t2 + (-p0[1]+3*p1[1]-3*p2[1]+p3[1])*t3)
            smooth_points.append((int(x), int(y)))
    return smooth_points

# --- HELPER FUNCTIONS ---
def save_state():
    if len(undo_stack) > 8: undo_stack.pop(0)
    boxes_copy = [b.copy() for b in voice_boxes]
    undo_stack.append((img_canvas.copy(), text_canvas.copy(), boxes_copy))

def perform_undo():
    global img_canvas, text_canvas, voice_boxes
    if undo_stack:
        i, t, v = undo_stack.pop()
        img_canvas = i; text_canvas = t; voice_boxes = v
        print("Undo Performed")

def save_as_pdf(final_image):
    try:
        rgb = cv2.cvtColor(final_image, cv2.COLOR_BGR2RGB)
        Image.fromarray(rgb).save("SmartBoard_Notes.pdf", "PDF", resolution=100.0)
        return True
    except: return False

def wrap_text(text, box_width):
    if not text: return []
    text = text.strip()
    if len(text) > 0: text = text[0].upper() + text[1:] 
    words = text.split(); lines = []; current_line = ""
    for word in words:
        test_line = current_line + " " + word if current_line else word
        (w, h), _ = cv2.getTextSize(test_line, CASUAL_FONT, FIXED_FONT_SCALE, 2)
        if w < box_width - 20: current_line = test_line
        else:
            if current_line: lines.append(current_line)
            current_line = word
    if current_line: lines.append(current_line)
    return lines

# --- HIGH SENSITIVITY VOICE THREAD ---
def continuous_listen_thread(box_idx):
    r = sr.Recognizer()
    
    # !!! SENSITIVITY FIX !!!
    r.dynamic_energy_threshold = False  # STOP auto-adjusting
    r.energy_threshold = 150            # High Sensitivity (Hear Whispers)
    r.pause_threshold = 0.8
    
    voice_boxes[box_idx]['status'] = "Ready"
    voice_boxes[box_idx]['color'] = RED
    voice_boxes[box_idx]['recording'] = True
    if 'text' not in voice_boxes[box_idx] or voice_boxes[box_idx]['text'] == "...":
        voice_boxes[box_idx]['text'] = ""

    print(f"--- DEBUG: Listening on Box {box_idx} ---")

    with sr.Microphone() as source:
        try:
            voice_boxes[box_idx]['status'] = "Listening..."
            
            while voice_boxes[box_idx]['recording']:
                try:
                    # Listen loop
                    audio = r.listen(source, timeout=1.0, phrase_time_limit=10.0)
                    
                    voice_boxes[box_idx]['status'] = "Processing..."
                    print("Processing Audio...")
                    
                    text_chunk = r.recognize_google(audio)
                    print(f"SUCCESS: '{text_chunk}'")
                    
                    current = voice_boxes[box_idx]['text']
                    if current == "": voice_boxes[box_idx]['text'] = text_chunk
                    else: voice_boxes[box_idx]['text'] += " " + text_chunk
                    
                    voice_boxes[box_idx]['status'] = "Listening..."
                    
                except sr.WaitTimeoutError:
                    pass 
                except sr.UnknownValueError:
                    print("Audio detected but not understood.")
                except Exception as e:
                    print(f"Error: {e}")
                    
        except Exception as e:
            print(f"Mic Access Error: {e}")

    voice_boxes[box_idx]['status'] = "" 
    voice_boxes[box_idx]['color'] = CYAN
    print("--- DEBUG: Stopped Listening ---")

def start_recording(box_idx):
    threading.Thread(target=continuous_listen_thread, args=(box_idx,)).start()

def enhance_image_for_ocr(roi):
    if roi.size == 0: return roi
    gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
    _, binary = cv2.threshold(gray, 20, 255, cv2.THRESH_BINARY)
    h, w = roi.shape[:2]; scale = 60 / h
    if scale > 0:
        resized = cv2.resize(binary, (int(w * scale), 60))
        kernel = np.ones((3,3), np.uint8)
        thickened = cv2.dilate(resized, kernel, iterations=1)
        return cv2.bitwise_not(cv2.copyMakeBorder(thickened, 10, 10, 10, 10, cv2.BORDER_CONSTANT, value=0))
    return binary

def convert_word_to_text():
    global word_min_x, word_max_x, word_min_y, word_max_y, img_canvas, text_canvas
    if word_min_x == 10000: return
    pad = 20
    y1 = max(0, word_min_y - pad); y2 = min(PROC_H, word_max_y + pad)
    x1 = max(0, word_min_x - pad); x2 = min(PROC_W, word_max_x + pad)
    roi = img_canvas[y1:y2, x1:x2].copy()
    try:
        final_img = enhance_image_for_ocr(roi)
        text = pytesseract.image_to_string(final_img, config=r'--psm 7').strip()
        if text:
            save_state()
            scale = max(0.8, (y2-y1)/80.0)
            cv2.putText(text_canvas, text, (x1, y2-10), CASUAL_FONT, scale, draw_color, 2)
            cv2.rectangle(img_canvas, (x1, y1), (x2, y2), (0,0,0), -1)
    except: pass
    word_min_x, word_max_x = 10000, 0; word_min_y, word_max_y = 10000, 0

# --- UI ---
def draw_ui(img):
    cv2.rectangle(img, (PROC_W//2 - 150, 0), (PROC_W//2 + 150, 60), DARK_GRAY, -1)
    btns = [{"c":BLUE, "x":PROC_W//2 - 100}, {"c":GREEN, "x":PROC_W//2 - 50},
            {"c":RED, "x":PROC_W//2}, {"c":PURPLE, "x":PROC_W//2 + 50}, {"c":CYAN, "x":PROC_W//2 + 100}]
    for b in btns:
        cv2.circle(img, (b["x"], 30), 18, b["c"], -1)
        if draw_color == b["c"]: cv2.circle(img, (b["x"], 30), 22, WHITE, 2)
        if b["c"] == CYAN: cv2.putText(img, "MIC", (b["x"]-14, 34), cv2.FONT_HERSHEY_PLAIN, 0.8, (0,0,0), 1)

    status = "SAFE MODE"; col = SAFE_COLOR
    move_cd_rem = MOVE_COOLDOWN - (time.time() - last_move_time)
    if is_two_handed: status = "BOX CREATION"; col = CYAN
    elif is_moving_box: status = "MOVING"; col = GOLD
    elif is_writing: status = "WRITING"; col = PURPLE
    elif move_cd_rem > 0: status = "COOLDOWN"; col = GREY
    
    cv2.rectangle(img, (10, 10), (160, 40), col, -1)
    cv2.putText(img, status, (15, 30), cv2.FONT_HERSHEY_PLAIN, 1.2, WHITE, 2)
    if time.time() - saved_feedback_timer < 2.0:
        cv2.putText(img, "PDF SAVED!", (PROC_W - 200, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.8, GREEN, 2)
    return img, btns

def check_click(x, y, btns):
    global draw_color
    for b in btns:
        if math.hypot(x - b["x"], y - 30) < 25: draw_color = b["c"]

# --- MAIN LOOP ---
print("--- JARVIS READY ---")
print("High Sensitivity Mode Active. Watch terminal for voice logs.")

while True:
    success, img = cap.read()
    if not success: break
    img = cv2.flip(img, 1)
    now = time.time()
    
    # Writing Logic with AI Smoothing
    if action_timer != 0 and (now - action_timer > WORD_CONVERT_DELAY) and word_min_x != 10000:
        if len(current_stroke) > 4:
            smooth_pts = calculate_smooth_curve(current_stroke)
            pts = np.array(smooth_pts, np.int32).reshape((-1, 1, 2))
            cv2.polylines(img_canvas, [pts], False, draw_color, BRUSH_SIZE)
            temp_canvas = np.zeros((PROC_H, PROC_W, 3), np.uint8)
            current_stroke = [] 
        convert_word_to_text()
        action_timer = 0

    img, btns = draw_ui(img)
    img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = hands.process(img_rgb)
    fingers = [] 

    if results.multi_hand_landmarks:
        for lm in results.multi_hand_landmarks:
            mp_draw.draw_landmarks(img, lm, mp_hands.HAND_CONNECTIONS)
            idx = lm.landmark[8]; thm = lm.landmark[4]; mid = lm.landmark[12]
            ix, iy = int(idx.x * PROC_W), int(idx.y * PROC_H)
            tx, ty = int(thm.x * PROC_W), int(thm.y * PROC_H)
            mx, my = int(mid.x * PROC_W), int(mid.y * PROC_H)
            idx_up = idx.y < lm.landmark[6].y
            mid_up = lm.landmark[12].y < lm.landmark[10].y
            fingers.append({'i': (ix, iy), 't': (tx, ty), 'm': (mx, my), 'idx_up': idx_up, 'mid_up': mid_up})

    # LOGIC 1: TWO-HANDED BOX
    if len(fingers) == 2 and (now - last_box_time > BOX_COOLDOWN):
        is_two_handed = True
        h1, h2 = fingers[0], fingers[1]
        x_min = min(h1['i'][0], h2['i'][0]); x_max = max(h1['i'][0], h2['i'][0])
        y_min = min(h1['i'][1], h2['i'][1]); y_max = max(h1['t'][1], h2['t'][1])
        w, h = x_max - x_min, y_max - y_min
        
        if box_stable_start == 0:
            box_stable_start = now
            prev_box_coords = (x_min, y_min, w, h)
        
        px, py, pw, ph = prev_box_coords
        diff = abs(x_min-px) + abs(y_min-py) + abs(w-pw) + abs(h-ph)
        prev_box_coords = (x_min, y_min, w, h)
        
        if diff < 30 and w > 50 and h > 50:
            elapsed = now - box_stable_start
            color = CYAN
            prog = int((elapsed / BOX_LOCK_TIME) * w)
            cv2.rectangle(img, (x_min, y_max-10), (x_min+prog, y_max), RED, -1)
            
            if elapsed > BOX_LOCK_TIME:
                save_state()
                new_box = {'x':x_min, 'y':y_min, 'w':w, 'h':h, 'text':"...", 'color':RED, 'recording':False}
                voice_boxes.append(new_box)
                start_recording(len(voice_boxes)-1)
                last_box_time = now; box_stable_start = 0; is_two_handed = False
            cv2.rectangle(img, (x_min, y_min), (x_max, y_max), color, 3)
        else:
            box_stable_start = now 
            cv2.rectangle(img, (x_min, y_min), (x_max, y_max), CYAN, 2)
    else:
        is_two_handed = False; box_stable_start = 0

    # LOGIC 2: ONE-HANDED
    if len(fingers) == 1:
        hand = fingers[0]
        ix, iy = hand['i']
        
        if (now - last_move_time) > MOVE_COOLDOWN:
            
            # CHECK IF HAND IS INSIDE ANY BOX
            is_inside_any_box = False
            for box in voice_boxes:
                if box['x'] < ix < box['x']+box['w'] and box['y'] < iy < box['y']+box['h']:
                    is_inside_any_box = True
                    break

            # GESTURE: HOVER / MOVE / RE-SPEAK (Two Fingers)
            if hand['idx_up'] and hand['mid_up']:
                if iy < 100: check_click(ix, iy, btns)
                hovering = -1; hovering_stop = -1
                
                for i, box in enumerate(voice_boxes):
                    if box['x'] < ix < box['x']+box['w'] and box['y'] < iy < box['y']+box['h']: hovering = i
                    if box.get('recording', False):
                        stop_x, stop_y = box['x'] + box['w'] + 10, box['y']
                        if stop_x < ix < stop_x+50 and stop_y < iy < stop_y+50: hovering_stop = i

                if hovering_stop != -1:
                    cv2.circle(img, (ix, iy), 10, RED, 2)
                    if math.hypot(ix - prev_hover_x, iy - prev_hover_y) < 10:
                        if hover_start == 0: hover_start = now
                        if (now - hover_start) > HOVER_TO_ACTIVATE:
                            voice_boxes[hovering_stop]['recording'] = False; hover_start = 0
                    else: hover_start = 0; prev_hover_x, prev_hover_y = ix, iy

                elif hovering != -1 and draw_color == CYAN and not is_moving_box:
                    if not voice_boxes[hovering].get('recording', False):
                        cv2.circle(img, (ix, iy), 10, RED, 2); cv2.putText(img, "RE-SPEAK", (ix+15, iy), cv2.FONT_HERSHEY_PLAIN, 1, RED, 2)
                        if math.hypot(ix - prev_hover_x, iy - prev_hover_y) < 10:
                            if hover_start == 0: hover_start = now
                            if (now - hover_start) > HOVER_TO_ACTIVATE:
                                start_recording(hovering); hover_start = 0
                        else: hover_start = 0; prev_hover_x, prev_hover_y = ix, iy

                elif hovering != -1 and not is_moving_box:
                    if not voice_boxes[hovering].get('recording', False):
                        cv2.circle(img, (ix, iy), 10, GOLD, 2)
                        if math.hypot(ix - prev_hover_x, iy - prev_hover_y) < 10:
                            if hover_start == 0: hover_start = now
                            if (now - hover_start) > HOVER_TO_ACTIVATE:
                                is_moving_box = True; moving_box_idx = hovering; hover_start = 0
                        else: hover_start = 0; prev_hover_x, prev_hover_y = ix, iy

                elif is_moving_box:
                    cv2.circle(img, (ix, iy), 15, GOLD, -1)
                    box = voice_boxes[moving_box_idx]
                    box['x'] = ix - box['w']//2; box['y'] = iy - box['h']//2
                    if math.hypot(ix - prev_hover_x, iy - prev_hover_y) < 5:
                         if hover_start == 0: hover_start = now
                         if (now - hover_start) > HOVER_TO_ACTIVATE:
                             is_moving_box = False; last_move_time = now; hover_start = 0
                    else: hover_start = 0; prev_hover_x, prev_hover_y = ix, iy
                else: cv2.circle(img, (ix, iy), 5, SAFE_COLOR, -1)
            
            # GESTURE: WRITE (One Finger) - BLOCKED IF INSIDE BOX
            elif hand['idx_up'] and not hand['mid_up'] and draw_color != CYAN:
                
                if is_inside_any_box:
                    cv2.circle(img, (ix, iy), 5, RED, -1)
                else:
                    if not is_writing:
                        cv2.circle(img, (ix, iy), 5, SAFE_COLOR, -1)
                        if math.hypot(ix - prev_hover_x, iy - prev_hover_y) < 5:
                             if hover_start == 0: hover_start = now
                             if (now - hover_start) > HOVER_TO_ACTIVATE:
                                 is_writing = True; hover_start = 0; prev_x, prev_y = ix, iy
                        else: hover_start = 0; prev_hover_x, prev_hover_y = ix, iy
                    else:
                        action_timer = now
                        if iy > 60:
                            word_min_x = min(word_min_x, ix); word_max_x = max(word_max_x, ix)
                            word_min_y = min(word_min_y, iy); word_max_y = max(word_max_y, iy)
                            # Gap Fill
                            dist = math.hypot(ix - prev_x, iy - prev_y)
                            if dist < 50:
                                current_stroke.append((ix, iy))
                                if len(current_stroke) > 1:
                                    cv2.line(temp_canvas, current_stroke[-2], current_stroke[-1], draw_color, BRUSH_SIZE)
                            else:
                                mid_x, mid_y = (ix + prev_x)//2, (iy + prev_y)//2
                                current_stroke.append((mid_x, mid_y)); current_stroke.append((ix, iy))
                                cv2.line(temp_canvas, (prev_x, prev_y), (ix, iy), draw_color, BRUSH_SIZE)
                            prev_x, prev_y = ix, iy
                            cv2.circle(img, (ix, iy), POINTER_SIZE, draw_color, -1)
        else: cv2.circle(img, (ix, iy), 5, GREY, -1)

    # RENDER BOXES
    for box in voice_boxes:
        lines = wrap_text(box['text'], box['w'])
        req_h = len(lines) * LINE_SPACING + 40 
        if req_h > box['h']: box['h'] = req_h
        x, y, w, h = box['x'], box['y'], box['w'], box['h']
        
        sub = img[y:y+h, x:x+w]
        if sub.shape[0]>0 and sub.shape[1]>0:
            white = np.full(sub.shape, 255, dtype=np.uint8)
            img[y:y+h, x:x+w] = cv2.addWeighted(sub, 0.7, white, 0.3, 1.0)
        cv2.rectangle(img, (x, y), (x+w, y+h), box['color'], 2)
        
        if box.get('recording', False):
            bx, by = x + w + 10, y
            cv2.rectangle(img, (bx, by), (bx+50, by+50), RED, -1)
            cv2.putText(img, "STOP", (bx+5, by+30), cv2.FONT_HERSHEY_PLAIN, 1, WHITE, 1)
            status_txt = box.get('status', 'Listening...')
            cv2.putText(img, status_txt, (x+10, y+30), CASUAL_FONT, 0.8, (50,50,50), 2)

        if not lines and not box.get('recording', False):
            cv2.putText(img, "...", (x+10, y+30), CASUAL_FONT, 1, (50,50,50), 2)
        else:
            for i, line in enumerate(lines):
                cv2.putText(img, line, (x+10, y + 35 + (i*LINE_SPACING)), CASUAL_FONT, FIXED_FONT_SCALE, (0,0,0), 2)

    k = cv2.waitKey(1) & 0xFF
    if k == ord('q'): break
    if k == ord('c'): img_canvas[:] = 0; text_canvas[:] = 0; voice_boxes = []
    if k == ord('z') or k == 26: perform_undo()
    if k == 19: save_as_pdf(img); saved_feedback_timer = time.time()

    combined_ink = cv2.add(img_canvas, temp_canvas)
    gray = cv2.cvtColor(combined_ink, cv2.COLOR_BGR2GRAY)
    _, mask_ink = cv2.threshold(gray, 10, 255, cv2.THRESH_BINARY)
    gray_txt = cv2.cvtColor(text_canvas, cv2.COLOR_BGR2GRAY)
    _, mask_txt = cv2.threshold(gray_txt, 10, 255, cv2.THRESH_BINARY)
    full_mask = cv2.bitwise_or(mask_ink, mask_txt)
    img = cv2.bitwise_and(img, img, mask=cv2.bitwise_not(full_mask))
    img = cv2.add(img, combined_ink); img = cv2.add(img, text_canvas)

    # FINAL RESIZE FOR DISPLAY (Scale Up to 1280x720)
    img_display = cv2.resize(img, (DISP_W, DISP_H), interpolation=cv2.INTER_LINEAR)
    cv2.imshow("Smart Board", img_display)

cap.release()
cv2.destroyAllWindows()