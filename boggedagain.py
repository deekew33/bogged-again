#key='P2YOMS1340LHZVJF'
import sys
from yahoo_quote_download import yqd
import urllib.request,csv,pandas as pd, time
#ticker=str(input('Which stock? '))
pd.options.mode.chained_assignment = None
ticker='HRB'
endtime=time.strftime("%Y%m%d",time.gmtime()) #end time is today in posix time
starttime=time.strftime("%Y%m%d",time.gmtime(time.time()-60*60*24*365*2))#arbitrary 2 year period?
#starttime=time.gmtime()-60*60*24*365*2 #arbitrary 2 year period?
requested=yqd.load_yahoo_quote(ticker, starttime, endtime, info = 'quote', format_output = 'dataframe')
requested['Open']=requested['Open'].astype('float64')
requested['Close']=requested['Close'].astype('float64')
#pd.to_numeric(requested['Open'])
requested['Percent']=requested['Close']
for x in range(1, len(requested)):
    requested['Percent'][x] = (requested['Close'][x] - requested['Close'][x-1]) / requested['Close'][x-1] * 100
#requested['Percent']=(requested['Close']-requested['Open'])/requested['Open']*100
print(requested)
targetdrop=requested['Percent'][len(requested)-1]
print(f'Target percent is {targetdrop}... gathering data')
for x in range(0, len(requested)-3):
    if requested['Percent'][x]<=targetdrop:
        final=(requested["Close"][x+3]-requested["Close"][x])/requested["Close"][x]*100
        print(f'{ticker} suffered a {requested["Percent"][x]} percent drop on {requested["Date"][x]}, 3 days later it went to {requested["Close"][x+3]} for a {final} percent change')
#print(targetdrop)
#size=len(Requested)
#for z in range(0, size):
#    writer.writerow(Requested[size-z-1])
#a=open(f'ticker.csv', 'r', newline='')