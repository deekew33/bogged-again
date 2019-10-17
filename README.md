# bogged-again
Third commit:
Did some overhauls on the headline ranking system- it'll attempt to get headlines that have the stock ticker/company name in them as the first one. Also added a rudimentary match percent for the articles- it doesn't work well and I'll probably need to try out that natural language processing thing.

Current Issues:
TheStreet doesn't actually have news on all the stocks, as I found out when I tried to test Pearson(PSO) with the script. I might need to change my news source to something more spread out, like Google or something- but at the same time I'd rather the news come from the same source. I need to think about this more. And as mentioned before, the match percent for the news needs more work.

Next build:
I've been trying to learn Django and I finally got through the tutorial- I'll probably change the script so that it becomes a pluggable app, but I wanted to at least make a commit before I do that.

-------------------------------------------------------------------------------------------------------
Second Commit:
Now it actually browses the web! It will now pull any headlines it deems likely from a website called the street, and saves it along with the previously extracted data. Code has also been commented better.

Current Issues:
The try catch loop doesn't seem to work on YQD- if it fails the first time it'll fail again. Maybe it's something to do with how it requests data? Don't think I want to look into it too much though.

Next build:
Try to get more relevant headlines? Some of the headlines pulled seem a little out there...

-------------------------------------------------------------------------------------------------------
Initial Commit:
This is a script that when run through python will take the stock ticker of whatever was hard coded into the script and look it up on Yahoo Finance through the old API. It will download financial data over the last two years(if there is that much), and extract dates when the stock had a greater percentage drop than whatever it had today. It then prints to the console when those dates were, and what the percentage change was 3 days later(the time it takes for a trade to settle in Fidelity) compared to today.

Current Issues:
YQD(the module provided at https://github.com/c0redumb/yahoo_quote_download) seems to return a 401 http unauthorized error occasionally... maybe adding a try catch loop to retry until it returns the data.

Next build:
Use a web scraper to return headlines for the stock on those days.
Organize repository better?
