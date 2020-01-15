import sys
sys.path.append("..")
sys.path.append('/stuff/venvs/python36/local/lib64/python3.6/dist-packages')
from shutil import copyfile
import os.path
import os, csv, pandas as pd, time, scrapy, bisect, logging, pickle, math, sqlite3
from scrapy.crawler import CrawlerRunner, CrawlerProcess
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor
from . import classifier as cl
pd.options.mode.chained_assignment = None
from crochet import setup, wait_for, run_in_reactor, retrieve_result, TimeoutError
standalone = 0
setup()
if not os.path.exists('/stuff/venvs/python36'):
    from .yahoo_quote_download import yqd
    lpath = ''
else: #we're on the linux server
    from .yahoo_quote_download import yqd
    lpath = '/stuff/ebdjango/'
loaddata = 0 # token for reloading data pulled earlier
save = 1 # token for saving data pulled by YQD


def truncate(value, percent=True):
    if percent == True:
        return math.ceil(value*10000)/100
    else:
        return math.ceil(value*100)/100


class QuotesSpider(scrapy.Spider):
    name = 'Quote'
    def __init__(self, args, **kwargs):
        super().__init__(**kwargs)
        self.datesecs = args['datesecs']
        self.ticker = args['ticker']
        self.finalnews = ['No match'] * len(self.datesecs)  # initialization of some variables
        self.relevancy = [0] * len(self.datesecs)
        # self.matchpercent = [0] * len(self.datesecs)
        self.urllist = ['No match'] * len(self.datesecs)
        self.pagenum = 0
        self.index = 0
        self.newstext = ['No match'] * len(self.datesecs)
        self.start_urls = [f'https://www.thestreet.com/quote/{self.ticker}/details/news?page=0']

    def start_requests(self):
        urls = [f'https://www.thestreet.com/quote/{self.ticker}/details/news?page=0']  # we start from page 0 on thestreet
        # self.log(urls)
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):
        fullname = response.xpath('//h1[@class="quote__header__company-name"]/text()').get()
        try:
            smolname = fullname[0:fullname.index(' ')]  # pick first string in the full name as the string to check
        except:
            smolname = fullname  # if you can't find a space in the company name, chances are it's just one word
        rdatesecs = []
        rdatelist = response.xpath('//@datetime').getall()  # extracts all date attributes embedded in the xml
        urllist = response.xpath('//div[@class="news-list-compact__body columnRight-"]//@href').getall()
        del rdatelist[0]  # the first date attribute is always the date you retrieved the page, so we delete it

        for stuff in rdatelist:
            rdatesecs.append(
                time.mktime(time.strptime(stuff, "%Y-%m-%dT%H:%MZ")))  # conversion of news date into seconds
        # finding which day is covered by the headlines on the page we're looking at,
        # and then ignoring all the dates in the future since the page is in reverse chronological order
        datesecs = self.datesecs
        #matchidx = bisect.bisect_right(datesecs[::-1], rdatesecs[0])
        # self.log(rdatesecs[0])
        if len(rdatesecs) >= 1: #if we run out of pages to look at (we get blank pages with no dates)
            if len(datesecs) > 1:
                matchidx = len(datesecs) - bisect.bisect_right(datesecs[::-1], rdatesecs[0] + 60 * 60 * 8) #can't remember why i subtracted from the length
            else:
                matchidx = bisect.bisect_right(datesecs[::-1], rdatesecs[0])-1
        else:  # exit by setting the matchindex so the datesecs iterator below becomes empty
            matchidx = len(datesecs)

        # more debugging
        match = 0
        timeover = 0  # initialization of certain checks
        if not datesecs[matchidx::]:  # if none of the days are covered by the headlines, we are done scraping headlines
            timeover = 1
        for day in datesecs[matchidx::]:
            # self.log(f'Currently looking at {time.strftime("%Y-%m-%d",time.localtime(day))}')
            match = 0
            timeover = 0  # resetting checks at the beginning of the loop
            for z in range(0, len(rdatesecs)):
                # pulling the headlines from the page
                headlines = response.xpath('//h3[contains(@class,"news-list-compact__headline news-list-compact__'
                                           'headline-")]/text()').getall()
                # a crude ranking system:
                # doesn't have qr in url: 16 points(because that requires subscribing to even read)
                # has company name/ticker in the headline: 8 points
                # has "investing" or "story"(older headlines) in the url: 4 points
                # doesn't have "realmoney" in the url: 2 points
                # doesn't have special characters in the headline: 1 point
                # slight edge to news that comes out after 16:30, since investors need time to react to conference calls
                ranking = (headlines[z].lower().find(smolname.lower()) != -1 or headlines[z].find(self.ticker) != -1) * 8 + \
                          (urllist[z].find('investing') != -1 or urllist[z].find('story') != -1) * 4 + \
                          (urllist[z].find('realmoney') == -1 and urllist[z].find('opinion') == -1) * 2 + \
                          (headlines[z].find('?') == -1 and headlines[z].find(';') == -1) * 1 + \
                          (day - 60 * 60 * 7.5 <= rdatesecs[z] ) * 1
                # simple check for the date: the drop most likely occurred during extended trading of the previous
                # day and part of today. so the range we're looking at is from 4 PM the day before til 5 PM today.
                if day - 60 * 60 * 8 <= rdatesecs[z] < day + 60 * 60 * 16 and urllist[z].find('/k/') == -1 :
                    match = 1
                    #self.log(
                    #    f'{headlines[z]} found for {time.strftime("%Y-%m-%d", time.localtime(day))} by {rdatelist[z]}, '
                    #    f'ranking of {ranking}!')
                    # list shenanigans since I don't know how big the list is when initializing the webscraper
                    if len(self.finalnews) == datesecs.index(day):
                        self.finalnews.append(headlines[z])  # append the headline if there is no headline yet
                    elif self.relevancy[datesecs.index(day)] <= ranking:
                        self.finalnews[datesecs.index(day)] = headlines[z]  # replace with an older headline
                        self.relevancy[datesecs.index(day)] = ranking
                        self.urllist[datesecs.index(day)] = urllist[z]
                # if the headline is earlier than 4PM yesterday, and we haven't had a match yet, we give on looking
                elif rdatesecs[z] < day - 60 * 60 * 8 and match == 0 and timeover == 0:
                    #self.log(f'Time out, no headlines found for {time.strftime("%Y-%m-%d",time.localtime(day))} '
                    #         f'by {rdatelist[z]}!')
                    timeover = 1
                    if len(self.finalnews) == datesecs.index(day):
                        self.finalnews.append('No match')
                    else:
                        self.log(datesecs.index(day))
                        self.finalnews[datesecs.index(day)] = 'No match'
                elif rdatesecs[z] < day - 60 * 60 * 8 and match == 1 and timeover == 0:
                    #self.log("Looks like we're done looking")
                    timeover = 1
        # if we haven't reached a point where the headlines occur before our lower date bound, we check
        # the next page of news and call the parse method on that page again
        if timeover == 0:
            self.pagenum += 1
            next_page = f'https://www.thestreet.com/quote/{self.ticker}/details/news?page={self.pagenum}'
            #self.log(next_page)
            return response.follow(next_page, callback=self.parse)
        # assuming we reached this point we're probably done scraping for all the dates, so save the headlines in a csv
        # but first, let us delve deeper into the actual articles
        if timeover == 1 or match == 1:
            #self.log(self.urllist)
            while self.urllist[self.index] == 'No match' and self.index < len(self.urllist)-1:
                self.index += 1
            if self.urllist[self.index] != 'No match':
                if self.urllist[self.index].find('http') == -1:
                    self.urllist[self.index] = f'https://www.thestreet.com{self.urllist[self.index]}'
                    self.log(self.urllist[self.index])
                return response.follow(self.urllist[self.index], callback=self.newsparse)
            else:
                self.save_news()
                return

    def newsparse(self, response):
        newstext = ' '.join(response.xpath('//p/text()').getall()[1:-8])
        self.log('parsing...')
        self.newstext[self.index] = newstext
        while self.index < len(self.urllist) - 1:
            self.index += 1
            while self.urllist[self.index] == 'No match' and self.index < len(self.urllist) - 1:
                self.index += 1
            if self.urllist[self.index] != 'No match':  # we've hit a new headline
                if self.urllist[self.index].find('http') == -1:
                    self.urllist[self.index] = f'https://www.thestreet.com{self.urllist[self.index]}'
                return response.follow(self.urllist[self.index], callback=self.newsparse)
        for z in range(0, len(self.datesecs)):
            if self.newstext[z] != 'No match':
                filename = f'{lpath}news/{self.ticker}-{time.strftime("%Y-%m-%d", time.gmtime(self.datesecs[z]))}.txt'
                with open(filename, "w", encoding="utf-8") as text_file:
                    print(self.newstext[z], file = text_file)
                #self.matchpercent[z] = len(set(self.newstext[z]).intersection(self.newstext[0])) / len(
                 #   self.newstext[0])
                # self.log(self.matchpercent[self.newstext.index(text)])
        self.log('parsing complete!')
        self.save_news()

    def save_news(self):
        filename = f'{lpath}stocks/headlines-{self.ticker}.csv'
        self.log(f'Now saving {filename}')
        a = open(filename, 'w', newline='',encoding="utf-8")
        writer = csv.writer(a)
        writer.writerow(['Headline', 'URL'])  # adding a header for better pandas
        for z in range(0, len(self.finalnews)):
            writer.writerow([self.finalnews[z], self.urllist[z]])  # save the headline
        a.close()
        # self.log('Saved file %s' % filename)

    # fudge factor so that we aren't too strict at looking at news


def extract_quote(ticker, starttime):
    ticker = ticker.upper()
    endtime = time.strftime("%Y%m%d",time.gmtime()) # end time is today in posix time
    # starttime = time.strftime("%Y%m%d",time.gmtime(time.time()-60*60*24*365*2))  # arbitrary 2 year period?
    requested = []
    loaddata = 0
    if loaddata == 1:
        requested = pd.read_csv(f'{lpath}{ticker}.csv')
    else:
        requested = yqd.load_yahoo_quote(ticker, starttime, endtime, info='quote', format_output='dataframe')
        time.sleep(5)
    if not isinstance(requested, str):
        requested = requested.replace('null', 'NaN').dropna() # drop null values
        requested = requested.dropna()
        requested['Open'] = requested['Open'].astype(
            'float64')  # converting data types to floats and calculating percentages
        requested['Close'] = requested['Close'].astype('float64')
        #if save == 1:
        #    requested.to_csv(f'{lpath}stocks/{ticker}.csv')  # save extracted data to csv to avoid tangling with YQD
        requested['Percent'] = requested['Close']
        for x in range(1, len(requested)):
            requested['Percent'][x] = truncate((requested['Close'][x] - requested['Close'][x - 1]) / requested['Close'][x - 1])
    return requested


def newscrape(requested, ticker):
    # here begins the definition for the web scraper
    logging.getLogger('scrapy').propagate = False # turn off logging
    targetdrop = requested['Percent'][len(requested)-1] * 0.9
    #targetdrop = -5
    if targetdrop > 0:
        return 'Target percent was greater than 0- Bogged Again should only be used with dips.'

    #print(f'Target percent is {targetdrop}... gathering data')
    datelist = []  # placeholder for dates of interest
    percentlist=[]
    finalpercentlist=[]
    finalopenpercent=[]
    for x in range(0, len(requested)-3):
        if requested['Percent'][x] <= targetdrop:
            final = truncate((requested["Close"][x+3]-requested["Close"][x])/requested["Close"][x])
            final_open = truncate((requested["Open"][x+3] - requested["Close"][x]) / requested["Close"][x])
            datelist.append(requested["Date"][x]) # saving items of interest to separate lists
            percentlist.append(requested["Percent"][x])
            finalpercentlist.append(final)
            finalopenpercent.append(final_open)
            #print(f'{ticker} suffered a {requested["Percent"][x]} percent drop on \
            #    {requested["Date"][x]}, 3 days later it went to {requested["Close"][x+3]} for a {final} percent change')
    datelist.append(requested["Date"][len(requested)-1])  # we add the items for today as well to the lists
    percentlist.append(requested['Percent'][len(requested)-1])
    finalpercentlist.append(0)  # place holder because we don't know the future percentage change
    finalopenpercent.append(0)
    datelist.reverse()  # reverse all the lists to be in reverse chronological order
    percentlist.reverse()
    finalpercentlist.reverse()
    finalopenpercent.reverse()
    datesecs = []
    for date in datelist:
        datesecs.append(time.mktime(time.strptime(date,"%Y-%m-%d")))  # convert all the dates into seconds
    if len(datesecs) > 100:
        return "There are at least 100 similar drops in the past, which probably means it's not a big enough drop. "
    categorylist = ['Unknown'] * len(datesecs)
    finaloutput = pd.DataFrame({'Date': datelist, 'Percent': percentlist, '3 Day Percent': finalpercentlist,'3 Day Open Percent': finalopenpercent})
    # launching the webspider here
    stuff = {'datesecs':datesecs, 'ticker':ticker}
    configure_logging({'LOG_FORMAT': '%(levelname)s: %(message)s'})
    runner = CrawlerRunner(get_project_settings())
    crawltime = abs(datesecs[0]-datesecs[-1])/60*60*24  # how many days are in between the first and the last
    def run_spider(spidername, thing):
        #d = runner.crawl(spidername, thing)
        #return d
        #reactor.run()  # the script will block here until the crawling is finished
        #a = process.crawl(spidername, thing)  # the script will block here until the crawling is finished
        process = CrawlerProcess({
            'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
        })
        process.crawl(spidername,thing)  # the script will block here until the crawling is finished
        #process.stop()


    #run_spider(QuotesSpider, stuff)
    # while the spider is still broken:
    filename = f'{lpath}stocks/headlines-{ticker}.csv'
    a = open(filename, 'w', newline='', encoding="utf-8")
    writer = csv.writer(a)
    writer.writerow(['Headline', 'URL'])  # adding a header for better pandas
    a.close()


    # since scrapy checks the news page by page, if the first and last date are far apart it may take some time for the
    # crawling to complete.
    timeout = 0
    while not os.path.exists(f'{lpath}stocks/headlines-{ticker}.csv') and timeout < 1500:
        time.sleep(5)  # assume it takes 1 second per page, 20 days of news on one page
        timeout += 5
    # if the spider ran successfully, it will have saved the headlines in a csv in the same directory
    if os.path.exists(f'{lpath}stocks/headlines-{ticker}.csv'):
        headlines=pd.read_csv(f'{lpath}stocks/headlines-{ticker}.csv', encoding = 'unicode_escape')
        os.remove(f'{lpath}stocks/headlines-{ticker}.csv')  # deleting file once it's fulfilled its purpose
        newstext=[]
        # make a dataframe out of all the stuff we care about, tack on the headlines to the side, and save it!
        finaloutput.assign(Headline=headlines.Headline)
        #finaloutput.assign(MatchPercent=headlines.MatchPercent)

        # unpickle pre-generated classifier to classify news
        f = open(f'{lpath}polls/boggedagain/my_classifier.pickle', 'rb')
        classifier = pickle.load(f)
        f.close()
        categorydecoder = {'AD':'Analyst downgrade','B':'Bankruptcy','CS':'Company scandal','LC':'Leadership change',
                           'LG':'Lowered guidance','LL':'Lost lawsuit','LS':'Leadership scandal','M':'Merger',
                           'NO':'New options', 'PO':'Public offering',
                           'R':'Regulation','RL':'Restructuring/Layoff','RM':'Revenue miss','SD':'Sector dump',
                           'SS':'Stock split','T':'Trump','TW':'Trade war'}
        for x in range(0, len(headlines.Headline)):
            if headlines.Headline[x] != 'No match':
                filename = f'{ticker}-{time.strftime("%Y-%m-%d", time.gmtime(datesecs[x]))}'
                with open(f'{lpath}news/{filename}.txt',encoding="utf-8") as f:
                    data = f.read()
                    f.close()
                    category = classifier.classify(cl.news_features(data))
                    categorylist[x] = categorydecoder[category]
                    # if this is not part of the training set yet, copy over as unlabeled so I can label it later.
                    if not os.path.exists(f'{lpath}trainer/{category}/{filename}_labeled.txt'):
                        copyfile(f'{lpath}news/{filename}.txt',f'{lpath}trainer/{filename}.txt')
                        os.remove(f'{lpath}news/{filename}.txt')
        finaloutput.assign(Category=categorylist)
        finalfinal=finaloutput.join(headlines)
        finalfinal['Category'] = pd.Series(categorylist, index=finalfinal.index)
        return finalfinal
    else:
        return "QuoteSpider did not finish after 150 seconds. Either there are too many news per page for the crawler" \
               "to parse through, or something went wrong with the spider and it hung. Please try again!"
    # print(__name__)
    #if __name__ == '__main__':
    #    p = Process(target=run_spider, args=(requested,ticker))
    #    p.start()
    #    p.join()
    # run_spider(requested,ticker)


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
    if results ==[]:
        cursor.execute(sql_command) # generate the table if it doesn't exist
    today = requested['Date'][0]
    if len(requested) >= 2: # only do calculations if there's more than one row
        med = truncate(requested[requested['Date'] != today]['3 Day Percent'].median(), False)
        mean = truncate(requested[requested['Date'] != today]['3 Day Percent'].mean(),False)
        samplesize = len(requested) - 1
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
    else: # there's only one row in the dataframe, stat functions will break
        med = 0
        mean = 0
        samplesize = 1
        med_cat = 0
        mean_cat =0
        sample_cat =0
    pospercent = truncate(len(requested[requested['3 Day Percent'] > 0]) / samplesize)
    #rank = math.ceil((1 - 1/samplesize)*(med + mean)*100*pospercent)/100 # updated 11/26
    rank = math.ceil(samplesize * med * 100 * pospercent) / 100

    searchparams = (today, ticker)
    cursor.execute("SELECT * FROM 'Daily Stats' WHERE time=? AND ticker=?",searchparams)
    result = cursor.fetchall()

    #for r in result:
    #    print(r)
    if len(result) == 0:
        params = (today, ticker, requested['Percent'][0], samplesize, med, mean, pospercent, sample_cat, med_cat, mean_cat, rank)
        cursor.execute("INSERT INTO 'Daily Stats' VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",  params)
    else:
        params = (requested['Percent'][0], today, ticker)
        cursor.execute("UPDATE 'Daily Stats' SET 'percent'=? WHERE time=? AND ticker=?", params)

    cursor.execute("SELECT * FROM 'Daily Stats'")
    connection.commit()
    connection.close()
    stuff = {'N':samplesize,'Median':med,'Mean':mean,'Positive Percent':pospercent,
             'N Same Category':sample_cat,'Same Category Median':med_cat, 'Same Category Mean':mean_cat}
    thing = pd.DataFrame(data=stuff, index=[0])
    return thing


def dailystats(date):
    if os.path.exists(f'{lpath}media/files/screener_results.csv'):
        tickerlist= pd.read_csv(f'{lpath}media/files/screener_results.csv')['Symbol']
        starttime = time.strftime("%Y%m%d", time.gmtime(time.time() - 60 * 60 * 24 * 365 * 2))
        for ticker in tickerlist:
            try:
            #    print(f'Trying {ticker}')
                requested=extract_quote(ticker,starttime)
                requested = newscrape(requested, ticker)
                createstat(requested, ticker)
            except:
                pass
        os.remove(f'{lpath}media/files/screener_results.csv')
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    searchparams = [date]
    cursor.execute("SELECT * FROM 'Daily Stats' WHERE time=?", searchparams)
    result = cursor.fetchall()
    connection.close()
    if len(result) == 0 :
        return "There are either no stocks looked at today yet or today's not a business day."
    else:
        finalresult = pd.DataFrame(result,columns =['Date','Ticker','Percent','N','Median','Mean','Positive Percent',
                                                    'N_cat','Same Cat Median','Same Cat Mean','Rank'])
        return finalresult


def archiveretrieval(date):
    # first check if we already have a table in the database
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?;",[date])
    results=cursor.fetchall()
    starttime = date.replace('-', '') # format string for the yahoo quote extractor

    def create_table(datetime):
        tablename = f"'{datetime}'" #SQL naming conventions
        sql_command = f"""CREATE TABLE {tablename} AS
            SELECT *
            FROM 'Daily Stats'
            WHERE time = ? AND rank > 0; """
        cursor.execute(sql_command, [(datetime)])
        sql_command = f"""ALTER TABLE {tablename}  ADD 'FinalPercent' real default -999;"""
        cursor.execute(sql_command)

    # extract previous tickers that were looked at
    data = dailystats(date)
    if not isinstance(data, str): #if we do have data for that day(aka not an error message)
        testdata = extract_quote(data['Ticker'][0], starttime)
        tablename = f"'{date}'"
        if len(results) == 0: # first check if table exists, if not make it
            create_table(date)
        if len(testdata) < 5: # not enough time has elapsed yet, so just replace the table unless we just made it
            if len(results) != 0:
                cursor.execute(f"DROP TABLE {tablename}")
                create_table(date)
        else: # we have enough data to set the final percentage, loop through all the tickers if it's not already set
            cursor.execute(f"SELECT * FROM {tablename} WHERE FinalPercent=-999.0")
            results=cursor.fetchall()
            if len(results) != 0:  # if it's an empty set, then we have already calculated the final percent.
                for ticker in cursor.execute(f"SELECT Ticker FROM {tablename}").fetchall():
                    #for ticker in data['Ticker']:
                    testdata = extract_quote(ticker[0], starttime)
                    finalpercent = truncate((testdata["Close"][3]-testdata["Close"][0])/testdata["Close"][0])
                    sql_command=f"""UPDATE {tablename}
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
                                                     'Positive Percentage','N_cat',
                                                    'Same Cat Median', 'Same Cat Mean', 'Rank','Final Percent'])
        if len(finalresult)==0:
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
    results=cursor.fetchall()
    return results

