import cv2
from cvzone.HandTrackingModule import HandDetector
import cvzone
import socket

HOST = "192.168.1.20"
PORT = 10003

# Socket setup
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((HOST, PORT))
except ConnectionRefusedError:
    print("Error: Connection refused. Please check if the server is running.")
    exit()

# Initial joint positions
joint_positions = {
    "J1": 0.400,
    "J2": -101.980,
    "J3": 162.100,
    "J4": 0.560,
    "J5": 43.930,
    "J6": 1.730,
}

# Webcam
cap = cv2.VideoCapture(0)
cap.set(3, 1280)  # Set width of the webcam frame
cap.set(4, 720)  # Set height of the webcam frame

# Hand Detector
detector = HandDetector(detectionCon=0.8, maxHands=1)

# Calibration for distance conversion
pixels_per_cm = 37

def send_message_and_confirm(sock, message):
    try:
        print(f"Sending message: {message}")
        sock.sendall(message.encode())
        response = sock.recv(1024).decode()  # Assuming the server sends a response
        print(f"Received response: {response}")
        return response.strip() == "True"  # Assuming the server sends "True" on success
    except Exception as e:
        print(f"Error sending/receiving message: {e}")
        return False

# Initialize variables for finger tracking
initial_position_x = None
initial_position_y = None
fingers_count = None
joint_key = None

while True:
    success, img = cap.read()
    if not success:
        print("Error: Failed to capture image from webcam.")
        break
    img = cv2.flip(img, 1)  # Flip the image horizontally

    # Detect hands and fingers
    hands, img = detector.findHands(img, draw=True)

    # Display finger count
    if fingers_count is not None:
        cv2.putText(img, f'Fingers Count: {fingers_count}', (50, 150),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2, cv2.LINE_AA)

    if hands:
        hand = hands[0]
        lmList = hand["lmList"]  # List of landmarks

        # Calculate thumb and index finger distances
        index_finger_tip = lmList[8]
        thumb_tip = lmList[4]
        thumb_index_distance = ((thumb_tip[0] - index_finger_tip[0]) ** 2 + (
                    thumb_tip[1] - index_finger_tip[1]) ** 2) ** 0.5

        if thumb_index_distance < 20:  # Assuming distance of 20 pixels as close enough
            if initial_position_x is None:
                initial_position_x = lmList[8][0]  # Set the initial position for x movement
            if initial_position_y is None:
                initial_position_y = lmList[8][1]  # Set the initial position for y movement

            current_position_x = lmList[8][0]
            dx = current_position_x - initial_position_x  # Calculate the difference in x-coordinates
            distance_cm_x = dx / pixels_per_cm  # Convert pixels to centimeters for x movement

            current_position_y = lmList[8][1]
            dy = current_position_y - initial_position_y  # Calculate the difference in y-coordinates
            distance_cm_y = dy / pixels_per_cm  # Convert pixels to centimeters for y movement

            cvzone.putTextRect(img, f'Moved X: {distance_cm_x:.2f} cm', (50, 50))
            cvzone.putTextRect(img, f'Moved Y: {distance_cm_y:.2f} cm', (50, 100))

            joint_value = None

            # Determine finger count
            fingers = detector.fingersUp(hand)
            fingers_count = fingers.count(1)

            # Display finger count
            cv2.putText(img, f'Fingers Count: {fingers_count}', (50, 150),
                        cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)

            # Determine which joint to control based on finger count
            joint_keys = ["J1", "J2", "J3", "J4", "J5"]
            if 1 <= fingers_count <= 5:
                joint_key = joint_keys[fingers_count - 1]
                joint_value = joint_positions[joint_key]

                if fingers_count in [1, 4]:  # J1 and J4 are controlled by x-movement
                    movement = distance_cm_x
                elif fingers_count in [2, 5]:  # J2 and J5 are controlled by y-movement
                    movement = distance_cm_y
                elif fingers_count == 3:  # J3 is controlled by inverted y-movement
                    movement = -distance_cm_y

                # Perform joint manipulation
                if joint_value is not None:
                    # Determine if the movement is positive or negative
                    if movement > 0:
                        adjustment = 5 if int(movement) % 2 == 0 else 0
                    else:
                        adjustment = -5 if int(abs(movement)) % 2 == 0 else 0

                    joint_value += adjustment
                    joint_positions[joint_key] = joint_value

                    message = f"1,({joint_positions['J1']:.3f},{joint_positions['J2']:.3f},{joint_positions['J3']:.3f},{joint_positions['J4']:.3f},{joint_positions['J5']:.3f},{joint_positions['J6']:.3f})(3,0)"
                    send_message_and_confirm(sock, message)

    # Display manipulating joint information
    if joint_key is not None:
        cv2.putText(img, f'Manipulating Joint: {joint_key}', (50, 200),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2, cv2.LINE_AA)

    cv2.imshow("Image", img)
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

# Release resources
cap.release()
cv2.destroyAllWindows()
sock.close()
