import sqlite3

# Connect to SQLite database (creates it if it doesn't exist)
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# ==========================
# Create Users Table
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE,
    password TEXT,
    name TEXT,
    email TEXT,
    department TEXT,
    phone TEXT,
    role TEXT
)
""")

# Insert default admin
cursor.execute("""
INSERT OR IGNORE INTO users
(username, password, name, email, department, phone, role)
VALUES
(
    'admin',
    'admin123',
    'Aman',
    'admin@gmail.com',
    'Traffic Department',
    '9876543210',
    'Admin'
)
""")

# ==========================
# Create Road Accidents Table
# ==========================
cursor.execute("""
CREATE TABLE IF NOT EXISTS road_accidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT
)
""")

conn.commit()
conn.close()

print("✅ Database created successfully!")
print("✅ Admin Username: admin")
print("✅ Admin Password: admin123")