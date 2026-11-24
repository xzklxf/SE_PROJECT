"""Visualization module: load saved expenses and draw a pie chart by category."""
import csv
import json
import os
import sys
from collections import defaultdict

import matplotlib.pyplot as plt

DEFAULT_FILE = "expenses.csv"


def load_expenses(path):
    """Load expense records from a CSV or JSON file.

    Each record needs at least 'date', 'amount' and 'category'.
    """
    if not os.path.exists(path):
        sys.exit(f"Error: data file '{path}' not found. Add some expenses first.")

    if path.lower().endswith(".json"):
        with open(path, encoding="utf-8") as f:
            records = json.load(f)
    else:
        with open(path, newline="", encoding="utf-8-sig") as f:
            records = list(csv.DictReader(f))

    expenses = []
    for i, row in enumerate(records, start=1):
        row = {str(k).strip().lower(): v for k, v in row.items()}
        try:
            amount = float(row["amount"])
        except (KeyError, TypeError, ValueError):
            print(f"Warning: skipping record {i}, invalid amount: {row}", file=sys.stderr)
            continue
        if amount <= 0:
            print(f"Warning: skipping record {i}, amount must be positive", file=sys.stderr)
            continue
        category = str(row.get("category") or "Uncategorized").strip()
        expenses.append({
            "date": str(row.get("date", "")).strip(),
            "amount": amount,
            "category": category,
        })
    return expenses


def summarize_by_category(expenses):
    """Return {category: total amount}, sorted from largest to smallest."""
    totals = defaultdict(float)
    for e in expenses:
        totals[e["category"]] += e["amount"]
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))


def draw_pie_chart(totals):
    """Draw a basic pie chart of category totals."""
    if not totals:
        sys.exit("No expenses to plot.")
    plt.pie(list(totals.values()), labels=list(totals.keys()), autopct="%1.1f%%", startangle=90)
    plt.title("Expenses by Category")
    plt.axis("equal")
    plt.show()


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_FILE
    totals = summarize_by_category(load_expenses(path))
    print("Category totals:")
    for cat, amt in totals.items():
        print(f"  {cat:<15} {amt:>10,.2f}")
    draw_pie_chart(totals)


if __name__ == "__main__":
    main()
