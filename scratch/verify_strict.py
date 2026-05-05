import sqlite3
conn = sqlite3.connect('data/taleweaver.db')
c = conn.cursor()
c.execute("SELECT id, title, strict_rules, rule_enforcement_mode FROM adventure_templates WHERE origin_id='THE_ARCHITECT'")
print(c.fetchall())
conn.close()
