import os
import mysql.connector

def get_db():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "mysql.railway.internal"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", "sFCPQOiIeDqxwIQyZYlUjQEbHHfCWcmZ"),
        database=os.environ.get("DB_NAME", "smart_attendance"),  # your DB name
        port=int(os.environ.get("DB_PORT", 3306)),
        autocommit=True  # prevents lock issues
    )
