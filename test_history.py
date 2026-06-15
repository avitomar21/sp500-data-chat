"""
test_history.py - checks for the company-over-time price feature.

Run with:  python test_history.py

It confirms that:
  1. The change calculation gives the right numbers for a known case.
  2. The edge cases answer sensibly (no history, years outside the data).
  3. The router sends each kind of question to the right engine.
"""

from history import load_history, try_history_answer
from qa_engine import load_data
from retrieval import SummarySearch
from router import route_and_answer

companies, index_df = load_data()
history = load_history()
search = SummarySearch(companies)

# 1. A known case: Apple from the first trading day of 2020 ($72.40 on
#    Jan 2 2020) to the last trading day of 2021 ($173.76 on Dec 31 2021).
a = try_history_answer("How did Apple's stock change from 2020 to 2021?",
                       companies, history)
print("Apple 2020->2021:", a.text[:120])
assert a.kind == "history"
assert "$72.40" in a.text and "$173.76" in a.text and "+140.0%" in a.text
assert a.chart is not None and a.chart_kind == "line"

# 2a. A company that is in the snapshot but NOT in the history file.
b = try_history_answer("How did BRK-B change from 2020 to 2024?", companies, history)
print("BRK-B (no history):", b.text[:80])
assert b.kind == "history_empty"

# 2b. Years entirely outside the data (history starts in 2000).
c = try_history_answer("How did Apple change from 1990 to 1995?", companies, history)
print("Outside range:", c.text[:80])
assert c.kind == "history_empty"

# 2c. A question with a year but NO company should NOT take the history path.
d = try_history_answer("Which companies did well in 2020?", companies, history)
assert d is None, "history path wrongly grabbed a question with no company"

# 3. Routing: each question type goes to its own engine.
CASES = {
    "How did Apple's stock change from 2020 to 2021?": "history",
    "Which company has the highest market cap?": "top",
    "How has the S&P 500 index changed over time?": "trend",
    "Tell me about NVDA": "company",
    "Which companies work on electric vehicles?": "text",
}
for question, expected in CASES.items():
    kind = route_and_answer(question, companies, index_df, search, history).kind
    print(f"[{'OK' if kind == expected else 'FAIL'}] {question} -> {kind}")
    assert kind == expected, f"'{question}' routed to {kind}, expected {expected}"

print("\nAll history + routing checks passed.")
