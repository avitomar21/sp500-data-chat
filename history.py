"""
history.py - answers questions like "how did Apple's stock change from 2020 to 2021?"

WHAT DATA THIS USES
-------------------
data/sp500_history.csv.gz - the daily closing stock price for 472 S&P 500
companies from January 2000 to February 2026. Three columns: Ticker, Date,
Close. It is a slimmed-down, compressed copy of the Kaggle file
SP500_Historical_Data.csv (the raw download is 142 MB with 8 columns; we only
need these 3, which shrinks it to about 13 MB).

Change here is measured by the CLOSING STOCK PRICE on the first and last
trading day of the period. It is NOT market cap - the history file only has
prices, so the answer wording says "stock price" on purpose.

HOW WEEKENDS AND HOLIDAYS ARE HANDLED
-------------------------------------
The stock market is closed on weekends and holidays, so there is no row for
dates like January 1. Instead of looking up one exact date, we grab the whole
window of rows between the start and end of the period, then use the FIRST
trading day in that window as the start price and the LAST trading day as the
end price. That skips weekends and holidays automatically, with no special
case code.
"""

import re

import pandas as pd

from qa_engine import Answer, find_company

# Matches a 4-digit year like 1999 or 2024, as a whole word.
YEAR_PATTERN = re.compile(r"\b(19\d{2}|20\d{2})\b")

# Matches a possessive like "Apple's" so we can strip the 's. Without this,
# "Apple's" becomes "apples" during cleaning and no longer matches "apple".
POSSESSIVE_PATTERN = re.compile(r"[’']s\b")

# Example questions for this feature, shown as buttons in the app.
HISTORY_SAMPLE_QUESTIONS = [
    "How did Apple's stock change from 2020 to 2021?",
    "How has NVDA changed since 2015?",
]


def load_history(data_dir=None):
    """Read the daily price history. pandas unzips the .gz file by itself."""
    from pathlib import Path
    data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
    return pd.read_csv(data_dir / "sp500_history.csv.gz", parse_dates=["Date"])


def find_years(q):
    """Pull the 4-digit years out of a question. 'from 2020 to 2021' -> [2020, 2021]"""
    return [int(year) for year in YEAR_PATTERN.findall(q)]


def find_hyphen_ticker(question, companies):
    """Catch tickers that contain a hyphen, like BRK-B or BF-B.

    The regular company finder looks for plain capital-letter tickers, so a
    hyphenated one slips past it. This is a small extra net just for those.
    """
    symbols = set(companies["Symbol"])
    for token in re.findall(r"\b[A-Z]{1,5}-[A-Z]\b", question):
        if token in symbols:
            row = companies[companies["Symbol"] == token].iloc[0]
            return row, f"Recognized **{token}** as a ticker symbol."
    return None, None


def try_history_answer(question, companies, history):
    """Answer a company-over-time question, or return None if this isn't one.

    A question counts as "company over time" only when BOTH things are found:
      1. at least one 4-digit year, AND
      2. a specific company (a ticker like NVDA or a name like Apple).
    If either is missing we return None and the router moves on to the other
    engines, so nothing else in the app changes.
    """
    q = question.lower()

    # --- 1. Is there a year in the question? -------------------------------
    years = find_years(q)
    if not years:
        return None

    # --- 2. Is there a specific company in the question? -------------------
    # First strip possessives ("Apple's stock" -> "Apple stock") so the name
    # matcher can see the name, then reuse the exact same company finder the
    # keyword engine uses. Hyphenated tickers (BRK-B) get a special check.
    cleaned = POSSESSIVE_PATTERN.sub("", question)
    row, how_found = find_company(cleaned, cleaned.lower(), companies, False)
    if row is None:
        row, how_found = find_hyphen_ticker(question, companies)
    if row is None:
        return None

    steps = [how_found]

    # --- 3. Turn the years into a start year and an end year ---------------
    #   two or more years  -> "from 2020 to 2021" style, use min and max
    #   "since" + one year -> from that year up to the newest data we have
    #   just one year      -> inside that single year
    if len(years) >= 2:
        start_year, end_year = min(years), max(years)
    elif "since" in q.split():
        start_year, end_year = years[0], history["Date"].max().year
    else:
        start_year = end_year = years[0]
    steps.append(f"Read the time period as **{start_year} to {end_year}** "
                 f"(from the years mentioned in your question).")

    # --- 4. Get this company's rows from the history file ------------------
    symbol = row["Symbol"]
    prices = history[history["Ticker"] == symbol]
    if prices.empty:
        steps.append(f"Searched the price history file, but it has no rows "
                     f"for {symbol}. It covers 472 of the 502 companies.")
        return Answer(f"Sorry - my price history file doesn't include "
                      f"**{row['Name']} ({symbol})**, so I can't compute its "
                      f"change over time.", steps, kind="history_empty")

    # --- 5. Cut out the requested window of time ---------------------------
    window = prices[(prices["Date"] >= pd.Timestamp(start_year, 1, 1)) &
                    (prices["Date"] <= pd.Timestamp(end_year, 12, 31))]

    # If the window is empty the years fall outside what the file covers.
    if window.empty:
        covered = f"{prices['Date'].min():%b %Y} to {prices['Date'].max():%b %Y}"
        steps.append(f"The history for {symbol} only covers {covered}, and the "
                     f"requested period is outside it.")
        return Answer(f"I have no {symbol} prices for {start_year} to "
                      f"{end_year}. My data covers **{covered}**.",
                      steps, kind="history_empty")

    # Warn (in the steps) if the request goes beyond the data on either side.
    if pd.Timestamp(start_year, 1, 1) < prices["Date"].min():
        steps.append(f"Note: the data only starts in "
                     f"{prices['Date'].min():%b %Y}, so the period was trimmed.")
    if pd.Timestamp(end_year, 12, 31) > prices["Date"].max():
        steps.append(f"Note: the data ends in {prices['Date'].max():%b %Y}, "
                     f"so the period was trimmed.")

    # --- 6. First and last trading day = start and end prices --------------
    first = window.iloc[0]     # earliest trading day in the window
    last = window.iloc[-1]     # latest trading day in the window
    steps.append(f"The market is closed on weekends and holidays, so I used "
                 f"the first trading day in the window (**{first['Date']:%b %d, %Y}**) "
                 f"and the last one (**{last['Date']:%b %d, %Y}**). "
                 f"{len(window):,} trading days in between.")

    # --- 7. The actual math -------------------------------------------------
    change = last["Close"] - first["Close"]
    percent = change / first["Close"] * 100
    steps.append("Change = end price minus start price. Percent = that change "
                 "divided by the start price, times 100.")
    steps.append("This measures the closing stock price, not market cap - "
                 "the history file only contains prices.")

    verb = "rose" if change >= 0 else "fell"
    high = window.loc[window["Close"].idxmax()]
    low = window.loc[window["Close"].idxmin()]
    text = (f"**{row['Name']} ({symbol})** {verb} from "
            f"**${first['Close']:,.2f}** ({first['Date']:%b %d, %Y}) to "
            f"**${last['Close']:,.2f}** ({last['Date']:%b %d, %Y}) - "
            f"a change of **${change:,.2f}** (**{percent:+,.1f}%**). "
            f"In that period its highest close was ${high['Close']:,.2f} "
            f"({high['Date']:%b %Y}) and its lowest ${low['Close']:,.2f} "
            f"({low['Date']:%b %Y}). Measured by stock price, not market cap.")

    # A tiny start/end table, plus the full price line for the chart.
    table = pd.DataFrame([
        {"Point": "Start", "Date": f"{first['Date']:%Y-%m-%d}", "Price": f"${first['Close']:,.2f}"},
        {"Point": "End", "Date": f"{last['Date']:%Y-%m-%d}", "Price": f"${last['Close']:,.2f}"},
        {"Point": "Change", "Date": "", "Price": f"${change:,.2f} ({percent:+,.1f}%)"},
    ])
    chart = window.set_index("Date")[["Close"]].rename(
        columns={"Close": f"{symbol} closing price ($)"})
    return Answer(text, steps, table=table, chart=chart,
                  chart_kind="line", kind="history")
