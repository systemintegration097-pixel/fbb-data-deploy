import re
import sqlite3

conn = sqlite3.connect("gnoc.db")
cursor = conn.cursor()
cursor.execute("SELECT description FROM work_orders LIMIT 100")
descriptions = [r[0] for r in cursor.fetchall()]
conn.close()

regex = r'\b(\d{2}_gftth_[a-zA-Z0-9_]+)\b'
matched = 0
for idx, d in enumerate(descriptions):
    m = re.search(regex, d, re.IGNORECASE)
    if m:
        matched += 1
        print(f"[{idx}]: Extracted: {m.group(1)} from description: {d[:80]}...")
print(f"\nTotal matched in sample of 100: {matched}")
