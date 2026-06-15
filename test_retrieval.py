"""
test_retrieval.py - quick checks for the BM25 text search and the router.

Run with:  python test_retrieval.py

It confirms that:
  1. BM25 surfaces sensible companies for topic questions.
  2. The router sends structured questions to the keyword engine and
     open-ended description questions to the text search.
"""

from history import load_history
from qa_engine import load_data
from retrieval import SummarySearch
from router import route_and_answer

companies, index_df = load_data()
search = SummarySearch(companies)
history = load_history()

# 1. BM25 relevance. Each topic should put an obviously-related company on top.
#    (key = query, value = a ticker we expect to appear in the top 5)
EXPECT = {
    "electric vehicles": "TSLA",          # Tesla
    "cloud computing": "MSFT",            # Microsoft / others
    "semiconductors or chips": "INTC",     # Intel
}
for query, expected_symbol in EXPECT.items():
    words, ranked = search.rank(query, k=5)
    symbols = [row["Symbol"] for row, score in ranked]
    print(f"[{query}] -> {[(s, round(sc, 1)) for (r, sc), s in zip(ranked, symbols)]}")
    assert ranked[0][1] > 0, f"BM25 found nothing for '{query}'"
    assert expected_symbol in symbols, f"expected {expected_symbol} for '{query}'"

# 2. Routing. Structured questions stay structured; topic questions go to text.
structured = route_and_answer("Which company has the highest market cap?",
                              companies, index_df, search, history)
textual = route_and_answer("Which companies work on electric vehicles?",
                           companies, index_df, search, history)
print(f"\nstructured question -> kind '{structured.kind}'")
print(f"text question       -> kind '{textual.kind}'")
assert structured.kind != "text", "structured question was wrongly sent to text search"
assert textual.kind == "text", "text question was not sent to text search"

print("\nAll retrieval + routing checks passed.")
