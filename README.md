# bogged-again
Initial Commit:
This is a script that when run through python will take the stock ticker of whatever was hard coded into the script and look it up on Yahoo Finance through the old API. It will download financial data over the last two years(if there is that much), and extract dates when the stock had a greater percentage drop than whatever it had today. It then prints to the console when those dates were, and what the percentage change was 3 days later(the time it takes for a trade to settle in Fidelity) compared to today.

Current Issues:
YQD(the module provided at https://github.com/c0redumb/yahoo_quote_download) seems to return a 401 http unauthorized error occasionally... maybe adding a try catch loop to retry until it returns the data.

Next build:
Use a web scraper to return headlines for the stock on those days.
Organize repository better?
