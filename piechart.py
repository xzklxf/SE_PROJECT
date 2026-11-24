"""Visualization module: load saved expenses and draw a pie chart by category.

Usage:
    python piechart.py                       # read expenses.csv, show chart
    python piechart.py -f data.json          # read a JSON file instead
    python piechart.py -o chart.png          # save to file instead of showing
    python piechart.py --month 2026-11       # only include one month
"""
import argparse
import csv
import json
import os
import sys
from collections import defaultdict

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager

DEFAULT_FILE = "expenses.csv"

# Fonts that can display Chinese category names (Windows / macOS / Linux).
CJK_FONTS = [
    "Microsoft JhengHei", "Microsoft YaHei", "PingFang TC", "Heiti TC",
    "Noto Sans CJK TC", "Noto Sans CJK JP", "WenQuanYi Zen Hei", "Arial Unicode MS",
]


def setup_font():
    """Use a CJK-capable font if one is installed, so Chinese labels render."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    for name in CJK_FONTS:
        if name in installed:
            matplotlib.rcParams["font.sans-serif"] = [name] + matplotlib.rcParams["font.sans-serif"]
            break
    matplotlib.rcParams["axes.unicode_minus"] = False


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


def summarize_by_category(expenses, month=None):
    """Return {category: total amount}, sorted from largest to smallest."""
    totals = defaultdict(float)
    for e in expenses:
        if month and not e["date"].startswith(month):
            continue
        totals[e["category"]] += e["amount"]
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))


def draw_pie_chart(totals, title="Expenses by Category", output=None):
    """Draw the pie chart; save to `output` if given, otherwise show a window."""
    if not totals:
        sys.exit("No expenses to plot.")

    setup_font()
    labels = list(totals.keys())
    values = list(totals.values())
    grand_total = sum(values)

    fig, ax = plt.subplots(figsize=(8, 6))
    wedges, _, autotexts = ax.pie(
        values,
        autopct=lambda p: f"{p:.1f}%" if p >= 3 else "",
        startangle=90,
        counterclock=False,
        pctdistance=0.75,
        wedgeprops={"edgecolor": "white", "linewidth": 1.5},
    )
    for t in autotexts:
        t.set_color("white")
        t.set_fontweight("bold")

    ax.legend(
        wedges,
        [f"{c}  ${v:,.0f}" for c, v in totals.items()],
        title="Category",
        loc="center left",
        bbox_to_anchor=(1, 0.5),
        frameon=False,
    )
    ax.set_title(f"{title}\nTotal: ${grand_total:,.0f}", fontsize=14)
    ax.axis("equal")
    plt.tight_layout()

    if output:
        plt.savefig(output, dpi=150, bbox_inches="tight")
        print(f"Pie chart saved to {output}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Draw a pie chart of expenses by category.")
    parser.add_argument("-f", "--file", default=DEFAULT_FILE, help="CSV or JSON data file")
    parser.add_argument("-o", "--output", help="save chart to this image file instead of showing it")
    parser.add_argument("--month", help="only include expenses in this month, e.g. 2026-11")
    args = parser.parse_args()

    expenses = load_expenses(args.file)
    totals = summarize_by_category(expenses, args.month)

    print("Category totals:")
    for cat, amt in totals.items():
        print(f"  {cat:<15} {amt:>10,.2f}")

    title = f"Expenses by Category ({args.month})" if args.month else "Expenses by Category"
    draw_pie_chart(totals, title=title, output=args.output)


if __name__ == "__main__":
    main()
