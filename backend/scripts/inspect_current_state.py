import sqlite3

conn = sqlite3.connect('backend/database.db')
c = conn.cursor()
tables = [r[0] for r in c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
print('Tables:', tables)

for t in tables:
    cnt = c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
    cols = [(r[1], r[2]) for r in c.execute(f"PRAGMA table_info({t})").fetchall()]
    print(f"\nTable '{t}' ({cnt} rows):")
    print("Columns:", cols)

print("\nUsers table sample:")
for u in c.execute("SELECT * FROM users").fetchall():
    print(dict(zip([r[1] for r in c.execute("PRAGMA table_info(users)").fetchall()], u)))

print("\nSeverity breakdown:")
for r in c.execute("SELECT accident_severity, count(*), data_source FROM road_accidents GROUP BY accident_severity, data_source").fetchall():
    print(r)

print("\nDate range:")
print("Min date, Max date:", c.execute("SELECT min(date), max(date) FROM road_accidents").fetchall())
