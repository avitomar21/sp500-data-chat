"""
qa_engine.py - this is the brain of the app. It figures out the answers.

Here is the plan it follows for every question:
  1. READ the question and look for words we already know.
  2. MATCH those words to a column ("market cap" -> MarketCap), a thing to do
     ("highest" -> put the biggest first, "average" -> find the mean), and any
     filters ("technology" -> only keep Technology companies).
  3. RUN the matching pandas step on the data.
  4. RETURN the answer plus the steps we took, so the app can show HOW it
     got the answer.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

# ---------------------------------------------------------------------------
# 1. Getting the data out of the files
# ---------------------------------------------------------------------------

# The CSV column names are long, so we swap them for short easy names.
FRIENDLY_NAMES = {
    "Shortname": "Name",
    "Currentprice": "Price",
    "Marketcap": "MarketCap",
    "Revenuegrowth": "RevenueGrowth",
    "Fulltimeemployees": "Employees",
    "Longbusinesssummary": "Summary",
}

KEEP_COLUMNS = ["Symbol", "Name", "Sector", "Industry", "Price", "MarketCap",
                "RevenueGrowth", "Employees", "City", "State", "Country", "Summary"]


def load_data(data_dir=None):
    """Open the two CSV files and rename the columns to the easy names."""
    data_dir = Path(data_dir) if data_dir else Path(__file__).parent / "data"
    companies = (pd.read_csv(data_dir / "sp500_companies.csv")
                 .rename(columns=FRIENDLY_NAMES)[KEEP_COLUMNS])
    index_df = pd.read_csv(data_dir / "sp500_index.csv", parse_dates=["Date"])
    return companies, index_df


# ---------------------------------------------------------------------------
# 2. Word lists. This is how the app understands what you typed.
# ---------------------------------------------------------------------------

# These words mean the question is about a number column.
METRIC_KEYWORDS = {
    "MarketCap":     ["market cap", "marketcap", "market capitalization", "market value",
                      "valuation", "mkt cap", "valuable", "worth", "company size"],
    "Price":         ["price", "stock price", "share price", "price per share",
                      "per share", "trading at", "expensive", "cheapest", "cheap",
                      "affordable", "afford", "cost", "costly", "pricey"],
    "RevenueGrowth": ["revenue growth", "sales growth", "growth", "growing", "grew",
                      "expanding", "expansion", "fastest growing", "revenue increase"],
    "Employees":     ["employees", "employee", "headcount", "head count", "workforce",
                      "staff", "staffing", "workers", "personnel", "employs", "people"],
}

METRIC_LABELS = {
    "MarketCap": "market cap",
    "Price": "stock price",
    "RevenueGrowth": "revenue growth",
    "Employees": "number of employees",
}

# These words mean a group column we can sort the companies into.
GROUP_KEYWORDS = {
    "Sector":   ["sector"],
    "Industry": ["industry", "industries"],
    "State":    ["state"],
    "City":     ["city", "cities"],
    "Country":  ["country", "countries"],
}

# These words tell us what to do, like sort, count, or average.
DESCENDING_WORDS = ["highest", "high", "most", "biggest", "bigger", "largest", "larger",
                    "top", "best", "greatest", "maximum", "max", "expensive", "fastest",
                    "leading", "leader", "richest", "wealthiest", "dominant", "strongest",
                    "huge", "massive", "record", "premier", "superior", "outperforming"]
ASCENDING_WORDS = ["lowest", "low", "lower", "least", "smallest", "smaller", "fewest",
                   "cheapest", "bottom", "minimum", "min", "worst", "slowest",
                   "weakest", "poorest", "tiniest", "underperforming", "declining",
                   "shrinking"]
AVERAGE_WORDS = ["average", "avg", "averaged", "on average", "mean", "typical"]
TOTAL_WORDS = ["total", "combined", "sum", "altogether", "aggregate", "overall",
               "collectively", "grand total", "summed"]
COUNT_WORDS = ["how many", "number of", "count", "how many companies",
               "total number", "quantity of", "tally", "count of"]
TREND_WORDS = ["trend", "over time", "index", "history", "historical", "historically",
               "time series", "trajectory", "over the years", "year over year", "yoy"]

# Short nicknames people use for sectors -> the real name in the CSV.
SECTOR_ALIASES = {
    "tech": "Technology",
    "software": "Technology",
    "finance": "Financial Services",
    "financial": "Financial Services",
    "bank": "Financial Services",
    "banks": "Financial Services",
    "banking": "Financial Services",
    "insurance": "Financial Services",
    "health": "Healthcare",
    "health care": "Healthcare",
    "pharma": "Healthcare",
    "pharmaceutical": "Healthcare",
    "medical": "Healthcare",
    "biotech": "Healthcare",
    "drug": "Healthcare",
    "industrial": "Industrials",
    "manufacturing": "Industrials",
    "materials": "Basic Materials",
    "mining": "Basic Materials",
    "chemicals": "Basic Materials",
    "communication": "Communication Services",
    "telecom": "Communication Services",
    "media": "Communication Services",
    "staples": "Consumer Defensive",
    "discretionary": "Consumer Cyclical",
    "retail": "Consumer Cyclical",
    "oil": "Energy",
    "gas": "Energy",
    "utility": "Utilities",
    "power": "Utilities",
    "reit": "Real Estate",
    "property": "Real Estate",
}

# Full state names -> the short 2 letter code that is in the CSV.
STATE_NAMES = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN", "mississippi": "MS",
    "missouri": "MO", "montana": "MT", "nebraska": "NE", "nevada": "NV",
    "new hampshire": "NH", "new jersey": "NJ", "new mexico": "NM", "new york": "NY",
    "north carolina": "NC", "north dakota": "ND", "ohio": "OH", "oklahoma": "OK",
    "oregon": "OR", "pennsylvania": "PA", "rhode island": "RI", "south carolina": "SC",
    "south dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA", "west virginia": "WV",
    "wisconsin": "WI", "wyoming": "WY",
}

WORD_NUMBERS = {"two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
                "seven": 7, "eight": 8, "nine": 9, "ten": 10}

# These are the example questions that show up as buttons.
SAMPLE_QUESTIONS = [
    "Which company has the highest market cap?",
    "Top 5 companies by revenue growth",
    "What is the average price in the Technology sector?",
    "Which sector has the most companies?",
    "Which sector has the highest total market cap?",
    "How many companies are headquartered in California?",
    "Tell me about NVDA",
    "How has the S&P 500 index changed over time?",
]


# ---------------------------------------------------------------------------
# 3. The box that holds an answer. Every question makes one of these.
# ---------------------------------------------------------------------------

@dataclass
class Answer:
    text: str                       # the answer written out in words
    steps: list = field(default_factory=list)   # the steps we did to find it
    table: pd.DataFrame | None = None            # a table to show, if there is one
    chart: pd.DataFrame | None = None            # a chart to show, if there is one
    chart_kind: str = "bar"                      # what kind of chart, "bar" or "line"
    kind: str = "answer"                         # which rule we used ("fallback" = none worked)


# ---------------------------------------------------------------------------
# 4. Tiny helper functions for making text look nice and matching words
# ---------------------------------------------------------------------------

def fmt_money(value):
    """Make a giant number look nice, like '$3.85 trillion'."""
    for cutoff, suffix in [(1e12, "trillion"), (1e9, "billion"), (1e6, "million")]:
        if abs(value) >= cutoff:
            return f"${value / cutoff:,.2f} {suffix}"
    return f"${value:,.0f}"


def fmt_value(column, value):
    """Make a number look nice depending on which column it came from."""
    if pd.isna(value):
        return "n/a"
    if column == "MarketCap":
        return fmt_money(value)
    if column == "Price":
        return f"${value:,.2f}"
    if column == "RevenueGrowth":
        return f"{value * 100:.1f}%"
    if column == "Employees":
        return f"{value:,.0f}"
    return str(value)


def normalize(text):
    """Make text lowercase and take out punctuation so 'Coca-Cola' matches 'coca cola'."""
    text = text.lower().replace("'", "").replace("’", "")
    text = re.sub(r"[.,&()\-/]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def word_match(q, phrase):
    """Say yes if the word is in the question as a whole word (so 'tech' is not found inside 'biotech')."""
    stem = re.escape(phrase.lower().rstrip("s"))
    return re.search(rf"\b{stem}s?\b", q) is not None


_NAME_SUFFIXES = re.compile(
    r"\b(incorporated|inc|corporation|corp|company|companies|co|plc|ltd|limited|"
    r"group|holdings|holding|class [ab]|the)\b")


def clean_company_name(name):
    """Chop off the extra company words, so 'Apple Inc.' just becomes 'apple'."""
    name = _NAME_SUFFIXES.sub(" ", normalize(name))
    return re.sub(r"\s+", " ", name).strip()


# ---------------------------------------------------------------------------
# 5. These functions figure out what the question is really asking for
# ---------------------------------------------------------------------------

def find_metric(q):
    """Which number column is the question about? (None if we can't tell)"""
    for column, words in METRIC_KEYWORDS.items():
        for word in words:
            if word in q:
                return column, word
    return None, None


def find_group(q, exclude):
    """Which group column should we group by? (None if we can't tell)"""
    for column, words in GROUP_KEYWORDS.items():
        if column in exclude:
            continue  # we already used this column as a filter, so skip it
        if any(word_match(q, w) for w in words):
            return column
    return None


def find_top_n(q):
    """Find the number after 'top'. 'top 5' is 5, just 'top' is 5, and no 'top' is None."""
    match = re.search(r"top\s+(\d+)", q)
    if match:
        return int(match.group(1))
    for word, number in WORD_NUMBERS.items():
        if f"top {word}" in q:
            return number
    return 5 if "top" in q.split() else None


def find_company(question, q, companies, has_superlative):
    """Look for a stock symbol like NVDA or a company name like apple in the question."""
    # 1) Stock symbols are 2 to 5 capital letters, like "MSFT".
    symbols = set(companies["Symbol"])
    for token in re.findall(r"\b[A-Z]{2,5}\b", question):
        if token in symbols:
            row = companies[companies["Symbol"] == token].iloc[0]
            return row, f"Recognized **{token}** as a ticker symbol."
    # 2) Company names. We skip this for questions like "which company has
    #    the highest price", because a name match there would just be luck.
    if has_superlative:
        return None, None
    qn = normalize(question)
    names = sorted(((clean_company_name(r["Name"]), i) for i, r in companies.iterrows()),
                   key=lambda pair: -len(pair[0]))  # check the longest names first
    for name, i in names:
        if len(name) >= 4 and re.search(rf"\b{re.escape(name)}\b", qn):
            row = companies.loc[i]
            return row, f"Matched the words \"{name}\" to **{row['Name']}**."
    return None, None


def apply_filters(q, companies, steps):
    """Cut the table down when the question names a sector, industry, state, and so on."""
    df = companies
    used_columns = set()
    description = []

    def add_filter(column, value, label):
        nonlocal df
        df = df[df[column] == value]
        used_columns.add(column)
        description.append(label)
        steps.append(f"Found \"{label}\" in your question - filtered to "
                     f"**{column} = {value}** ({len(df)} companies left).")

    # Sector. Try the real names first ("technology"), then nicknames ("tech").
    for sector in companies["Sector"].unique():
        if word_match(q, sector):
            add_filter("Sector", sector, sector)
            break
    else:
        for alias, sector in SECTOR_ALIASES.items():
            if word_match(q, alias):
                add_filter("Sector", sector, sector)
                break

    # Industry, like "semiconductors" or "banks".
    for industry in companies["Industry"].dropna().unique():
        if "Sector" in used_columns and industry.lower() in description[0].lower():
            continue
        if word_match(q, industry):
            add_filter("Industry", industry, industry)
            break

    # States by their full name ("california" -> CA). Do the longest names
    # first so "west virginia" gets picked before "virginia".
    for state_name in sorted(STATE_NAMES, key=len, reverse=True):
        if word_match(q, state_name):
            add_filter("State", STATE_NAMES[state_name], state_name.title())
            break
    else:
        # Cities. We only check these if no state matched.
        for city in sorted(companies["City"].dropna().unique(), key=len, reverse=True):
            if word_match(q, city):
                add_filter("City", city, city)
                break

    # Countries, like "ireland" or "united kingdom".
    for country in companies["Country"].dropna().unique():
        if country != "United States" and word_match(q, country):
            add_filter("Country", country, country)
            break

    return df, used_columns, " / ".join(description)


# ---------------------------------------------------------------------------
# 6. These functions build the answer, one for each kind of question
# ---------------------------------------------------------------------------

def scale_for_chart(values, metric):
    """Shrink the chart numbers (market cap in billions, growth in %) so they are easy to read."""
    if metric == "MarketCap":
        return values / 1e9, " ($B)"
    if metric == "RevenueGrowth":
        return values * 100, " (%)"
    return values, ""


def make_table(df, metric=None):
    """Make a neat table with the main columns plus the number we are talking about."""
    columns = ["Symbol", "Name", "Sector", "Price", "MarketCap"]
    if metric and metric not in columns:
        columns.append(metric)
    out = df[columns].copy()
    for col in out.columns:
        if col in METRIC_LABELS:
            out[col] = out[col].map(lambda v: fmt_value(col, v))
    return out


def trend_answer(index_df, steps):
    series = index_df.set_index("Date")["S&P500"]
    first, last = series.iloc[0], series.iloc[-1]
    change = (last - first) / first * 100
    low_date, high_date = series.idxmin(), series.idxmax()
    years = (series.index[-1] - series.index[0]).days / 365
    steps.append("Spotted a trend keyword - switched to the `sp500_index.csv` "
                 "file (daily index values).")
    steps.append("Compared the first and last values and located the "
                 "all-time low and high.")
    text = (f"Over the past **{years:.0f} years** "
            f"({series.index[0]:%b %Y} to {series.index[-1]:%b %Y}) the S&P 500 went "
            f"from **{first:,.0f}** to **{last:,.0f}** - a gain of **{change:,.0f}%**. "
            f"Its lowest point was **{series.min():,.0f}** ({low_date:%b %Y}) and its "
            f"highest **{series.max():,.0f}** ({high_date:%b %Y}).")
    chart = index_df.set_index("Date")[["S&P500"]]
    return Answer(text, steps, chart=chart, chart_kind="line", kind="trend")


def company_answer(row, metric, steps):
    name = f"**{row['Name']} ({row['Symbol']})**"
    if metric:
        if metric == "Employees":
            text = f"{name} has **{fmt_value(metric, row[metric])} employees**."
        else:
            text = (f"{name} has a {METRIC_LABELS[metric]} of "
                    f"**{fmt_value(metric, row[metric])}**.")
        steps.append(f"Matched a metric keyword - read the **{metric}** "
                     "column for this company.")
    else:
        text = (f"{name} is a **{row['Sector']}** company ({row['Industry']}), "
                f"headquartered in {row['City']}, {row['State']}, {row['Country']}.")
        steps.append("No specific number was asked for, so I built a profile "
                     "from the company's row.")
    summary = str(row["Summary"]).split(". ")[0]
    text += f"\n\n> {summary[:300]}{'...' if len(summary) > 300 else '.'}"
    table = make_table(row.to_frame().T, metric)
    return Answer(text, steps, table=table, kind="company")


def group_answer(df, group_col, metric, operation, ascending, scope, steps):
    if operation == "count":
        series = df.groupby(group_col).size()
        label = "number of companies"
    elif operation == "average":
        series = df.groupby(group_col)[metric].mean()
        label = f"average {METRIC_LABELS[metric]}"
    else:
        series = df.groupby(group_col)[metric].sum()
        label = f"total {METRIC_LABELS[metric]}"
    series = series.sort_values(ascending=ascending)
    steps.append(f"Grouped the {len(df)} companies by **{group_col}** and "
                 f"calculated the {label} for each group.")
    steps.append(f"Sorted the {len(series)} groups from "
                 f"{'lowest to highest' if ascending else 'highest to lowest'}.")

    winner, value = series.index[0], series.iloc[0]
    if group_col == "State":  # show "California" instead of the short code "CA"
        code_to_name = {code: name.title() for name, code in STATE_NAMES.items()}
        winner = code_to_name.get(winner, winner)
    formatted = f"{value:,.0f}" if operation == "count" else fmt_value(metric, value)
    direction = "lowest" if ascending else ("most" if operation == "count" else "highest")
    text = (f"**{winner}** has the {direction} "
            f"{label.replace('number of companies', 'companies')}{scope}: "
            f"**{formatted}**.")

    show = series.head(15)
    if len(series) > 15:
        steps.append(f"Showing the top 15 of {len(series)} groups in the chart.")
    table = show.reset_index()
    table.columns = [group_col, label.title()]
    if operation != "count":
        table[label.title()] = table[label.title()].map(lambda v: fmt_value(metric, v))
    scaled, suffix = scale_for_chart(show, metric)
    chart = scaled.to_frame(name=label.title() + suffix)
    return Answer(text, steps, table=table, chart=chart, kind="group")


def top_answer(df, metric, n, ascending, scope, steps):
    data = df.dropna(subset=[metric])
    single = n is None
    n = n or 1
    result = data.nsmallest(n, metric) if ascending else data.nlargest(n, metric)
    word = "lowest" if ascending else "highest"
    steps.append(f"Sorted {len(data)} companies by **{metric}** "
                 f"({'lowest to highest' if ascending else 'highest to lowest'}) "
                 f"and took the top {n}.")
    if single:
        row = result.iloc[0]
        text = (f"**{row['Name']} ({row['Symbol']})** has the {word} "
                f"{METRIC_LABELS[metric]}{scope}: **{fmt_value(metric, row[metric])}**.")
        context = data.nsmallest(5, metric) if ascending else data.nlargest(5, metric)
        steps.append("Included the top 5 in the table so you can see the runners-up.")
    else:
        text = f"Here are the {n} companies with the {word} {METRIC_LABELS[metric]}{scope}:"
        context = result
    scaled, suffix = scale_for_chart(context.set_index("Symbol")[metric], metric)
    chart = scaled.to_frame(name=METRIC_LABELS[metric].title() + suffix)
    return Answer(text, steps, table=make_table(context, metric), chart=chart, kind="top")


def listing_answer(df, metric, scope, steps):
    sort_col = metric or "MarketCap"
    result = df.sort_values(sort_col, ascending=False)
    steps.append(f"Listed the matching companies, sorted by **{sort_col}**.")
    text = f"Found **{len(df)} companies**{scope}, sorted by {METRIC_LABELS[sort_col]}:"
    return Answer(text, steps, table=make_table(result.head(50), metric), kind="listing")


# ---------------------------------------------------------------------------
# 7. The main function. This is the one the app calls for each question.
# ---------------------------------------------------------------------------

def answer_question(question, companies, index_df):
    """Take one question in normal English and turn it into an Answer."""
    q = question.lower().strip()
    steps = []

    # --- Step A: is the question about the index over time? ---
    if any(word in q for word in TREND_WORDS):
        return trend_answer(index_df, steps)

    # --- Step B: which action words and number words are in the question? ---
    metric, metric_word = find_metric(q)
    if metric:
        steps.append(f"Matched \"{metric_word}\" to the **{metric}** column.")
    ascending = any(word_match(q, w) for w in ASCENDING_WORDS)
    descending = any(word_match(q, w) for w in DESCENDING_WORDS)
    wants_average = any(w in q for w in AVERAGE_WORDS)
    wants_total = any(w in q for w in TOTAL_WORDS)
    wants_count = any(word_match(q, w) for w in COUNT_WORDS)
    top_n = find_top_n(q)

    # --- Step C: is the question about one certain company? ---
    row, how = find_company(question, q, companies, descending or ascending)
    if row is not None:
        steps.insert(0, how)
        return company_answer(row, metric, steps)

    # --- Step D: cut the table down with any filters (sector, state, ...) ---
    df, used_columns, filter_text = apply_filters(q, companies, steps)
    scope = f" in {filter_text}" if filter_text else ""
    if df.empty:
        return Answer("No companies match those filters.", steps, kind="empty")

    # --- Step E: pick which kind of answer to make ---
    group_col = find_group(q, exclude=used_columns)
    if group_col:
        steps.append(f"The question asks about each **{group_col}**, "
                     "so I'll group the companies.")
        if metric and (wants_average or wants_total or descending or ascending):
            operation = "average" if wants_average else "total"
            return group_answer(df, group_col, metric, operation, ascending, scope, steps)
        if wants_count or descending or ascending:
            return group_answer(df, group_col, None, "count", ascending, scope, steps)

    if wants_count:
        steps.append(f"Counted the rows that matched: **{len(df)}**.")
        text = f"**{len(df)} companies**{scope} (out of {len(companies)} in the S&P 500)."
        table = make_table(df.sort_values("MarketCap", ascending=False).head(50), metric)
        return Answer(text, steps, table=table, kind="count")

    if (wants_average or wants_total) and metric:
        values = df[metric].dropna()
        result = values.mean() if wants_average else values.sum()
        op_word = "average" if wants_average else "total"
        steps.append(f"Calculated the {op_word} of **{metric}** across "
                     f"{len(values)} companies.")
        text = (f"The {op_word} {METRIC_LABELS[metric]}{scope} is "
                f"**{fmt_value(metric, result)}** (based on {len(values)} companies).")
        return Answer(text, steps, kind="aggregate")

    if descending or ascending or top_n:
        if not metric:
            metric = "MarketCap"
            steps.append("No specific number was named - defaulting to "
                         "**MarketCap**, the usual measure of company size.")
        return top_answer(df, metric, top_n, ascending, scope, steps)

    if used_columns:
        return listing_answer(df, metric, scope, steps)

    # --- Fallback: nothing matched, so we give up in a nice way ---
    steps.append("I scanned the question for keywords about price, market cap, "
                 "growth, employees, sectors, states and companies - none matched.")
    text = "Try only using a sample question for now"
    return Answer(text, steps, kind="fallback")
