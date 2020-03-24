import sys

sys.path.append("..")
sys.path.append('/stuff/venvs/python36/local/lib64/python3.6/dist-packages')
from shutil import copyfile
import os.path
import os, csv, pandas as pd, time, scrapy, bisect, logging, pickle, math, sqlite3

from scrapy.crawler import CrawlerRunner, CrawlerProcess
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings

pd.options.mode.chained_assignment = None
from crochet import setup, wait_for, run_in_reactor, retrieve_result, TimeoutError

if __name__ == "__main__":
    import classifier as cl
    import key_manager
    from yahoo_quote_download import yqd
else:
    from . import classifier as cl
    from . import key_manager
    from .yahoo_quote_download import yqd
standalone = 0
setup()
if not os.path.exists('/stuff/venvs/python36'):
    lpath = ''
else:  # we're on the linux server
    lpath = '/stuff/ebdjango/'
loaddata = 0  # token for reloading data pulled earlier
save = 1  # token for saving data pulled by YQD


from googleapiclient.discovery import build
# zacks search engine
my_api_key = key_manager.get_google_api_key()
my_cse_id = key_manager.get_google_cse_id()

def google_search(search_term, api_key=my_api_key, cse_id=my_cse_id, **kwargs):
    service = build("customsearch", "v1", developerKey=api_key,cache_discovery=False)
    res = service.cse().list(q=search_term, cx=cse_id, **kwargs).execute()
    return res

def truncate(value, percent=True):
    if percent == True:
        return math.ceil(value * 10000) / 100
    else:
        return math.ceil(value * 100) / 100


class ZacksSpider(scrapy.Spider):
    name = 'Zacks'

    def __init__(self, args, **kwargs):
        super().__init__(**kwargs)
        self.datelist = args['datelist']
        self.ticker = args['ticker']
        self.finalnews = ['No match'] * len(self.datelist)  # initialization of some variables
        self.urllist = ['No match'] * len(self.datelist)
        self.finalindex = 0

        self.index = -1
        self.newslist = 0
        self.newscounter = 0
        self.newstext = ['No match'] * len(self.datelist)

    def start_requests(self):
        urls = [f'https://www.zacks.com/stock/quote/{self.ticker}']  # we start by getting the full name
        self.log(urls)
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        fullname = response.xpath('//h1//a/text()').get()
        self.log(f'full name is {fullname}')
        for index, date in enumerate(self.datelist):
            searchterm = f'{date} "{self.ticker}" {fullname}'
            result = google_search(searchterm)
            if 'totalResults' in result['queries']['request'][0]:
                if int(result['queries']['request'][0]['totalResults']) > 0:
                    newscheck = 0
                    url = result['items'][0]['link']
                    if 'seekingalpha' in url:
                        try:
                            if result['items'][0]['pagemap']['webpage'][0]['datepublished'][:10] == date:
                                newscheck = 1
                                self.finalnews[index] = result['items'][0]['pagemap']['webpage'][0]['headline']
                        except:
                            newscheck = 1
                            self.finalnews[index] = result['items'][0]['title']
                    else:
                        newscheck = 1
                        self.finalnews[index] = result['items'][0]['title']

                    if newscheck == 1:
                        self.urllist[index] = url
                        self.newstext[index] = result['items'][0]['snippet']
                        # variable to help us keep track of whether this is the last valid url
                        self.finalindex = index
        self.save_news()
        return


    def save_news(self):
        filename = f'{lpath}stocks/Zacks/headlines-{self.ticker}.csv'
        self.log(f'Now saving {filename}')
        a = open(filename, 'w', newline='', encoding="utf-8")
        writer = csv.writer(a)
        writer.writerow(['Headline', 'URL'])  # adding a header for better pandas
        for z in range(0, len(self.finalnews)):
            writer.writerow([self.finalnews[z], self.urllist[z]])  # save the headline
        a.close()


def extract_quote(ticker, starttime, endtime=time.strftime("%Y%m%d", time.gmtime())):
    ticker = ticker.upper()
    # endtime = time.strftime("%Y%m%d", time.gmtime())  # end time is today in posix time
    loaddata = 0
    if loaddata == 1:
        requested = pd.read_csv(f'{lpath}{ticker}.csv')
    else:
        requested = yqd.load_yahoo_quote(ticker, starttime, endtime, info='quote', format_output='dataframe')
    if not isinstance(requested, str):
        requested = requested.replace('null', 'NaN')  # drop null values
        requested['Open'] = requested['Open'].astype(
            'float64')  # converting data types to floats and calculating percentages
        requested['Close'] = requested['Close'].astype('float64')
        #requested.to_csv(f'{lpath}{ticker}.csv')  # save extracted data to csv to avoid tangling with YQD
        requested['Percent'] = requested['Close']
        nanindex = min(requested.isna()[::-1].idxmax().values)
        if nanindex < len(requested) - 1:
            requested = requested[requested.index > nanindex].reset_index(drop=True)
        for x in range(1, len(requested)):
            requested['Percent'][x] = truncate(
                (requested['Close'][x] - requested['Close'][x - 1]) / requested['Close'][x - 1])
    return requested


def newscrape(requested, ticker, daily=0):
    # here begins the definition for the web scraper
    #logging.getLogger('scrapy').propagate = False  # turn off logging
    targetdrop = requested['Percent'][len(requested) - 1] * 0.9
    if targetdrop > 0:
        return 'Target percent was greater than 0- Bogged Again should only be used with dips.'
    # connect to sql database to reduce number of searches required
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{ticker}';")

    results = cursor.fetchall()
    sql_command = f"""
            CREATE TABLE '{ticker}' ( 
            date text,
            percent real,
            percent3 real,
            percent3o real,
            headline text,
            url text,
            source text,
            category text) """
    if len(results) == 0:
        cursor.execute(sql_command)
    datelist = []  # placeholder for dates of interest
    percentlist = []
    finalpercentlist = []
    finalopenpercent = []
    for x in range(0, len(requested) - 3):
        results = cursor.execute(f"SELECT * FROM '{ticker}' WHERE date = '{requested['Date'][x]}' "
                                 f"and source = 'CSE';").fetchall()
        if requested['Percent'][x] <= targetdrop and len(results) == 0:
            final = truncate((requested["Close"][x + 3] - requested["Close"][x]) / requested["Close"][x])
            final_open = truncate((requested["Open"][x + 3] - requested["Close"][x]) / requested["Close"][x])
            datelist.append(requested["Date"][x])  # saving items of interest to separate lists
            percentlist.append(requested["Percent"][x])
            finalpercentlist.append(final)
            finalopenpercent.append(final_open)

    results = cursor.execute(f"SELECT * FROM '{ticker}' WHERE date = '{requested['Date'][len(requested) - 1]}';").fetchall()
    if len(results)==0:  # if we looked up news today already then don't bother
        datelist.append(requested["Date"][len(requested) - 1])  # we add the items for today as well to the lists
        percentlist.append(requested['Percent'][len(requested) - 1])
        finalpercentlist.append(0)  # place holder because we don't know the future percentage change
        finalopenpercent.append(0)
    cursor.execute(f"UPDATE '{ticker}' SET 'percent'=? WHERE date = '{requested['Date'][len(requested) - 1]}';",
                   (requested['Percent'][len(requested) - 1],))
    datelist.reverse()  # reverse all the lists to be in reverse chronological order
    percentlist.reverse()
    finalpercentlist.reverse()
    finalopenpercent.reverse()
    datesecs = []
    for date in datelist:
        datesecs.append(time.mktime(time.strptime(date, "%Y-%m-%d")))  # convert all the dates into seconds
    if len(datesecs) > 100:
        return "There are at least 100 similar drops in the past, which probably means it's not a big enough drop. "
    categorylist = ['Unknown'] * len(datesecs)

    # launching the webspider here
    stuff = {'datelist': datelist, 'ticker': ticker}
    configure_logging({'LOG_FORMAT': '%(levelname)s: %(message)s'})
    runner = CrawlerRunner(get_project_settings())

    def run_spider(spidername, thing):
        # d = runner.crawl(spidername, thing)
        # return d
        # reactor.run()  # the script will block here until the crawling is finished
        # a = process.crawl(spidername, thing)  # the script will block here until the crawling is finished
        process = CrawlerProcess({
            'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
        })
        process.crawl(spidername, thing)  # the script will block here until the crawling is finished
        # process.stop()

    # create table that tracks how many searches we've made today- Google CSE allows up to 100 free searches a day
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='DailySearch';")
    results = cursor.fetchall()
    if len(results)==0:
        sql_command = f"""
                    CREATE TABLE 'DailySearch' ( 
                    date text,
                    searches real) """
        cursor.execute(sql_command)
    # check if we have an entry for today
    results = cursor.execute(f"SELECT searches FROM DailySearch WHERE date='{requested['Date'][len(requested) - 1]}'").fetchall()
    if len(results) == 0:
        params = (requested['Date'][len(requested) - 1],0)
        cursor.execute(f"INSERT INTO 'DailySearch' VALUES (?, ?)",params)
        results = [(0,)]
    if results[0][0] + len(datelist) < 350 and len(datelist) > 0 and daily == 0:
        run_spider(ZacksSpider, stuff)
        cursor.execute(f"UPDATE 'DailySearch' SET searches = {results[0][0] + len(datelist)} WHERE date = '{requested['Date'][len(requested) - 1]}';")
    elif (results[0][0] + len(datelist) > 350 and len(datelist) > 0) or daily == 1:
        #save directly to database since we don't have enough searches/or don't want to search news
        for x in range(0, len(datelist)):
            params = (datelist[x], percentlist[x], finalpercentlist[x], finalopenpercent[x],
                      'No match', 'No match', 'none', categorylist[x])
            search_result = cursor.execute(f"SELECT * FROM '{ticker}' WHERE date = '{datelist[x]}'").fetchall()
            if len(search_result) == 0:
                cursor.execute(f"INSERT INTO '{ticker}' VALUES (?, ?, ?, ?, ?, ?, ?, ?)", params)


    # since scrapy checks the news page by page, if the first and last date are far apart it may take some time for the
    # crawling to complete.
    timeout = 0
    while not os.path.exists(f'{lpath}stocks/Zacks/headlines-{ticker}.csv')\
            and results[0][0] + len(datelist) < 350 and timeout < 150 and len(datelist) > 0 and daily == 0:
        time.sleep(5)
        timeout += 5
    # if the spider ran successfully, it will have saved the headlines in a csv in the same directory
    if os.path.exists(f'{lpath}stocks/Zacks/headlines-{ticker}.csv') and len(datelist) > 0:
        headlines = pd.read_csv(f'{lpath}stocks/Zacks/headlines-{ticker}.csv', encoding='unicode_escape')
        os.remove(f'{lpath}stocks/Zacks/headlines-{ticker}.csv')  # deleting file once it's fulfilled its purpose
        newstext = []
        # make a dataframe out of all the stuff we care about, tack on the headlines to the side, and save it!
        finaloutput = pd.DataFrame({'Date': datelist, 'Percent': percentlist, '3 Day Percent': finalpercentlist,
                                    '3 Day Open Percent': finalopenpercent})
        finaloutput.assign(Headline=headlines.Headline)
        # finaloutput.assign(MatchPercent=headlines.MatchPercent)
        for x in range(0, len(headlines.Headline)):
            result = cursor.execute(f"SELECT * FROM '{ticker}' WHERE date = '{datelist[x]}' AND source = 'none'").fetchall()
            if len(result)==0:
                params = (datelist[x], percentlist[x], finalpercentlist[x],finalopenpercent[x],
                          headlines.Headline[x], headlines.URL[x], 'CSE', categorylist[x])
                #print(f"Params about to be inserted are {params}")
                cursor.execute(f"INSERT INTO '{ticker}' VALUES (?, ?, ?, ?, ?, ?, ?, ?)", params)
            else:
                params = (headlines.Headline[x], headlines.URL[x], categorylist[x], 'CSE',datelist[x])
                cursor.execute(f"UPDATE '{ticker}' SET 'headline'=? AND 'url'=? AND 'category' = ? AND 'source' = ? WHERE 'date'=?", params)

    # now that everything should be inserted into the sql database, we pull it out from the database
    # and turn it into a dataframe
    result = cursor.execute(f"SELECT * FROM '{ticker}' WHERE date > {requested['Date'][0]} "
                            f" AND percent < {targetdrop} ORDER BY date DESC").fetchall()
    finalresult = pd.DataFrame(result,
                               columns=['Date', 'Percent', '3 Day Percent', '3 Day Open Percent', 'Headline', 'URL',
                                         'Source', 'Category'])
    finalresult = finalresult.drop('Source', axis=1)
    connection.commit()
    connection.close()
    return finalresult


#  method to save a daily value into a sqlite database
def createstat(requested, ticker):
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    sql_command = """
        CREATE TABLE 'Daily Stats' ( 
        time text,
        ticker text,
        percent real, 
        'sample size' real, 
        '3 day median' real,
        '3 day mean' real,
        'pos percent' real,
        'Same cat sample size' real,
        'Same cat mean' real,
        'Same cat median' real,
        rank real);"""
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='Daily Stats';")
    results = cursor.fetchall()
    if results == []:
        cursor.execute(sql_command)  # generate the table if it doesn't exist
    today = requested['Date'][0]
    if len(requested) >= 2:  # only do calculations if there's more than one row
        try:
            med = truncate(requested[requested['Date'] != today]['3 Day Percent'].median(), False)
            mean = truncate(requested[requested['Date'] != today]['3 Day Percent'].mean(), False)
            samplesize = len(requested) - 1
        except:
            med = 0
            mean = 0
            samplesize = 1
        try:
            med_cat = requested[(requested['Date'] != today) & (requested['Category'] ==
                                                                requested['Category'][0])]['3 Day Percent'].median()
            mean_cat = requested[(requested['Date'] != today) & (requested['Category'] ==
                                                                 requested['Category'][0])]['3 Day Percent'].mean()
            sample_cat = len(requested[(requested['Date'] != today) &
                                       (requested['Category'] == requested['Category'][0])])
            med_cat = truncate(med_cat, False)
            mean_cat = truncate(mean_cat, False)
        except:
            med_cat = 0
            mean_cat = 0
            sample_cat = 0
    else:  # there's only one row in the dataframe, stat functions will break
        med = 0
        mean = 0
        samplesize = 1
        med_cat = 0
        mean_cat = 0
        sample_cat = 0
    pospercent = truncate(len(requested[requested['3 Day Percent'] > 0]) / samplesize)
    rank = math.ceil(samplesize * med * 100 * pospercent) / 100

    searchparams = (today, ticker)
    cursor.execute("SELECT * FROM 'Daily Stats' WHERE time=? AND ticker=?", searchparams)
    result = cursor.fetchall()

    if len(result) == 0:
        print(f"Inserting data into daily stats..")
        params = (
        today, ticker, requested['Percent'][0], samplesize, med, mean, pospercent, sample_cat, med_cat, mean_cat, rank)
        cursor.execute("INSERT INTO 'Daily Stats' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", params)
    else:
        params = (requested['Percent'][0], rank, today, ticker)
        cursor.execute("UPDATE 'Daily Stats' SET 'percent'=?, 'rank' = ? WHERE time=? AND ticker=?", params)

    cursor.execute("SELECT * FROM 'Daily Stats'")
    connection.commit()
    connection.close()
    stuff = {'N': samplesize, 'Median': med, 'Mean': mean, 'Positive Percent': pospercent,
             'N Same Category': sample_cat, 'Same Category Median': med_cat, 'Same Category Mean': mean_cat}
    thing = pd.DataFrame(data=stuff, index=[0])
    return thing


def dailystats(date):
    daily = 0
    if os.path.exists(f'{lpath}media/files/screener_results.csv'):
        data = pd.read_csv(f'{lpath}media/files/screener_results.csv')
        nanindex = min(data.isna().idxmax().values)
        data = data[data.index < nanindex]
        tickerlist = data['Symbol']
        starttime = time.strftime("%Y%m%d", time.gmtime(time.time() - 60 * 60 * 24 * 365 * 2))
        daily = 1
        for ticker in tickerlist:
            print(f'Trying {ticker}')
            requested = extract_quote(ticker, starttime)
            requested = newscrape(requested, ticker, daily)
            if not isinstance(requested, str):
                createstat(requested, ticker)
        os.remove(f'{lpath}media/files/screener_results.csv')
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    if daily ==1 :
        for ticker in tickerlist:
            results = cursor.execute(f"SELECT * FROM 'Stockfacts' WHERE ticker = '{ticker}'").fetchall()
            capstring = data['Market Capitalization'][data['Symbol']==ticker].values[0]
            if capstring[-1] == 'B':
                cap = truncate(float(capstring[1:-1])*1000, False)
            else:
                cap = truncate(float(capstring[1:-1]), False)
            params = (ticker,
                      data['Company Name'][data['Symbol'] == ticker].values[0],
                      cap,
                      data['Sector'][data['Symbol'] == ticker].values[0],
                      data['Industry'][data['Symbol'] == ticker].values[0],
                      data['Sub-Industry'][data['Symbol'] == ticker].values[0],
                      data['Company Headquarters Location'][data['Symbol'] == ticker].values[0])
            # print(f"Adding stock facts for {ticker} with parameters of {params}")
            if len(results) != 0:
                cursor.execute(f"DELETE FROM 'Stockfacts' WHERE ticker='{ticker}'")
            cursor.execute("INSERT INTO 'Stockfacts' VALUES (?, ?, ?, ?, ?, ?, ?)", params)
    searchparams = [date]

    sql_command = "SELECT DS.time, DS.ticker, DS.percent, DS.'sample size', DS.'3 day median', DS.'3 day mean'," \
                  "DS.'pos percent', SF.cap, SF.sector, SF.industry, DS.rank " \
                  "FROM 'Daily Stats' AS DS LEFT JOIN Stockfacts as SF " \
                  "ON DS.ticker = SF.ticker WHERE DS.time =? ORDER BY rank DESC"
    cursor.execute(sql_command, searchparams)
    result = cursor.fetchall()
    connection.commit()
    connection.close()
    if len(result) == 0:
        return "There are either no stocks looked at today yet or today's not a business day."
    else:
        finalresult = pd.DataFrame(result,
                                   columns=['Date', 'Ticker', 'Percent', 'N', 'Median', 'Mean', 'Positive Percent',
                                            'Market Cap(M)', 'Sector', 'Industry', 'Rank'])
        return finalresult


def archiveretrieval(date):
    # first check if we already have a table in the database
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;", [date])
    results = cursor.fetchall()
    starttime = date.replace('-', '')  # format string for the yahoo quote extractor

    def create_table(datetime):
        tablename = f"'{datetime}'"  # SQL naming conventions
        sql_command = f"""CREATE TABLE {tablename} AS
            SELECT *
            FROM 'Daily Stats'
            WHERE time = ? AND rank > 0; """
        cursor.execute(sql_command, [(datetime)])
        sql_command = f"""ALTER TABLE {tablename}  ADD 'FinalPercent' real default -999;"""
        cursor.execute(sql_command)

    # extract previous tickers that were looked at
    data = dailystats(date)
    if not isinstance(data, str):  # if we do have data for that day(aka not an error message)
        testdata = extract_quote(data['Ticker'][0], starttime)
        tablename = f"'{date}'"
        if len(results) == 0:  # first check if table exists, if not make it
            create_table(date)
        if len(testdata) < 5:  # not enough time has elapsed yet, so just replace the table unless we just made it
            if len(results) != 0:
                cursor.execute(f"DROP TABLE {tablename}")
                create_table(date)
        else:  # we have enough data to set the final percentage, loop through all the tickers if it's not already set
            cursor.execute(f"SELECT * FROM {tablename} WHERE FinalPercent=-999.0")
            results = cursor.fetchall()
            if len(results) != 0:  # if it's an empty set, then we have already calculated the final percent.
                for ticker in cursor.execute(f"SELECT Ticker FROM {tablename}").fetchall():
                    # for ticker in data['Ticker']:
                    testdata = extract_quote(ticker[0], starttime)
                    if len(testdata) < 5: # rare occasion when the company gets acquired, we use the last data point.
                        finalpercent = truncate((testdata["Close"][len(testdata)-1]-testdata["Close"][0])/testdata["Close"][0])
                    else:
                        finalpercent = truncate((testdata["Close"][3] - testdata["Close"][0]) / testdata["Close"][0])
                    sql_command = f"""UPDATE {tablename}
                            SET FinalPercent = ? 
                            WHERE ticker = ?;"""
                    params = [finalpercent, ticker[0]]
                    cursor.execute(sql_command, params)
        # we should have a table of some kind at this point.
        sql_command = f"SELECT * FROM {tablename} ORDER BY rank DESC"
        cursor.execute(sql_command)
        results = cursor.fetchall()
        connection.commit()
        connection.close()
        finalresult = pd.DataFrame(results, columns=['Date', 'Ticker', 'Percent', 'N', 'Median', 'Mean',
                                                     'Positive Percentage', 'N_cat',
                                                     'Same Cat Median', 'Same Cat Mean', 'Rank', 'Final Percent'])
        if len(finalresult) == 0:
            return "It looks like either everyone forgot to look up stocks that day, or all the stocks that dipped were" \
                   " too bad to make it into the archives."
        else:
            return finalresult
    else:
        return "We don't have daily stats for this day yet, much less an archive."


def rangeretrieval():
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    cursor.execute("SELECT MIN(time), MAX(time) FROM 'Daily Stats'")
    results = cursor.fetchall()
    return results


# for standalone usage
if __name__ == "__main__":
    ticker = 'ACMR'
    starttime = time.strftime("%Y%m%d", time.gmtime(time.time() - 60 * 60 * 24 * 365 * 2))
    abc = extract_quote(ticker, starttime)
    if not isinstance(abc, str):
        finalvento = newscrape(abc, ticker)
        finalvento.to_csv(f'stocks/{ticker}_final.csv')
        cdf = createstat(finalvento, ticker)
        print(cdf)
