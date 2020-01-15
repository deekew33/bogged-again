# this script will reset all the ticker information stowed away in results.db. USE AT OWN RISK!

import sqlite3
connection=sqlite3.connect('results.db')
cursor=connection.cursor()
tablenames = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
# the elements in the list are in the form of a tuple:
tablelist = []
for name in tablenames:
    if '20' not in name[0] and 'Daily' not in name[0] and 'Archives' not in name[0]:
        tablelist.append(name[0])
print(tablelist)
for name in tablelist:
    cursor.execute(f"DROP TABLE '{name}'")
connection.commit()
connection.close()

