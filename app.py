from flask import Flask, request, jsonify
from flask_cors import CORS
import base64, cv2, numpy as np, os
import bcrypt

from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from datetime import timedelta

from db import get_db
from face_service import load_known_faces, recognize_face
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity
app = Flask(__name__)

# ==========================
# CONFIG
# ==========================

CORS(
    app,
    resources={r"/*": {"origins": "http://localhost:8080"}},
    supports_credentials=True,
    allow_headers=["Content-Type", "Authorization"]
)

app.config["JWT_SECRET_KEY"] = "smart-attendance-secret-key"
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=4)

# 🔒 FORCE JWT TO USE HEADERS ONLY
app.config["JWT_TOKEN_LOCATION"] = ["headers"]
app.config["JWT_HEADER_NAME"] = "Authorization"
app.config["JWT_HEADER_TYPE"] = "Bearer"

# ❌ NO COOKIES
app.config["JWT_COOKIE_CSRF_PROTECT"] = False


jwt = JWTManager(app)

# ==========================
# JWT ERROR HANDLERS (IMPORTANT)
# ==========================
@jwt.unauthorized_loader
def missing_token(reason):
    return jsonify({"message": "Missing or invalid token"}), 401

@jwt.invalid_token_loader
def invalid_token(reason):
    return jsonify({"message": "Invalid token"}), 401

@jwt.expired_token_loader
def expired_token(jwt_header, jwt_payload):
    return jsonify({"message": "Token expired"}), 401


# Load face encodings on startup
load_known_faces()


@app.route("/", methods=["GET"])
def home():
    return jsonify({"status": "Smart Attendance Backend Running"})


# =====================================================
# STUDENT REGISTRATION
# =====================================================
@app.route("/student/register", methods=["POST"])
def register_student():
    try:
        data = request.get_json()

        roll_no = data.get("rollNo")
        name = data.get("name")
        student_class = data.get("class")
        department = data.get("department")
        images = data.get("images", [])

        if not roll_no or not images:
            return jsonify({"message": "Invalid data"}), 400

        conn = get_db()
        cur = conn.cursor()

        cur.execute("SELECT id FROM students WHERE roll_no=%s", (roll_no,))
        if cur.fetchone():
            return jsonify({"message": "Student already exists"}), 409

        cur.execute(
            "INSERT INTO students (roll_no, name, class, department) VALUES (%s,%s,%s,%s)",
            (roll_no, name, student_class, department)
        )

        student_dir = f"faces/{roll_no}"
        os.makedirs(student_dir, exist_ok=True)

        for i, img in enumerate(images):
            img_bytes = base64.b64decode(img.split(",")[1])
            path = f"{student_dir}/{i}.jpg"

            with open(path, "wb") as f:
                f.write(img_bytes)

            cur.execute(
                "INSERT INTO face_samples (roll_no, image_path) VALUES (%s,%s)",
                (roll_no, path)
            )

        conn.commit()
        cur.close()
        conn.close()

        load_known_faces()
        return jsonify({"message": "Student registered successfully"}), 201

    except Exception as e:
        print("❌ STUDENT REGISTER ERROR:", e)
        return jsonify({"message": "Registration failed"}), 500


# =====================================================
# STUDENT LOGIN (NO SECURITY)
# =====================================================
@app.route("/student/login", methods=["POST"])
def student_login():
    roll_no = request.json.get("rollNo")

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM students WHERE roll_no=%s", (roll_no,))
    student = cur.fetchone()

    cur.close()
    conn.close()

    if not student:
        return jsonify({"message": "Student not found"}), 404

    return jsonify(student), 200


# =====================================================
# TEACHER REGISTER
# =====================================================
@app.route("/teacher/register", methods=["POST"])
def register_teacher():
    data = request.get_json()

    name = data.get("name")
    email = data.get("email")
    password = data.get("password")
    department = data.get("department")

    if not name or not email or not password:
        return jsonify({"message": "Invalid data"}), 400

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"),
        bcrypt.gensalt()
    ).decode("utf-8")

    try:
        conn = get_db()
        cur = conn.cursor()

        cur.execute(
            "INSERT INTO teachers (name, email, password_hash, department) VALUES (%s,%s,%s,%s)",
            (name, email, password_hash, department)
        )

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Teacher registered successfully"}), 201

    except Exception as e:
        print("❌ TEACHER REGISTER ERROR:", e)
        return jsonify({"message": "Teacher already exists"}), 409

@app.route("/teacher/login", methods=["POST", "OPTIONS"])
def teacher_login():

    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    data = request.get_json()
    email = data.get("email")
    password = data.get("password")

    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT * FROM teachers WHERE email=%s", (email,))
    teacher = cur.fetchone()

    cur.close()
    conn.close()

    if not teacher:
        return jsonify({"message": "Invalid credentials"}), 401

    if not bcrypt.checkpw(
        password.encode("utf-8"),
        teacher["password_hash"].encode("utf-8")
    ):
        return jsonify({"message": "Invalid credentials"}), 401

    token = create_access_token(
        identity=str(teacher["id"]),     # 🔥 FIX IS HERE
        additional_claims={
            "role": "teacher",
            "email": teacher["email"]
        }
    )

    return jsonify({
        "token": token,
        "teacher": {
            "id": teacher["id"],
            "name": teacher["name"],
            "email": teacher["email"],
            "department": teacher["department"]
        }
    }), 200

#  =====================================================
# FACE RECOGNITION (TEACHER ONLY)
# =====================================================
from flask_jwt_extended import verify_jwt_in_request, get_jwt_identity, get_jwt

@app.route("/recognize", methods=["POST", "OPTIONS"])
def recognize():

    if request.method == "OPTIONS":
        return jsonify({"status": "ok"}), 200

    try:
        verify_jwt_in_request()
    except Exception as e:
        print("JWT ERROR:", e)
        return jsonify({"message": "Unauthorized"}), 401

    user_id = get_jwt_identity()   # STRING
    claims = get_jwt()             # EXTRA DATA

    if claims.get("role") != "teacher":
        return jsonify({"message": "Unauthorized"}), 403

    data = request.get_json()
    image = data.get("image")
    class_code = data.get("classCode", "").strip().upper()
    subject = data.get("subject", "").strip().upper()

    if not image or not class_code or not subject:
        return jsonify({"message": "Invalid data"}), 400

    img_bytes = base64.b64decode(image.split(",")[1])
    frame = cv2.imdecode(np.frombuffer(img_bytes, np.uint8), cv2.IMREAD_COLOR)

    roll_no, confidence = recognize_face(frame)

    if not roll_no:
        return jsonify({"message": "No face matched"}), 200

    conn = get_db()
    cur = conn.cursor()

    cur.execute("""
        SELECT id FROM attendance
        WHERE roll_no=%s AND class_code=%s AND subject=%s AND date=CURDATE()
    """, (roll_no, class_code, subject))

    if cur.fetchone():
        cur.close()
        conn.close()
        return jsonify({"duplicate": True}), 200

    cur.execute("""
        INSERT INTO attendance
        (roll_no, class_code, subject, date, time, confidence)
        VALUES (%s,%s,%s,CURDATE(),CURTIME(),%s)
    """, (roll_no, class_code, subject, confidence))

    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"rollNo": roll_no, "confidence": confidence}), 200

# =====================================================
# FETCH STUDENT ATTENDANCE (PUBLIC)
# =====================================================
@app.route("/student/attendance/<roll_no>", methods=["GET"])
def get_student_attendance(roll_no):
    conn = get_db()
    cur = conn.cursor(dictionary=True)

    cur.execute(
        """
        SELECT id, roll_no, class_code, subject, date, time, confidence
        FROM attendance
        WHERE roll_no=%s
        ORDER BY date DESC, time DESC
        """,
        (roll_no,)
    )

    rows = cur.fetchall()
    cur.close()
    conn.close()

    records = []
    for row in rows:
        records.append({
            "id": row["id"],
            "roll_no": row["roll_no"],
            "class_code": row["class_code"],
            "subject": row["subject"],
            "date": row["date"].isoformat(),
            "time": str(row["time"]),
            "confidence": row["confidence"]
        })

    return jsonify(records)


# =====================================================
# APP START
# =====================================================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
