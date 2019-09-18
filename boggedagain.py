import sys
from yahoo_quote_download import yqd
import urllib.request,csv,pandas as pd, time, scrapy, bisect
from scrapy.crawler import CrawlerProcess
# ticker=str(input('Which stock? '))
pd.options.mode.chained_assignment = None
ticker = 'ROKU'
endtime = time.strftime("%Y%m%d",time.gmtime()) # end time is today in posix time
starttime = time.strftime("%Y%m%d",time.gmtime(time.time()-60*60*24*365*2))  # arbitrary 2 year period?

loaddata = 0 # token for reloading data pulled earlier
save = 1 # token for saving data pulled by YQD


# here begins the definition for the web scraper
class QuotesSpider(scrapy.Spider):
    name = ticker

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.finalnews = [] # initialization of some variables
        self.pagenum = 0

    def start_requests(self):
        urls = [
            f'https://www.thestreet.com/quote/{ticker}/details/news?page=0', # we start from page 0 on thestreet
        ]
        self.log(urls)
        for url in urls:
            yield scrapy.Request(url=url, callback=self.parse)

    def parse(self, response):

        rdatesecs=[]
        rdatelist = response.xpath('//@datetime').getall() # extracts all date attributes embedded in the xml
        del rdatelist[0] # the first date attribute is always the date you retrieved the page, so we delete it
        #self.log(rdatelist) #debug

        for stuff in rdatelist:
            rdatesecs.append(time.mktime(time.strptime(stuff, "%Y-%m-%dT%H:%MZ"))) #conversion of the news date into seconds
        # finding which day is covered by the headlines on the page we're looking at,
        # and then ignoring all the dates in the future since the page is in reverse chronological order
        matchidx = len(datesecs) - bisect.bisect_right(datesecs[::-1],rdatesecs[0])
        # more debugging
        #self.log(matchidx)
        #self.log(datesecs[matchidx::])
        #self.log(datesecs)
        #self.log(rdatesecs)
        match = 0
        timeover = 0 # initialization of certain checks
        if not datesecs[matchidx::]: # if none of the days are covered by the headlines, we are done scraping headlines
            timeover = 1
        for day in datesecs[matchidx::]:
            self.log(f'Currently looking at {time.strftime("%Y-%m-%d",time.localtime(day))}')
            match = 0
            timeover = 0 # resetting checks at the beginning of the loop
            for z in range(0, len(rdatesecs)):
                # pulling the headlines from the page
                headlines=response.xpath('//h3[contains(@class,"news-list-compact__headline news-list-compact__headline-")]/text()').getall()
                # simple check for the date: the drop most likely occurred during extended trading of the previous day and part of today.
                # so the range we're looking at is from 4 PM the day before til 4 PM today.
                if day - 60 * 60 * 8 <= rdatesecs[z] < day + 60 * 60 * 16:
                    match = 1
                    self.log(
                        f'{headlines[z]} found for {time.strftime("%Y-%m-%d", time.localtime(day))} by {rdatelist[z]}!')
                    # list shenanigans since I don't know how big the list is when initializing the webscraper
                    if len(self.finalnews) == datesecs.index(day):
                        self.finalnews.append(headlines[z]) # append the headline if there is no headline for that date yet
                    else:
                        self.finalnews[datesecs.index(day)] = headlines[z] # replace with an older headline
                # if the headline is earlier than 4PM yesterday, and we haven't had a match yet, we give on looking
                elif rdatesecs[z] < day - 60 * 60 * 8 and match == 0 and timeover == 0:
                    self.log(f'Time out, no headlines found for {time.strftime("%Y-%m-%d",time.localtime(day))} by {rdatelist[z]}!')
                    timeover = 1
                    if len(self.finalnews) == datesecs.index(day):
                        self.finalnews.append('No match')
                    else:
                        self.finalnews[datesecs.index(day)] = 'No match'
        # if we haven't reached a point where the headlines occur before our lower date bound, we check the next page of news
        # and call the parse method on that page again
        if timeover == 0 and match == 0:
            self.pagenum += 1
            next_page = f'https://www.thestreet.com/quote/{ticker}/details/news?page={self.pagenum}'
            self.log(next_page)
            return response.follow(next_page, callback=self.parse)
        # assuming we reached this point we're probably done scraping for all the dates, so save the headlines in a csv
        if timeover == 1 or match == 1:
            self.save_news()

    def save_news(self):
        filename = f'headlines-{ticker}.csv'
        a=open(filename, 'w', newline='')
        writer = csv.writer(a)
        writer.writerow(['Headline']) # adding a header for better pandas
        for z in range(0, len(self.finalnews)):
            writer.writerow([self.finalnews[z]]) #save the headline
        a.close()
        self.log('Saved file %s' % filename)


requested = []
if loaddata == 1:
    requested = pd.read_csv(f'{ticker}.csv')
else:
    while len(requested)<20: # TODO: currently kind of a bad check...
        try:
            requested = yqd.load_yahoo_quote(ticker, starttime, endtime, info='quote', format_output='dataframe')
        except:
            print('YQD screwed up')
            pass
        time.sleep(5)
requested['Open'] = requested['Open'].astype('float64') # converting data types to something usable and calculating percentages
requested['Close'] = requested['Close'].astype('float64')
requested['Percent']=requested['Close']
for x in range(1, len(requested)):
    requested['Percent'][x] = (requested['Close'][x] - requested['Close'][x-1]) / requested['Close'][x-1] * 100
targetdrop = requested['Percent'][len(requested)-1] * 0.9 #a fudge factor so that we aren't too strict at looking at news
print(f'Target percent is {targetdrop}... gathering data')
datelist = [] #placeholder for dates of interest
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
datelist.append(requested["Date"][len(requested)-1]) #we add the items for today as well to the lists
percentlist.append(requested['Percent'][len(requested)-1])
finalpercentlist.append(0) # place holder because we don't know the future percentage change
datelist.reverse() #reverse all the lists to be in reverse chronological order
percentlist.reverse()
finalpercentlist.reverse()
datesecs = []
for date in datelist:
    datesecs.append(time.mktime(time.strptime(date,"%Y-%m-%d"))) #convert all the dates we're interested in to seconds
#print(datelist)
if save == 1:
    requested.to_csv(f'{ticker}.csv') # save extracted data to csv to avoid tangling with YQD
# launching the webspider here
process = CrawlerProcess({
    'USER_AGENT': 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1)'
})
process.crawl(QuotesSpider)  # the script will block here until the crawling is finished
process.start()

# if the spider ran successfully, it will have saved the headlines in a csv in the same directory
headlines=pd.read_csv(f'headlines-{ticker}.csv')
#print(headlines)
# make a dataframe out of all the stuff we care about, tack on the headlines to the side, and save it!
finaloutput=pd.DataFrame({'Date':datelist,'Percent':percentlist,'3 Day Percent':finalpercentlist})
finaloutput.assign(Headline=headlines.Headline)
finalfinal=finaloutput.join(headlines)
finalfinal.to_csv(f'{ticker}_Final.csv')
