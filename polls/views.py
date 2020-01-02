from django.http import HttpResponseRedirect, HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from .models import Ticker
from .forms import TickerForm
from .boggedagain import boggedagain
import math, time, os, sqlite3
if not os.path.exists('/stuff/venvs/python36'):
    lpath = ''
else: #we're on the linux server
    lpath = '/stuff/ebdjango/'

def bogging(request):
    ticker = request.GET['ticker'].upper()
    starttime = time.strftime("%Y%m%d",time.gmtime(time.time()-60*60*24*365*2))
    requested = boggedagain.extract_quote(ticker, starttime)
    if not isinstance(requested, str):
        requested = boggedagain.newscrape(requested, ticker)
    if isinstance(requested, str):
        return render(request, 'polls/error.html', {'error': requested})
    else:
        stats = boggedagain.createstat(requested, ticker)
        requested = requested.set_index('URL')

    return render(request, 'polls/bogging.html',
                  {'headers':requested.columns,'finaldata':requested.iterrows(),
                   'ticker':ticker,'statheaders':stats.columns, 'stats':stats.iterrows()})

def input(request):
    return render(request, 'polls/input.html')

def dailybog(request):
    date = time.strftime("%Y-%m-%d",time.localtime()) #gm time is 5 hours ahead of EST
    dailydata = boggedagain.dailystats(date)
    if isinstance(dailydata, str):
        return render(request, 'polls/error.html', {'error': dailydata})
    return render(request, 'polls/dailybog.html',{'headers':dailydata.columns,'finaldata':dailydata.iterrows()})

def entrance(request):
    daterange = boggedagain.rangeretrieval()
    connection = sqlite3.connect(f"{lpath}results.db")
    cursor = connection.cursor()
    result = cursor.execute("SELECT * FROM 'Archives' ORDER BY time DESC LIMIT 20").fetchall()
    headers=['Date','All stocks','Top 10 Rank','Rank 1k+']
    performance = {'all':0, 'top10':0,'rank1k':0}
    for thing in result:
        performance['all']+= thing[1]
        performance['top10'] += thing[2]
        performance['rank1k'] += thing[3]
    performance['all'] = math.ceil(performance['all']/len(result)*100)/100
    performance['top10'] = math.ceil(performance['top10'] / len(result) * 100) / 100
    performance['rank1k'] = math.ceil(performance['rank1k'] / len(result) * 100) / 100
    connection.close()
    return render(request,'polls/entrance.html',{'mindate':daterange[0][0], 'performance':performance,
                                                 'maxdate':daterange[0][1], 'headers':headers, 'results':result})

def bogchives(request):
    date = request.GET['date']
    bogchive = boggedagain.archiveretrieval(date)
    if isinstance(bogchive, str):
        return render(request, 'polls/error.html', {'error': bogchive})
    else:
        ensemble = [0]*3
        try:
            ensemble[0] = math.ceil(bogchive['Final Percent'].mean()*100)/100
            ensemble[1] = math.ceil(bogchive['Final Percent'][0:10].mean() * 100) / 100
            ensemble[2] = math.ceil(bogchive[bogchive['Rank']>1000]['Final Percent'].mean()*100)/100
        except:
            pass
        if ensemble[0] != -999: # we add an updated result to the grand archives
            connection = sqlite3.connect(f"{lpath}results.db")
            cursor = connection.cursor()
            cursor.execute(f"SELECT * FROM 'Archives' WHERE time='{date}'")
            results = cursor.fetchall()
            if len(results) == 0:
                cursor.execute(f"INSERT INTO 'Archives' VALUES ('{date}', {ensemble[0]}, {ensemble[1]}, {ensemble[2]});")
            connection.commit()
            connection.close()

        return render(request, 'polls/bogchives.html', {'headers': bogchive.columns,
                                                    'finaldata': bogchive.iterrows(),'ensemble':ensemble})

def bloggedagain(request):
    return render(request,'polls/blog.html')
