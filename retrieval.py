"""
retrieval.py - text search over the company business descriptions (BM25).

WHY THIS EXISTS
---------------
The keyword engine in qa_engine.py can only answer questions about the
*columns* it knows (price, market cap, sector, ...). But every company row
also has a free-text "Summary" describing what the company actually does.
A question like "which companies work on electric vehicles?" can't be answered
by filtering a column - there is no "electric vehicle" column. So instead we
SEARCH the summary text, the same way a search engine ranks pages by relevance.

We use BM25, a classic, well-known ranking formula. It is pure math - there is
no AI and no API key involved.

HOW BM25 RANKS (the short version)
----------------------------------
For a search like "electric vehicles", BM25 gives every company's summary a
relevance score using three ideas:
  1. Term frequency - a summary that mentions "electric" and "vehicle" more
     times is more relevant (but with diminishing returns, so 10 mentions is
     not 10x better than 1).
  2. Rarity (inverse document frequency) - a word found in only a few summaries
     (like "vehicle") is more informative than a word in almost every summary
     (like "services"), so matches on rare words count for more.
  3. Length - it adjusts for summary length so a very long description does not
     score high just for being long.
The company with the highest total score is the best match.
"""

import re

import pandas as pd
from rank_bm25 import BM25Okapi

from qa_engine import Answer  # reuse the same answer container the app renders


# Very common words that carry no topic meaning. Removing them keeps the search
# focused on the words that matter ("electric", "vehicles") instead of filler
# like "the" or "company". The SAME cleaning is applied to both the company
# summaries and the user's question so they are compared fairly.
STOPWORDS = {
    "the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with",
    "is", "are", "was", "were", "be", "been", "being", "as", "at", "by",
    "from", "that", "this", "these", "those", "it", "its", "their", "they",
    "which", "what", "who", "whom", "whose", "where", "when", "how", "why",
    "do", "does", "did", "has", "have", "had", "will", "would", "can", "could",
    "company", "companies", "corporation", "inc", "business", "businesses",
    "work", "works", "working", "involved", "make", "makes", "making", "made",
    "provide", "provides", "providing", "offer", "offers", "operate",
    "operates", "based", "headquartered", "founded", "include", "including",
    "also", "well", "various", "addition", "products", "services", "me",
    "show", "list", "find", "any", "some", "all", "about", "into",
}


def tokenize(text):
    """Turn a piece of text into a clean list of lowercase words.

    'Apple Inc. designs iPhones.' -> ['apple', 'designs', 'iphones']
    We keep only letter/number chunks, drop stopwords, and drop 1-character
    leftovers. The exact same function is used on summaries and on questions so
    they match consistently.
    """
    text = str(text).lower()
    words = re.findall(r"[a-z0-9]+", text)        # split on anything non-alphanumeric
    return [w for w in words if w not in STOPWORDS and len(w) > 1]


# A few example questions that work well with the text search, shown as buttons
# in the app next to the structured (keyword-engine) sample questions.
TEXT_SAMPLE_QUESTIONS = [
    "Which companies work on electric vehicles?",
    "What companies are involved in cloud computing?",
    "Which companies make semiconductors or chips?",
    "Show me companies in renewable or solar energy",
]


class SummarySearch:
    """A BM25 search index built over every company's Summary text."""

    def __init__(self, companies):
        # Keep a clean copy with a simple 0..N row index we can look up by.
        self.companies = companies.reset_index(drop=True)

        # Tokenize every summary once. This "corpus" is a list of word-lists,
        # one per company - exactly the format BM25Okapi expects.
        self.corpus_tokens = [tokenize(s) for s in self.companies["Summary"]]

        # Building the index makes BM25 read the whole corpus once and work out
        # how common or rare each word is, so it can score relevance instantly.
        self.bm25 = BM25Okapi(self.corpus_tokens)

    def rank(self, question, k=5):
        """Return (query_words, [(row, score), ...]) for the top-k companies."""
        query_words = tokenize(question)
        # get_scores returns ONE relevance score per company (502 numbers).
        scores = self.bm25.get_scores(query_words)
        # Sort companies by score, highest first, and take the top k.
        top_indexes = scores.argsort()[::-1][:k]
        ranked = [(self.companies.iloc[i], float(scores[i])) for i in top_indexes]
        return query_words, ranked

    def answer(self, question, k=5):
        """Run the search and package it as an Answer the app can render."""
        steps = ["This looked like an open-ended description question, so I "
                 "searched the company summaries with BM25 instead of using the "
                 "keyword engine."]

        query_words = tokenize(question)
        steps.append(f"Cleaned your question down to the search words: "
                     f"**{', '.join(query_words) or '(none)'}**.")
        if not query_words:
            return Answer("Please use a few describing words, like 'electric "
                          "vehicles' or 'cloud computing'.", steps, kind="text_empty")

        query_words, ranked = self.rank(question, k)
        steps.append(f"BM25 scored all {len(self.companies)} company summaries for "
                     "those words and ranked them by relevance.")

        # If even the best score is 0, no summary contained any of the words.
        if ranked[0][1] <= 0:
            steps.append("No summary contained those words.")
            return Answer(f"I couldn't find any company descriptions matching "
                          f"**{', '.join(query_words)}**. Try different words.",
                          steps, kind="text_empty")

        # Keep only the matches that actually scored above 0.
        hits = [(row, score) for row, score in ranked if score > 0]

        # The worded answer: name the top matches.
        names = [f"**{row['Name']} ({row['Symbol']})**" for row, _ in hits]
        text = (f"Here are the companies whose descriptions best match "
                f"**{', '.join(query_words)}**:\n\n" + ", ".join(names) + ".")

        # A table of the matches with their relevance score and a short snippet.
        table = pd.DataFrame([{
            "Symbol": row["Symbol"],
            "Name": row["Name"],
            "Sector": row["Sector"],
            "Relevance": round(score, 2),
            "What they do": str(row["Summary"]).split(". ")[0][:160] + "...",
        } for row, score in hits])

        # Show every score in the steps so the ranking stays transparent.
        for row, score in hits:
            steps.append(f"**{row['Symbol']}** scored **{score:.2f}** "
                         f"({row['Name']}).")

        chart = table.set_index("Symbol")[["Relevance"]]
        return Answer(text, steps, table=table, chart=chart, kind="text")
