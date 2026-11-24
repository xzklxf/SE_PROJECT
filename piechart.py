"""Visualization module: load saved expenses and draw a pie chart by category.

Usage:
    python piechart.py                       # read expenses.csv, show chart
    python piechart.py -f data.json          # read a JSON file instead
    python piechart.py -o chart.png          # save to file instead of showing
    python piechart.py --month 2026-11       # only include one month
    python piechart.py --theme light         # light theme instead of dark
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
from matplotlib.patches import FancyBboxPatch

DEFAULT_FILE = "expenses.csv"
MAX_SLICES = 7  # smaller categories are grouped into "Other"

# Latin font first, then CJK fonts so Chinese category names also render.
FONT_CANDIDATES = [
    "Segoe UI", "Helvetica Neue", "Inter", "Arial",
    "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "Noto Sans CJK JP",
    "WenQuanYi Zen Hei", "Arial Unicode MS",
]

THEMES = {
    "dark": {
        "bg": "#0E1117",
        "card": "#161B24",
        "track": "#232A36",
        "text": "#F2F4F8",
        "muted": "#8B94A7",
        "palette": ["#7C9CFF", "#5EE6C8", "#FFB86B", "#FF7A9A",
                    "#B69CFF", "#62C6FF", "#E5D27A", "#6B7385"],
    },
    "light": {
        "bg": "#F6F5F1",
        "card": "#FFFFFF",
        "track": "#ECEAE4",
        "text": "#1C1F26",
        "muted": "#80838C",
        "palette": ["#3D5A98", "#2A9D8F", "#E9A23B", "#D1495B",
                    "#7B6CB5", "#3A8FC9", "#B8A03A", "#A4A7AE"],
    },
}


def setup_font():
    """Use the nicest installed fonts; CJK fonts act as fallback for Chinese."""
    installed = {f.name for f in font_manager.fontManager.ttflist}
    fonts = [name for name in FONT_CANDIDATES if name in installed]
    if fonts:
        matplotlib.rcParams["font.family"] = fonts
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


def filter_by_month(expenses, month=None):
    """Keep only expenses whose date starts with `month` (e.g. '2026-11')."""
    if not month:
        return expenses
    return [e for e in expenses if e["date"].startswith(month)]


def summarize_by_category(expenses):
    """Return {category: total amount}, sorted from largest to smallest."""
    totals = defaultdict(float)
    for e in expenses:
        totals[e["category"]] += e["amount"]
    return dict(sorted(totals.items(), key=lambda kv: kv[1], reverse=True))


def group_small_categories(totals, max_slices=MAX_SLICES):
    """Merge everything beyond the top `max_slices - 1` categories into 'Other'."""
    items = list(totals.items())
    if len(items) <= max_slices:
        return totals
    top = dict(items[:max_slices - 1])
    top["Other"] = sum(v for _, v in items[max_slices - 1:])
    return top


def date_range_text(expenses):
    dates = sorted(e["date"] for e in expenses if e["date"])
    if not dates:
        return ""
    return dates[0] if dates[0] == dates[-1] else f"{dates[0]}  –  {dates[-1]}"


def draw_pie_chart(totals, expenses, title="Expenses by Category",
                   output=None, theme="dark"):
    """Draw a dashboard-style donut chart with a ranked breakdown panel."""
    if not totals:
        sys.exit("No expenses to plot.")

    setup_font()
    t = THEMES[theme]
    totals = group_small_categories(totals)
    labels = list(totals.keys())
    values = list(totals.values())
    grand_total = sum(values)
    colors = [t["palette"][i % len(t["palette"])] for i in range(len(values))]

    fig = plt.figure(figsize=(12, 6.75), facecolor=t["bg"])
    if fig.canvas.manager is not None:
        fig.canvas.manager.set_window_title("Expense Tracker")

    # ---- Header -------------------------------------------------------
    fig.text(0.05, 0.90, title, fontsize=22, fontweight="bold", color=t["text"])
    subtitle = date_range_text(expenses)
    fig.text(0.05, 0.855, f"{subtitle}   ·   {len(expenses)} transactions",
             fontsize=11, color=t["muted"])

    # ---- Donut (left) -------------------------------------------------
    ax = fig.add_axes([0.03, 0.06, 0.46, 0.74])
    ax.set_facecolor(t["bg"])
    ax.pie(
        values,
        colors=colors,
        startangle=90,
        counterclock=False,
        wedgeprops={"width": 0.16, "edgecolor": t["bg"], "linewidth": 4},
    )
    ax.text(0, 0.17, "TOTAL SPENDING", ha="center", va="center",
            fontsize=10, color=t["muted"], fontweight="bold")
    ax.text(0, -0.02, f"${grand_total:,.0f}", ha="center", va="center",
            fontsize=34, fontweight="bold", color=t["text"])
    ax.text(0, -0.22, f"{len(labels)} categories", ha="center", va="center",
            fontsize=10, color=t["muted"])
    ax.set_aspect("equal")

    # ---- Breakdown card (right) ---------------------------------------
    card = fig.add_axes([0.53, 0.08, 0.42, 0.70])
    card.set_xlim(0, 1)
    card.set_ylim(0, 1)
    card.axis("off")
    card.add_patch(FancyBboxPatch(
        (0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.04",
        facecolor=t["card"], edgecolor="none", transform=card.transAxes,
    ))
    card.text(0.07, 0.91, "Breakdown", fontsize=14, fontweight="bold", color=t["text"])
    card.text(0.93, 0.91, "Amount", fontsize=10, color=t["muted"], ha="right")

    top, bottom = 0.80, 0.07
    step = min(0.12, (top - bottom) / len(labels))
    bar_x, bar_w = 0.07, 0.86
    for i, (label, value, color) in enumerate(zip(labels, values, colors)):
        y = top - i * step
        share = value / grand_total
        card.scatter(bar_x + 0.012, y, s=60, color=color, zorder=3)
        card.text(bar_x + 0.045, y, label, fontsize=11.5, color=t["text"], va="center")
        card.text(0.93, y, f"${value:,.0f}", fontsize=11.5, color=t["text"],
                  ha="right", va="center", fontweight="bold")
        card.text(0.74, y, f"{share:.1%}", fontsize=10, color=t["muted"],
                  ha="right", va="center")
        bar_y = y - step * 0.38
        card.add_patch(FancyBboxPatch(
            (bar_x, bar_y), bar_w, 0.012, boxstyle="round,pad=0,rounding_size=0.006",
            facecolor=t["track"], edgecolor="none"))
        card.add_patch(FancyBboxPatch(
            (bar_x, bar_y), max(bar_w * share, 0.012), 0.012,
            boxstyle="round,pad=0,rounding_size=0.006",
            facecolor=color, edgecolor="none"))

    if output:
        plt.savefig(output, dpi=160, facecolor=t["bg"])
        print(f"Pie chart saved to {output}")
    else:
        plt.show()


def main():
    parser = argparse.ArgumentParser(description="Draw a pie chart of expenses by category.")
    parser.add_argument("-f", "--file", default=DEFAULT_FILE, help="CSV or JSON data file")
    parser.add_argument("-o", "--output", help="save chart to this image file instead of showing it")
    parser.add_argument("--month", help="only include expenses in this month, e.g. 2026-11")
    parser.add_argument("--theme", choices=THEMES.keys(), default="dark", help="color theme")
    args = parser.parse_args()

    expenses = filter_by_month(load_expenses(args.file), args.month)
    totals = summarize_by_category(expenses)

    print("Category totals:")
    for cat, amt in totals.items():
        print(f"  {cat:<15} {amt:>10,.2f}")

    title = f"Expenses by Category · {args.month}" if args.month else "Expenses by Category"
    draw_pie_chart(totals, expenses, title=title, output=args.output, theme=args.theme)


if __name__ == "__main__":
    main()
