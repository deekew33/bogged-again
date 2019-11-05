import sys
sys.path.append("..")
from shutil import copyfile
import os.path
import os, csv, pandas as pd, time, scrapy, bisect, logging, nltk, pickle, classifier as cl
from scrapy.crawler import CrawlerRunner, CrawlerProcess
from scrapy.utils.log import configure_logging
from scrapy.utils.project import get_project_settings
from twisted.internet import reactor
pd.options.mode.chained_assignment = None
from crochet import setup, wait_for, run_in_reactor, retrieve_result, TimeoutError
setup()
endtime = time.strftime("%Y%m%d",time.gmtime()) # end time is today in posix time
starttime = time.strftime("%Y%m%d",time.gmtime(time.time()-60*60*24*365*2))  # arbitrary 2 year period?
standalone = 1
if standalone == 1:
    from yahoo_quote_download import yqd
    lpath=''
else:
    from .yahoo_quote_download import yqd
    lpath='/stuff/ebdjango/'
loaddata = 0 # token for reloading data pulled earlier
save = 1 # token for saving data pulled by YQD


class QuotesSpider(scrapy.Spider):
    name = 'Quote'
    def __init__(self, args, **kwargs):
        super().__init__(**kwargs)
        self.datesecs = args['datesecs']
        self.ticker = args['ticker']
        self.finalnews = ['No match'] * len(self.datesecs)  # initialization of some variables
        self.relevancy = [0] * len(self.datesecs)
        self.matchpercent = [0] * len(self.datesecs)
        self.urllist = ['No match'] * len(self.datesecs)
        self.log(self.urllist)
        self.log(self.datesecs)
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
        # self.log(fullname)
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
        self.log(rdatesecs[0])
        if len(datesecs) > 1:
            matchidx = len(datesecs) - bisect.bisect_right(datesecs[::-1], rdatesecs[0] + 60 * 60 * 8) #can't remember why i subtracted from the length
        else:
            matchidx = bisect.bisect_right(datesecs[::-1], rdatesecs[0])-1
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
                ranking = (headlines[z].find(smolname) != -1 or headlines[z].find(self.ticker) != -1) * 8 + \
                          (urllist[z].find('investing') != -1 or urllist[z].find('story') != -1) * 4 + \
                          (urllist[z].find('realmoney') == -1 and urllist[z].find('opinion') == -1) * 2 + \
                          (headlines[z].find('?') == -1 and headlines[z].find(';') == -1) * 1 + \
                          (day - 60 * 60 * 7.5 <= rdatesecs[z] ) * 1
                # simple check for the date: the drop most likely occurred during extended trading of the previous
                # day and part of today. so the range we're looking at is from 4 PM the day before til 5 PM today.
                if day - 60 * 60 * 8 <= rdatesecs[z] < day + 60 * 60 * 16 and urllist[z].find('/k/') == -1 :
                    match = 1
                    self.log(
                        f'{headlines[z]} found for {time.strftime("%Y-%m-%d", time.localtime(day))} by {rdatelist[z]}, '
                        f'ranking of {ranking}!')
                    self.log(urllist[z])
                    # list shenanigans since I don't know how big the list is when initializing the webscraper
                    if len(self.finalnews) == datesecs.index(day):
                        self.finalnews.append(headlines[z])  # append the headline if there is no headline yet
                    elif self.relevancy[datesecs.index(day)] <= ranking:
                        self.finalnews[datesecs.index(day)] = headlines[z]  # replace with an older headline
                        self.relevancy[datesecs.index(day)] = ranking
                        self.urllist[datesecs.index(day)] = urllist[z]
                # if the headline is earlier than 4PM yesterday, and we haven't had a match yet, we give on looking
                elif rdatesecs[z] < day - 60 * 60 * 8 and match == 0 and timeover == 0:
                    self.log(f'Time out, no headlines found for {time.strftime("%Y-%m-%d",time.localtime(day))} '
                             f'by {rdatelist[z]}!')
                    timeover = 1
                    if len(self.finalnews) == datesecs.index(day):
                        self.finalnews.append('No match')
                    else:
                        self.log(datesecs.index(day))
                        self.finalnews[datesecs.index(day)] = 'No match'
                elif rdatesecs[z] < day - 60 * 60 * 8 and match == 1 and timeover == 0:
                    self.log("Looks like we're done looking")
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
            if self.urllist[self.index].find('http') == -1:
                return response.follow(f'https://www.thestreet.com/{self.urllist[self.index]}', callback=self.newsparse)
            else:
                return response.follow(self.urllist[self.index], callback=self.newsparse)

    def newsparse(self, response):
        newstext = ' '.join(response.xpath('//p/text()').getall()[1:-8])
        self.log('parsing...')
        self.newstext[self.index] = newstext
        self.log(newstext)
        while self.index < len(self.urllist) - 1:
            self.index += 1
            while self.urllist[self.index] == 'No match' and self.index < len(self.urllist) - 1:
                self.index += 1
            if self.urllist[self.index] != 'No match':  # we've hit a new headline
                if self.urllist[self.index].find('http') == -1:
                    self.log(f'https://www.thestreet.com/{self.urllist[self.index]}')
                    return response.follow(f'https://www.thestreet.com/{self.urllist[self.index]}',
                                           callback=self.newsparse)
                else:
                    self.log(self.urllist[self.index])
                    return response.follow(self.urllist[self.index], callback=self.newsparse)
        for z in range(0, len(self.datesecs)):
            if self.newstext[z] != 'No match':
                filename = f'{lpath}news/{self.ticker}-{time.strftime("%Y-%m-%d", time.gmtime(self.datesecs[z]))}.txt'
                with open(filename, "w", encoding="utf-8") as text_file:
                    print(self.newstext[z], file = text_file)
                self.matchpercent[z] = len(set(self.newstext[z]).intersection(self.newstext[0])) / len(
                    self.newstext[0])
                # self.log(self.matchpercent[self.newstext.index(text)])
        self.log('parsing complete!')
        self.save_news()

    def save_news(self):
        filename = f'{lpath}stocks/headlines-{self.ticker}.csv'
        self.log(f'Now saving {filename}')
        a = open(filename, 'w', newline='')
        writer = csv.writer(a)
        writer.writerow(['Headline', 'MatchPercent'])  # adding a header for better pandas
        for z in range(0, len(self.finalnews)):
            writer.writerow([self.finalnews[z], self.matchpercent[z] * 100])  # save the headline
        a.close()
        # self.log('Saved file %s' % filename)

    # fudge factor so that we aren't too strict at looking at news


def extract_quote(ticker):
    endtime = time.strftime("%Y%m%d",time.gmtime()) # end time is today in posix time
    starttime = time.strftime("%Y%m%d",time.gmtime(time.time()-60*60*24*365*2))  # arbitrary 2 year period?
    requested = []
    loaddata = 0
    if loaddata == 1:
        requested = pd.read_csv(f'{lpath}{ticker}.csv')
    else:
        requested = yqd.load_yahoo_quote(ticker, starttime, endtime, info='quote', format_output='dataframe')
        time.sleep(5)
    if not isinstance(requested, str):
        requested['Open'] = requested['Open'].astype(
            'float64')  # converting data types to floats and calculating percentages
        requested['Close'] = requested['Close'].astype('float64')
        requested['Percent'] = requested['Close']
        for x in range(1, len(requested)):
            requested['Percent'][x] = (requested['Close'][x] - requested['Close'][x - 1]) / requested['Close'][x - 1] * 100
    return requested


def newscrape(requested, ticker):
    # here begins the definition for the web scraper
    logging.getLogger('scrapy').propagate = False # turn off logging
    targetdrop = requested['Percent'][len(requested)-1] * 0.9
    #targetdrop = -5
    if targetdrop > 0:
        return 'Target percent was greater than 0- Bogged Again should only be used with dips.'

    print(f'Target percent is {targetdrop}... gathering data')
    datelist = []  # placeholder for dates of interest
    percentlist=[]
    finalpercentlist=[]
    for x in range(0, len(requested)-3):
        if requested['Percent'][x] <= targetdrop:
            final = (requested["Close"][x+3]-requested["Close"][x])/requested["Close"][x]*100
            datelist.append(requested["Date"][x]) # saving items of interest to separate lists
            percentlist.append(requested["Percent"][x])
            finalpercentlist.append(final)
            print(f'{ticker} suffered a {requested["Percent"][x]} percent drop on \
                {requested["Date"][x]}, 3 days later it went to {requested["Close"][x+3]} for a {final} percent change')
    datelist.append(requested["Date"][len(requested)-1])  # we add the items for today as well to the lists
    percentlist.append(requested['Percent'][len(requested)-1])
    finalpercentlist.append(0)  # place holder because we don't know the future percentage change
    datelist.reverse()  # reverse all the lists to be in reverse chronological order
    percentlist.reverse()
    finalpercentlist.reverse()
    datesecs = []
    for date in datelist:
        datesecs.append(time.mktime(time.strptime(date,"%Y-%m-%d")))  # convert all the dates into seconds
    if save == 1:
        requested.to_csv(f'stocks/{ticker}.csv')  # save extracted data to csv to avoid tangling with YQD
    if len(datesecs) > 100:
        return "There are at least 100 similar drops in the past, which probably means it's not a big enough drop. "
    categorylist = ['Unknown'] * len(datesecs)
    finaloutput = pd.DataFrame({'Date': datelist, 'Percent': percentlist, '3 Day Percent': finalpercentlist})
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
        #process.start()


    run_spider(QuotesSpider, stuff)
    # since scrapy checks the news page by page, if the first and last date are far apart it may take some time for the
    # crawling to complete.
    timeout = 0
    while not os.path.exists(f'{lpath}stocks/headlines-{ticker}.csv') and timeout < 1500:
        time.sleep(5)  # assume it takes 1 second per page, 20 days of news on one page
        timeout += 5
    # if the spider ran successfully, it will have saved the headlines in a csv in the same directory
    if os.path.exists(f'{lpath}stocks/headlines-{ticker}.csv'):
        headlines=pd.read_csv(f'{lpath}stocks/headlines-{ticker}.csv')
        os.remove(f'{lpath}stocks/headlines-{ticker}.csv')  # deleting file once it's fulfilled its purpose
        newstext=[]
        # make a dataframe out of all the stuff we care about, tack on the headlines to the side, and save it!
        finaloutput.assign(Headline=headlines.Headline)
        finaloutput.assign(MatchPercent=headlines.MatchPercent)

        # unpickle pre-generated classifier to classify news
        f = open(f'{lpath}my_classifier.pickle', 'rb')
        classifier = pickle.load(f)
        f.close()
        for x in range(0, len(headlines.Headline)):
            if headlines.Headline[x] != 'No match':
                filename = f'{ticker}-{time.strftime("%Y-%m-%d", time.gmtime(datesecs[x]))}'
                with open(f'{lpath}news/{filename}.txt') as f:
                    data = f.read()
                    categorylist[x] = classifier.classify(cl.news_features(data))
                    # if this is not part of the training set yet, copy over as unlabeled so I can label it later.
                    if not os.path.exists(f'{lpath}trainer/{filename}_labeled.txt'):
                        copyfile(f'{lpath}news/{filename}.txt',f'{lpath}trainer/{filename}.txt')
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
if standalone == 1:
    ticker='ATHM'
    abc = extract_quote(ticker)
    if not isinstance(abc, str):
        finalvento = newscrape(abc, ticker)
        finalvento.to_csv(f'stocks/{ticker}_final.csv')
