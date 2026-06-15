"""
app.py - this builds the screen you see (the user interface).

How the page is laid out:
  - Title at the top
  - Left side:  the data table with a sector filter and sorting
  - Right side: the question box and the answer
  - Bottom:     sample questions you can click

Run it with:  python -m streamlit run app.py
"""

import streamlit as st

from history import HISTORY_SAMPLE_QUESTIONS, load_history
from qa_engine import SAMPLE_QUESTIONS, load_data
from retrieval import SummarySearch, TEXT_SAMPLE_QUESTIONS
from router import route_and_answer

st.set_page_config(page_title="S&P 500 Data Chat", layout="wide")


RETRO_CSS = """
<style>
.stApp :where(*:not([data-testid="stIconMaterial"])) {
    font-family: Verdana, Geneva, Tahoma, sans-serif !important;
}
.stApp h1, .stApp h2, .stApp h3,
.stApp h1 span, .stApp h2 span, .stApp h3 span {
    font-family: Georgia, "Times New Roman", serif !important;
}
h1 { border-bottom: 3px double #5B82B8; padding-bottom: 8px; }
h3 { border-bottom: 1px solid #2E4D73; padding-bottom: 4px; }

/* make every corner square and turn off the soft shadows */
* { border-radius: 0 !important; box-shadow: none !important; }

/* old style buttons that fade from light to dark */
.stButton > button {
    background: linear-gradient(to bottom, #1D3354 0%, #122440 100%);
    border: 1px solid #3A5A82;
    color: #E8E6E0;
    box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08) !important;
}
.stButton > button:hover {
    background: linear-gradient(to bottom, #264066 0%, #182E4F 100%);
    border-color: #5B82B8;
    color: #FFFFFF;
}
.stButton > button:active {
    background: #182E4F;
    box-shadow: inset 0 2px 3px rgba(0, 0, 0, 0.5) !important;
}

/* the text box and dropdowns, made to look like boxes pushed in */
.stTextInput [data-baseweb="input"] {
    background-color: #0D1C30 !important;
    border: 1px solid #3A5A82 !important;
    box-shadow: inset 1px 1px 3px rgba(0, 0, 0, 0.45) !important;
}
.stTextInput input { background-color: transparent !important; }
[data-baseweb="select"] > div {
    background-color: #0D1C30 !important;
    border-color: #3A5A82 !important;
}

/* draw a border around the expander and the table */
[data-testid="stExpander"] details { border: 1px solid #3A5A82 !important; }
[data-testid="stDataFrame"] { border: 1px solid #3A5A82; }

hr { border: none; border-top: 1px solid #3A5A82; }
</style>
"""
st.markdown(RETRO_CSS, unsafe_allow_html=True)


@st.cache_data
def get_data():
    return load_data()


@st.cache_data
def get_history():
    # The daily price history (2.7 million rows) is loaded once and cached,
    # so asking questions stays fast.
    return load_history()


companies, index_df = get_data()


@st.cache_resource
def get_search(_companies):
    # Build the BM25 text index once and reuse it. cache_resource (not
    # cache_data) is used because a search index is a live object rather than a
    # simple value. The leading underscore on _companies tells Streamlit not to
    # try to hash the whole DataFrame.
    return SummarySearch(_companies)


search = get_search(companies)
history = get_history()

st.title("Chat with the S&P 500", anchor=False)

left, right = st.columns(2, gap="large")

# ---------------------------------------------------------------------------
# Left side: the data table with simple filtering and sorting
# ---------------------------------------------------------------------------

SORT_OPTIONS = {
    "Market cap": "MarketCap",
    "Price": "Price",
    "Revenue growth": "RevenueGrowth",
    "Name": "Name",
}

with left:
    st.subheader("The dataset", anchor=False)
    c1, c2, c3 = st.columns(3)
    sector = c1.selectbox("Filter by sector",
                          ["All sectors"] + sorted(companies["Sector"].unique()))
    sort_label = c2.selectbox("Sort by", list(SORT_OPTIONS))
    order = c3.selectbox("Order", ["High to low", "Low to high"])

    view = companies if sector == "All sectors" else companies[companies["Sector"] == sector]
    view = view.sort_values(SORT_OPTIONS[sort_label],
                            ascending=(order == "Low to high"))

    # These are the 7 columns we put in the table. (The brain uses a few
    # more, like Employees and State, when it answers questions.)
    table = view[["Symbol", "Name", "Sector", "Industry", "Price",
                  "MarketCap", "RevenueGrowth"]].copy()
    table["MarketCap"] = (table["MarketCap"] / 1e9).round(2)
    table["RevenueGrowth"] = (table["RevenueGrowth"] * 100).round(1)
    table = table.rename(columns={"MarketCap": "Market cap ($B)",
                                  "RevenueGrowth": "Revenue growth (%)"})
    st.dataframe(
        table, hide_index=True, height=420,
        column_config={"Price": st.column_config.NumberColumn(format="$%.2f")})
    st.caption(f"{len(view)} companies shown")

# ---------------------------------------------------------------------------
# Right side: ask a question and read the answer
# ---------------------------------------------------------------------------

with right:
    st.subheader("Ask a question", anchor=False)
    question = st.text_input(
        "Your question", key="question_box",
        placeholder="e.g. Which company has the highest market cap?")

    if question:
        answer = route_and_answer(question, companies, index_df, search, history)
        st.markdown(answer.text)
        if answer.chart is not None:
            if answer.chart_kind == "line":
                st.line_chart(answer.chart)
            else:
                st.bar_chart(answer.chart)
        if answer.table is not None:
            st.dataframe(answer.table, hide_index=True)
        with st.expander("How the app found this answer"):
            for number, step in enumerate(answer.steps, start=1):
                st.markdown(f"**{number}.** {step}")

# ---------------------------------------------------------------------------
# Bottom: the sample question buttons
# ---------------------------------------------------------------------------


def use_sample(sample):
    st.session_state.question_box = sample


st.divider()
st.subheader("Sample Questions", anchor=False)
# Structured questions go to the keyword engine, the "over the years" ones to
# the price-history feature, and the topic ones to the BM25 text search.
all_samples = SAMPLE_QUESTIONS + HISTORY_SAMPLE_QUESTIONS + TEXT_SAMPLE_QUESTIONS
columns = st.columns(2)
for i, sample in enumerate(all_samples):
    columns[i % 2].button(sample, on_click=use_sample, args=(sample,),
                          width="stretch")
