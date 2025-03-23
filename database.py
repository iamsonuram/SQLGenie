import sqlite3

DB_PATH = "db/database.db"

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row  # Allows dictionary-like row access
    return conn
