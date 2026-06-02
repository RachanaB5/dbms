import mysql.connector
import logging
from app import app, init_db as app_init_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def init_db():
    try:
        # Connect to MySQL server to ensure database is created/wiped
        conn = mysql.connector.connect(
            host="127.0.0.1",
            user="root",
            password="Rachana@05"
        )
        cursor = conn.cursor()
        cursor.execute("DROP DATABASE IF EXISTS EcommerceDB")
        cursor.execute("CREATE DATABASE EcommerceDB")
        cursor.close()
        conn.close()
        logger.info("Raw MySQL EcommerceDB database created successfully")
        
        # Now run Flask-SQLAlchemy schema creation and seeding
        app_init_db()
        logger.info("Database initialized and seeded via Flask-SQLAlchemy successfully!")
        return True
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
        return False

if __name__ == "__main__":
    init_db()
