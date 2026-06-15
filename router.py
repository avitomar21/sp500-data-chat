"""
router.py - decides which engine should answer a question.

The app now has THREE ways to answer, tried in this order:

  1. history.py   - "company over time" questions, like "how did Apple's stock
                    change from 2020 to 2021?". Only fires when the question
                    contains BOTH a specific company AND a 4-digit year, which
                    is a combination the other engines can't handle anyway.
  2. qa_engine.py - the structured keyword/pandas engine (price, market cap,
                    sectors, counts, the overall index trend...). Unchanged.
  3. retrieval.py - BM25 text search over the company descriptions, used only
                    when the keyword engine says it doesn't understand.

WHY THIS ORDER
--------------
The history check runs first because its trigger is very specific (company +
year). If it ran after the keyword engine, a question like "how did Apple
change from 2020 to 2021" would never reach it - the keyword engine recognizes
"Apple" and would answer with today's company profile instead. Checking the
most specific pattern first avoids that. When the question has no year or no
company, try_history_answer returns None and everything behaves exactly as it
did before, so paths 2 and 3 are completely unaffected.

Note the difference between the two "over time" features:
  - "How has the S&P 500 index changed over time?" has NO company in it, so it
    skips the history path and the keyword engine answers it with the overall
    index file (the existing trend answer).
  - "How did AAPL change from 2020 to 2021?" names a company and a year, so it
    takes the new history path, which uses the per-company daily price file.
"""

from history import try_history_answer
from qa_engine import answer_question


def route_and_answer(question, companies, index_df, search, history):
    """Pick the right engine for this question and return its Answer."""
    # 1. Most specific first: a company + a year means "company over time".
    #    Returns None when the question doesn't have both.
    over_time = try_history_answer(question, companies, history)
    if over_time is not None:
        return over_time

    # 2. The structured keyword/pandas engine (works exactly as before).
    structured = answer_question(question, companies, index_df)
    if structured.kind != "fallback":
        return structured

    # 3. The keyword engine didn't understand it, so treat it as an open-ended
    #    description question and search the company summaries with BM25.
    return search.answer(question)
