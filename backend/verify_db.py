import sqlite3
import os

db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'database.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
c = conn.cursor()

# Sample casualties values
c.execute('SELECT casualties FROM road_accidents LIMIT 10')
print('Sample casualties:', [r[0] for r in c.fetchall()])

# Total SUM
c.execute('SELECT SUM(CAST(casualties AS INTEGER)) FROM road_accidents')
print('Total casualties SUM:', c.fetchone()[0])

# Non-zero
c.execute('SELECT COUNT(*) FROM road_accidents WHERE CAST(casualties AS INTEGER) > 0')
print('Rows casualties > 0:', c.fetchone()[0])

# Max value
c.execute('SELECT MAX(CAST(casualties AS INTEGER)) FROM road_accidents')
print('Max casualties in one accident:', c.fetchone()[0])

# All columns
c.execute('PRAGMA table_info(road_accidents)')
cols = [r['name'] for r in c.fetchall()]
print('Columns:', cols)

# Cause distribution
c.execute("SELECT cause, COUNT(*) as cnt FROM road_accidents WHERE cause != '' GROUP BY cause ORDER BY cnt DESC")
print('Causes:')
for r in c.fetchall():
    print(' ', r['cause'], ':', r['cnt'])

# Check if killed/injured columns exist
for col in ['killed', 'injured', 'persons_killed', 'persons_injured', 'fatalities']:
    if col in cols:
        c.execute(f'SELECT SUM(CAST({col} AS INTEGER)) FROM road_accidents')
        print(f'SUM of {col}:', c.fetchone()[0])

conn.close()
