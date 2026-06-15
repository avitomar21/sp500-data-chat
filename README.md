# Chat with the S&P 500

For this project, I decided to choose an S&P 500 dataset. This dataset contains information about each company's sector, stock price, market cap, and etc. I choose this primarily because I thought it would be interesting to use a stock dataset for this specific application, but also because the dataset is particularly well structured and contains many different fields that could be explored. Questions can be asked of the data that ask for specific information from the table, such as "Which company has the highest market cap?" or "Show me all the technology stocks?" The app will interpret these questions and extract the relevant information from the table to provide the answer.

## How to run it

You need Python 3.10 or newer. Run pip install -r requirements.txt to install the libraries it needs (streamlit, pandas, and rank-bm25), then run python -m streamlit run app.py to open the app in your browser. You can also run python test_engine.py and python test_retrieval.py to check the questions and the text search work without opening the app. The app needs no API key.

## The dataset

I used the S&P 500 Stocks dataset from Kaggle (https://www.kaggle.com/datasets/andrewmvd/sp-500-stocks) and the files are in the data folder. The main file sp500_companies.csv has 502 rows, one per company, with columns like symbol, name, sector, industry, price, market cap, revenue growth, and employees. The second file sp500_index.csv has the daily value of the index from December 2014 to December 2024, which I use for the question about how the index changed over time.

There is also a third file, sp500_history.csv.gz, which has the daily closing stock price for 472 of the companies from January 2000 to February 2026. It comes from a Kaggle historical prices dataset (the original file is called SP500_Historical_Data.csv and is 142 MB, so I kept only the three columns I need, ticker, date, and closing price, and compressed it down to about 13 MB). This file powers the questions about how one company changed over the years.

## Sample questions

These are the questions I put in the app as buttons: which company has the highest market cap, top 5 companies by revenue growth, what is the average price in the Technology sector, which sector has the most companies, which sector has the highest total market cap, how many companies are headquartered in California, tell me about NVDA, and how has the S&P 500 index changed over time. It also handles similar ones like top 10 cheapest stocks, which state has the most companies, how many employees does Microsoft have, and show me healthcare companies.

## How the app finds the answer

Every question goes through four steps in qa_engine.py. First it makes the question lowercase and looks for words it knows. Then it matches those words to the data, so market cap points to the MarketCap column, highest means sort from big to small, average means take the mean, how many means count, and a word like technology or california means filter to that group. Then it runs the one pandas calculation that matches. Finally it returns the answer plus the list of steps it took, which you can see in the app under "how the app found this answer." I did it this way so I can explain exactly how every answer was found.

## Company price change over time

The app can also answer questions like "how did Apple's stock change from 2020 to 2021?" or "how has NVDA changed since 2015?". This lives in history.py. A question takes this path only when it contains both a specific company and a four digit year, which is a combination the other engines cannot handle. The app looks up that company's daily prices, cuts out the window between the start of the first year and the end of the last year, and uses the first trading day in the window as the start price and the last trading day as the end price. Doing it that way automatically handles weekends and holidays, because the market is closed on those days and they simply are not in the data. Then the change is just the end price minus the start price, and the percent change is that difference divided by the start price. The answer shows the change in dollars and percent, a line chart of the price over the period, and the steps it took, including the exact trading days it used. One thing to know is that this measures the closing stock price, not market cap, because the history file only contains prices. If the company is one of the 30 or so that the history file does not cover, or the years are outside 2000 to 2026, the app says so instead of guessing.

## Text search for open-ended questions (BM25)

The keyword engine above only works for questions about the columns it knows, like price or sector. But the dataset also has a Summary column that describes what each company actually does, so I added a second way to answer questions that are about topics instead of numbers, like "which companies work on electric vehicles?" or "what companies are involved in cloud computing?". There is no electric vehicle column to filter on, so instead the app searches the summary text.

It does this with BM25, which is the classic ranking formula that search engines use. It is pure math, so it needs no AI and no API key. For a search like "electric vehicles" it gives every company summary a relevance score based on three things: how many times the search words appear in that summary, how rare those words are across all 502 summaries (rare words like "vehicle" count for more than common words like "services"), and the length of the summary so long descriptions do not win just for being long. The company with the highest score is the best match. This lives in retrieval.py.

A small router (router.py) decides which engine to use. It tries the keyword engine first, and if that engine understands the question it uses its answer. If the keyword engine does not understand the question and returns its fallback message, the app runs the BM25 text search instead. The app still shows the steps it took, including which companies BM25 found and their relevance scores, so the text search is just as transparent as the keyword engine.

## Notes on the project

I chose the S&P 500 companies because it is finance, which is one of the suggested topics, and it has a good mix of category columns like sector and state and number columns like price and market cap, so I could do both rankings and group comparisons.

The app can answer rankings like the biggest companies or cheapest stocks, group comparisons like how many companies are in each sector, averages and counts after filtering like the average price in Technology, basic info about a single company, and how the index moved over ten years.

The hardest part was turning normal English into the right calculation, because people say the same thing many ways like biggest or most valuable, so I made keyword dictionaries and set market cap as the default when no number is named. Another tricky part was telling filtering apart from grouping, so I made it treat a sector name as a filter and the plain word sector as a grouping. I also only match ticker symbols in capital letters so company names that are normal words do not cause problems.

If I had more time I would add fuzzy matching for typos, support harder questions that need more than one step, and deploy it online with Streamlit Community Cloud.
