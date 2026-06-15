"""
test_engine.py - a quick check to make sure the question engine still works.

It runs every sample question (and a few extra ones) through
answer_question() and complains if one of them fails when it should not.

Run with:  python test_engine.py
"""

from qa_engine import SAMPLE_QUESTIONS, answer_question, load_data

EXTRA_QUESTIONS = [
    "What is the price of Apple?",
    "How many employees does Microsoft have?",
    "Top 10 cheapest stocks",
    "Which state has the most companies?",
    "Show me healthcare companies",
    "Which company has the lowest revenue growth?",
    "What is the total market cap of the Energy sector?",
    # extra phrasings, to make sure the new keywords are recognized
    "Which company is the most valuable?",
    "What is the average headcount in the Technology sector?",
    "Show me the biggest banks",
    "List telecom companies",
    "Which company has the largest workforce?",
    "oil and gas companies",
    "banana banana banana",          # this one is junk, so it SHOULD fail on purpose
]

companies, index_df = load_data()
failures = []

for question in SAMPLE_QUESTIONS + EXTRA_QUESTIONS:
    answer = answer_question(question, companies, index_df)
    expected_fallback = question == "banana banana banana"
    ok = (answer.kind == "fallback") == expected_fallback
    status = "OK  " if ok else "FAIL"
    if not ok:
        failures.append(question)
    first_line = answer.text.splitlines()[0]
    print(f"[{status}] ({answer.kind:9}) {question}")
    print(f"        -> {first_line[:100]}")

print()
if failures:
    raise SystemExit(f"FAILED: {len(failures)} question(s) not handled: {failures}")
print(f"All {len(SAMPLE_QUESTIONS + EXTRA_QUESTIONS)} questions behaved as expected.")
