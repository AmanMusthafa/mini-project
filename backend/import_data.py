import sqlite3
import pandas as pd

# Connect to database
conn = sqlite3.connect("database.db")
cursor = conn.cursor()

# Read CSV
df = pd.read_csv("data/indian_roads_dataset.csv")

print("Total rows:", len(df))

# Create table automatically from CSV columns
columns = df.columns.tolist()

column_definitions = ", ".join([f'"{col}" TEXT' for col in columns])

cursor.execute("DROP TABLE IF EXISTS road_accidents")

cursor.execute(f"""
CREATE TABLE road_accidents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    {column_definitions}
)
""")

# Insert data
placeholders = ",".join(["?"] * len(columns))
query = f'''
INSERT INTO road_accidents ({",".join([f'"{c}"' for c in columns])})
VALUES ({placeholders})
'''

cursor.executemany(query, df.fillna("").astype(str).values.tolist())

conn.commit()
conn.close()

print("✅ Data Imported Successfully!")
print("Rows Imported:", len(df))