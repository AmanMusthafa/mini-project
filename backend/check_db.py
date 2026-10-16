import sqlite3
conn = sqlite3.connect('database.db')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("SELECT COUNT(*) FROM road_accidents")
total = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM road_accidents WHERE accident_severity='fatal'")
fatal = c.fetchone()[0]
print('Stats OK - total:', total, 'fatal:', fatal)

c.execute("SELECT substr(date,7,4) yr, CAST(substr(date,4,2) AS INTEGER) mo, COUNT(*) cnt FROM road_accidents WHERE date!='' GROUP BY yr, mo ORDER BY yr, mo LIMIT 5")
rows = c.fetchall()
print('Trend sample:', [(r['yr'], r['mo'], r['cnt']) for r in rows])

c.execute("SELECT CAST(hour AS INTEGER) h, COUNT(*) cnt FROM road_accidents WHERE hour!='' GROUP BY h ORDER BY h")
rows = c.fetchall()
peak = sorted([(r['h'], r['cnt']) for r in rows], key=lambda x: -x[1])[:3]
print('Peak hours (top 3):', peak)

c.execute("SELECT cause, COUNT(*) cnt FROM road_accidents WHERE cause!='' GROUP BY cause ORDER BY cnt DESC")
rows = c.fetchall()
print('Causes:', [(r['cause'], r['cnt']) for r in rows])

c.execute("SELECT day_of_week, COUNT(*) cnt FROM road_accidents WHERE day_of_week!='' GROUP BY day_of_week ORDER BY cnt DESC")
rows = c.fetchall()
print('Weekdays:', [(r['day_of_week'], r['cnt']) for r in rows])

conn.close()
print('ALL QUERIES OK')
