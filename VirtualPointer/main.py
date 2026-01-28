import cv2
import mediapipe as mp
import numpy as np

# Initialize MediaPipe Hand Tracking
mp_hands = mp.solutions.hands
hands = mp_hands.Hands(min_detection_confidence=0.8, min_tracking_confidence=0.8)
mp_draw = mp.solutions.drawing_utils

# Initialize Webcam
cap = cv2.VideoCapture(0)
cap.set(3, 1280) # Width
cap.set(4, 720)  # Height

# Create a blank digital canvas
canvas = np.zeros((720, 1280, 3), np.uint8)

# Variables for drawing
prev_x, prev_y = 0, 0
draw_color = (0, 255, 0) # Green by default
thickness = 5

while True:
    success, frame = cap.read()
    if not success: break
    
    # Flip the frame so it acts like a mirror
    frame = cv2.flip(frame, 1)
    rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    result = hands.process(rgb_frame)
    
    if result.multi_hand_landmarks:
        for hand_lms in result.multi_hand_landmarks:
            # Get coordinates of Index Finger Tip (ID 8) and Middle Finger Tip (ID 12)
            landmarks = hand_lms.landmark
            h, w, c = frame.shape
            ix, iy = int(landmarks[8].x * w), int(landmarks[8].y * h)
            mx, my = int(landmarks[12].x * w), int(landmarks[12].y * h)

            # Check which fingers are up
            index_up = landmarks[8].y < landmarks[6].y
            middle_up = landmarks[12].y < landmarks[10].y

            # 1. Selection Mode (Two fingers up) - DON'T DRAW
            if index_up and middle_up:
                prev_x, prev_y = 0, 0 # Reset drawing path
                cv2.circle(frame, (ix, iy), 15, (255, 255, 255), cv2.FILLED)

            # 2. Drawing Mode (Only Index finger up)
            elif index_up:
                cv2.circle(frame, (ix, iy), 10, draw_color, cv2.FILLED)
                if prev_x == 0 and prev_y == 0:
                    prev_x, prev_y = ix, iy
                
                # Draw lines on the canvas
                cv2.line(canvas, (prev_x, prev_y), (ix, iy), draw_color, thickness)
                prev_x, prev_y = ix, iy

    # Merge the canvas with the live camera feed
    gray_canvas = cv2.cvtColor(canvas, cv2.COLOR_BGR2GRAY)
    _, inv_canvas = cv2.threshold(gray_canvas, 10, 255, cv2.THRESH_BINARY_INV)
    inv_canvas = cv2.cvtColor(inv_canvas, cv2.COLOR_GRAY2BGR)
    frame = cv2.bitwise_and(frame, inv_canvas)
    frame = cv2.bitwise_or(frame, canvas)

    cv2.imshow("Virtual Blackboard", frame)
    
    # Press 'c' to clear screen, 'q' to quit
    key = cv2.waitKey(1)
    if key == ord('q'): break
    if key == ord('c'): canvas = np.zeros((720, 1280, 3), np.uint8)

cap.release()
cv2.destroyAllWindows()