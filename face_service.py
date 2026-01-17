import face_recognition
import cv2
import os
import numpy as np

KNOWN_ENCODINGS = []
KNOWN_ROLLNOS = []

FACES_DIR = "faces"


def load_known_faces():
    global KNOWN_ENCODINGS, KNOWN_ROLLNOS

    KNOWN_ENCODINGS = []
    KNOWN_ROLLNOS = []

    if not os.path.exists(FACES_DIR):
        return

    for roll_no in os.listdir(FACES_DIR):
        roll_path = os.path.join(FACES_DIR, roll_no)

        if not os.path.isdir(roll_path):
            continue

        for img_name in os.listdir(roll_path):
            img_path = os.path.join(roll_path, img_name)

            image = face_recognition.load_image_file(img_path)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                KNOWN_ENCODINGS.append(encodings[0])
                KNOWN_ROLLNOS.append(roll_no)

    print(f"✅ Loaded faces for {len(set(KNOWN_ROLLNOS))} students")


def recognize_face(frame):
    if frame is None or len(KNOWN_ENCODINGS) == 0:
        return None, None

    rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

    face_locations = face_recognition.face_locations(rgb)
    face_encodings = face_recognition.face_encodings(rgb, face_locations)

    if not face_encodings:
        return None, None

    for encoding in face_encodings:
        distances = face_recognition.face_distance(KNOWN_ENCODINGS, encoding)
        best_index = np.argmin(distances)
        best_distance = distances[best_index]

        if best_distance < 0.55:
            confidence = int((1 - best_distance) * 100)
            confidence = max(85, min(confidence, 99))
            return KNOWN_ROLLNOS[best_index], confidence

    return None, None
