# kind of a sandbox for easier database management since i don't like typing things out in terminal
import sqlite3, time
from polls.boggedagain import boggedagain

connection = sqlite3.connect("results.db")
cursor = connection.cursor()
sqlcommand = " CREATE TABLE 'Stockfacts' (ticker text, fullname text, " \
             "cap real, sector text, industry text, subindustry text, hq text)"
cursor.execute(sqlcommand)

tablenames = cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
tablelist = []
for name in tablenames:
    if '20' not in name[0] and 'Daily' not in name[0] and 'Archives' not in name[0] and 'Stock' not in name[0]:
        tablelist.append(name[0])
daily = 1
datelist = []
for ticker in tablelist:
    datelist.append(cursor.execute(f"SELECT date FROM '{ticker}'").fetchall())
connection.close()
for index, ticker in enumerate(tablelist):
    for date in set(datelist[index]):
        realtime = time.mktime(time.strptime(date[0],'%Y-%m-%d'))
        starttime = time.strftime("%Y%m%d", time.gmtime(realtime - 60 * 60 * 24 * 365 * 2))
        endtime = time.strftime("%Y%m%d", time.gmtime(realtime))
        requested = boggedagain.extract_quote(ticker, starttime)
        requested = requested[requested['Date'] <= date[0]]
        requested = boggedagain.newscrape(requested, ticker, daily)
        if not isinstance(requested, str):
            boggedagain.createstat(requested, ticker)
            print(f"Completed retroactive analysis of {ticker} on {endtime}")
