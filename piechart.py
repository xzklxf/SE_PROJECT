"""Visualization module: load saved expenses and draw a pie chart by category.

Usage:
    python piechart.py                       # read expenses.csv, show chart
    python piechart.py -f data.json          # read a JSON file instead
    python piechart.py -o chart.png          # save to file instead of showing
    python piechart.py --month 2026-11       # only include one month
    python piechart.py --theme light         # light theme instead of dark
    python piechart.py --currency "$"        # change currency symbol (default NT$)
    python piechart.py --no-animation        # skip the opening animation
    python piechart.py --font "Segoe UI"     # use another installed font

In the chart window, hover over a slice (or a row on the right) to see details.
"""
import argparse
import csv
import json
import logging
import math
import os
import sys
from collections import defaultdict
from datetime import datetime

import matplotlib
import matplotlib.pyplot as plt
from matplotlib import font_manager
from matplotlib.animation import FuncAnimation
from matplotlib.patches import FancyBboxPatch, Wedge

DEFAULT_FILE = "expenses.csv"
DEFAULT_CURRENCY = "NT$"
MAX_SLICES = 6            # smaller categories are grouped into "Other"
LABEL_MIN_SHARE = 0.04    # slices smaller than this get no outer label

RING_WIDTH = 0.17
HOVER_GROW = 0.07
ANIM_FRAMES = 55
ANIM_INTERVAL_MS = 16

# Fonts shipped with the project (fonts/*.ttf next to this script).
FONT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fonts")
DEFAULT_FONT = "Outfit"
# Used when the main font is missing, and for Chinese characters it can't draw.
FALLBACK_FONTS = [
    "Segoe UI", "Helvetica Neue", "Arial",
    "Microsoft JhengHei", "PingFang TC", "Noto Sans CJK TC", "Noto Sans CJK JP",
    "WenQuanYi Zen Hei", "Arial Unicode MS",
]

THEMES = {
    "dark": {
        "bg": "#0E1117", "card": "#161B24", "track": "#2C3545", "hover": "#1F2633",
        "text": "#F2F4F8", "muted": "#8B94A7",
        "palette": ["#7C9CFF", "#5EE6C8", "#FFB86B", "#FF7A9A",
                    "#B69CFF", "#62C6FF", "#6B7385"],
    },
    "light": {
        "bg": "#F6F5F1", "card": "#FFFFFF", "track": "#ECEAE4", "hover": "#F3F1EC",
        "text": "#1C1F26", "muted": "#80838C",
        "palette": ["#3D5A98", "#2A9D8F", "#E9A23B", "#D1495B",
                    "#7B6CB5", "#3A8FC9", "#A4A7AE"],
    },
}

DATE_FORMATS = ["%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y%m%d", "%Y-%m-%d %H:%M:%S"]


# ----------------------------------------------------------------------
# Data
# ----------------------------------------------------------------------
def normalize_date(text):
    """Turn '2026/11/1' or '20261101' into '2026-11-01'; keep unknown formats as-is."""
    text = str(text or "").strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text


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
            "date": normalize_date(row.get("date")),
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


def build_insight(totals):
    """One-sentence summary of the biggest spending category."""
    grand_total = sum(totals.values())
    ranked = [(c, v) for c, v in totals.items() if c != "Other"]
    if not ranked or grand_total == 0:
        return ""
    category, value = ranked[0]
    return f"{category} is your biggest expense — {value / grand_total:.0%} of total spending."


def date_range_text(expenses):
    dates = sorted(e["date"] for e in expenses if e["date"])
    if not dates:
        return ""
    return dates[0] if dates[0] == dates[-1] else f"{dates[0]}  –  {dates[-1]}"


# ----------------------------------------------------------------------
# Drawing helpers
# ----------------------------------------------------------------------
def setup_font(main_font=DEFAULT_FONT):
    """Register the bundled fonts and use `main_font`, with CJK fonts as fallback."""
    logging.getLogger("matplotlib.font_manager").setLevel(logging.ERROR)
    if os.path.isdir(FONT_DIR):
        for name in os.listdir(FONT_DIR):
            if name.lower().endswith((".ttf", ".otf")):
                font_manager.fontManager.addfont(os.path.join(FONT_DIR, name))
    installed = {f.name for f in font_manager.fontManager.ttflist}
    fonts = [name for name in [main_font] + FALLBACK_FONTS if name in installed]
    if fonts:
        matplotlib.rcParams["font.family"] = fonts
    matplotlib.rcParams["axes.unicode_minus"] = False


def ease_out_cubic(x):
    return 1 - (1 - x) ** 3


def add_card(fig, rect, color):
    """Create an invisible axes with a rounded background card."""
    ax = fig.add_axes(rect)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    ax.add_patch(FancyBboxPatch(
        (0, 0), 1, 1, boxstyle="round,pad=0,rounding_size=0.035",
        facecolor=color, edgecolor="none", transform=ax.transAxes, zorder=0))
    return ax


def rounded_bar(ax, x, y, w, h, color, **kw):
    return ax.add_patch(FancyBboxPatch(
        (x, y), w, h, boxstyle=f"round,pad=0,rounding_size={h / 2}",
        facecolor=color, edgecolor="none", **kw))


# ----------------------------------------------------------------------
# Main chart
# ----------------------------------------------------------------------
def draw_pie_chart(totals, expenses, title="Expenses by Category",
                   output=None, theme="dark", currency=DEFAULT_CURRENCY, animate=True,
                   font=DEFAULT_FONT):
    """Draw a dashboard-style donut chart with a ranked breakdown card."""
    if not totals:
        sys.exit("No expenses to plot.")

    setup_font(font)
    t = THEMES[theme]
    money = lambda v: f"{currency}{v:,.0f}"

    totals = group_small_categories(totals)
    labels = list(totals.keys())
    values = list(totals.values())
    grand_total = sum(values)
    shares = [v / grand_total for v in values]
    colors = [t["palette"][i % len(t["palette"])] for i in range(len(values))]
    if "Other" in labels:
        colors[labels.index("Other")] = t["palette"][-1]

    # Each slice spans [start, end] measured clockwise from 12 o'clock, in degrees.
    spans, acc = [], 0.0
    for s in shares:
        spans.append((acc * 360, (acc + s) * 360))
        acc += s

    fig = plt.figure(figsize=(13, 7.5), facecolor=t["bg"])
    if fig.canvas.manager is not None:
        fig.canvas.manager.set_window_title("Expense Tracker")

    # ---- Header -------------------------------------------------------
    fig.text(0.045, 0.915, title, fontsize=22, fontweight="bold", color=t["text"])
    fig.text(0.045, 0.875, f"{date_range_text(expenses)}   ·   {len(expenses)} transactions",
             fontsize=11, color=t["muted"])
    insight = build_insight(totals)
    if insight:
        fig.text(0.045, 0.835, "●  " + insight, fontsize=11.5, color=colors[0])

    # ---- Donut (left) -------------------------------------------------
    ax = fig.add_axes([0.02, 0.03, 0.50, 0.77])
    ax.set_xlim(-1.45, 1.45)
    ax.set_ylim(-1.45, 1.45)
    ax.set_aspect("equal")
    ax.axis("off")

    wedges = []
    for (a, b), color in zip(spans, colors):
        w = Wedge((0, 0), 1.0, 90 - b, 90 - a, width=RING_WIDTH,
                  facecolor=color, edgecolor=t["bg"], linewidth=4)
        ax.add_patch(w)
        wedges.append(w)

    center_top = ax.text(0, 0.22, "TOTAL SPENDING", ha="center", va="center",
                         fontsize=10, color=t["muted"], fontweight="bold")
    center_mid = ax.text(0, 0.0, money(grand_total), ha="center", va="center",
                         fontsize=32, fontweight="bold", color=t["text"])
    center_bot = ax.text(0, -0.24, f"{len(labels)} categories", ha="center",
                         va="center", fontsize=10, color=t["muted"])

    # Outer percentage labels with leader lines (magazine style).
    outer = []
    for (a, b), share, color in zip(spans, shares, colors):
        if share < LABEL_MIN_SHARE:
            continue
        mid = math.radians(90 - (a + b) / 2)
        cx, cy = math.cos(mid), math.sin(mid)
        x0, y0 = 1.05 * cx, 1.05 * cy
        x1, y1 = 1.18 * cx, 1.18 * cy
        x2 = x1 + (0.10 if cx >= 0 else -0.10)
        line, = ax.plot([x0, x1, x2], [y0, y1, y1], color=color, linewidth=1.2)
        text = ax.text(x2 + (0.03 if cx >= 0 else -0.03), y1, f"{share:.0%}",
                       ha="left" if cx >= 0 else "right", va="center",
                       fontsize=11, fontweight="bold", color=t["text"])
        outer += [line, text]

    # ---- Breakdown card (top right) -----------------------------------
    card = add_card(fig, [0.545, 0.08, 0.415, 0.72], t["card"])
    card.text(0.07, 0.91, "Breakdown", fontsize=14, fontweight="bold", color=t["text"])
    card.text(0.93, 0.91, "Amount", fontsize=10, color=t["muted"], ha="right")

    top, bottom = 0.78, 0.06
    step = min(0.13, (top - bottom) / len(labels))
    bar_x, bar_w, bar_h = 0.07, 0.86, 0.018
    row_bounds, row_bgs, fills = [], [], []
    for i, (label, value, share, color) in enumerate(zip(labels, values, shares, colors)):
        y = top - i * step
        bg = FancyBboxPatch((0.03, y - step * 0.62), 0.94, step * 0.92,
                            boxstyle="round,pad=0,rounding_size=0.02",
                            facecolor=t["hover"], edgecolor="none", visible=False, zorder=1)
        card.add_patch(bg)
        row_bgs.append(bg)
        row_bounds.append((y - step * 0.62, y + step * 0.30))

        card.scatter(bar_x + 0.012, y, s=55, color=color, zorder=3)
        card.text(bar_x + 0.045, y, label, fontsize=11.5, color=t["text"], va="center", zorder=3)
        card.text(0.93, y, money(value), fontsize=11.5, color=t["text"],
                  ha="right", va="center", fontweight="bold", zorder=3)
        card.text(0.72, y, f"{share:.1%}", fontsize=10, color=t["muted"],
                  ha="right", va="center", zorder=3)
        bar_y = y - step * 0.42
        rounded_bar(card, bar_x, bar_y, bar_w, bar_h, t["track"], zorder=2)
        fills.append(rounded_bar(card, bar_x, bar_y, max(bar_w * share, bar_h), bar_h,
                                 color, zorder=3))

    # ---- Hover interaction --------------------------------------------
    state = {"hover": None, "ready": not animate}

    def set_highlight(idx):
        if idx == state["hover"]:
            return
        state["hover"] = idx
        for j, w in enumerate(wedges):
            if idx is None:
                w.set_radius(1.0)
                w.set_width(RING_WIDTH)
                w.set_alpha(1.0)
            elif j == idx:
                w.set_radius(1.0 + HOVER_GROW)
                w.set_width(RING_WIDTH + HOVER_GROW)
                w.set_alpha(1.0)
            else:
                w.set_radius(1.0)
                w.set_width(RING_WIDTH)
                w.set_alpha(0.28)
        for j, bg in enumerate(row_bgs):
            bg.set_visible(j == idx)
        if idx is None:
            center_top.set_text("TOTAL SPENDING")
            center_top.set_color(t["muted"])
            center_mid.set_text(money(grand_total))
            center_bot.set_text(f"{len(labels)} categories")
        else:
            center_top.set_text(labels[idx].upper())
            center_top.set_color(colors[idx])
            center_mid.set_text(money(values[idx]))
            center_bot.set_text(f"{shares[idx]:.1%} of total")
        fig.canvas.draw_idle()

    def on_move(event):
        if not state["ready"]:
            return
        idx = None
        if event.inaxes is ax and event.xdata is not None:
            r = math.hypot(event.xdata, event.ydata)
            if 1.0 - RING_WIDTH - 0.05 <= r <= 1.0 + HOVER_GROW + 0.03:
                # clockwise angle from 12 o'clock
                d = (90 - math.degrees(math.atan2(event.ydata, event.xdata))) % 360
                for j, (a, b) in enumerate(spans):
                    if a <= d < b:
                        idx = j
                        break
        elif event.inaxes is card and event.ydata is not None:
            for j, (lo, hi) in enumerate(row_bounds):
                if lo <= event.ydata <= hi:
                    idx = j
                    break
        set_highlight(idx)

    fig.canvas.mpl_connect("motion_notify_event", on_move)

    # ---- Opening animation --------------------------------------------
    fade_items = outer + fills

    def render_progress(p):
        """Draw the chart at animation progress p in [0, 1]."""
        sweep = 360 * p
        for w, (a, b) in zip(wedges, spans):
            if sweep <= a:
                w.set_visible(False)
            else:
                w.set_visible(True)
                w.set_theta1(90 - min(b, sweep))
                w.set_theta2(90 - a)
        center_mid.set_text(money(grand_total * p))
        fade = min(1.0, max(0.0, (p - 0.7) / 0.3))
        for item in fade_items:
            item.set_alpha(fade)
        for fill, share in zip(fills, shares):
            fill.set_width(max(bar_w * share * p, bar_h))

    if animate and not output:
        render_progress(0)

        def update(frame):
            render_progress(ease_out_cubic(frame / (ANIM_FRAMES - 1)))
            if frame == ANIM_FRAMES - 1:
                state["ready"] = True
            return []

        # init_func is a no-op so resizing the window never resets the chart.
        fig._anim = FuncAnimation(fig, update, frames=ANIM_FRAMES, init_func=lambda: [],
                                  interval=ANIM_INTERVAL_MS, repeat=False)
    else:
        render_progress(1)
        state["ready"] = True

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
    parser.add_argument("--currency", default=DEFAULT_CURRENCY, help="currency symbol, e.g. NT$ or $")
    parser.add_argument("--font", default=DEFAULT_FONT, help="main font family name")
    parser.add_argument("--no-animation", action="store_true", help="skip the opening animation")
    args = parser.parse_args()

    expenses = filter_by_month(load_expenses(args.file), args.month)
    totals = summarize_by_category(expenses)

    print("Category totals:")
    for cat, amt in totals.items():
        print(f"  {cat:<15} {amt:>10,.2f}")

    title = f"Expenses by Category · {args.month}" if args.month else "Expenses by Category"
    draw_pie_chart(totals, expenses, title=title, output=args.output,
                   theme=args.theme, currency=args.currency,
                   animate=not args.no_animation, font=args.font)


if __name__ == "__main__":
    main()
