import face_recognition
import os
import pickle

KNOWN_ENCODINGS = []
KNOWN_ROLLNOS = []

FACES_DIR = "faces"

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

with open("encodings.pkl", "wb") as f:
    pickle.dump((KNOWN_ENCODINGS, KNOWN_ROLLNOS), f)

print("✅ Face training completed")
