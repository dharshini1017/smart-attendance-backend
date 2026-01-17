import mysql.connector

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="imyours@1017",
        database="smart_attendance",
        autocommit=True   # 🔥 THIS FIXES LOCK ISSUES
    )
