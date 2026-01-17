import mysql.connector

def get_db():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="your_mysql_password",
        database="smart_attendance",
        autocommit=True   # 🔥 THIS FIXES LOCK ISSUES
    )
