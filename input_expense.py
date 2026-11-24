import csv
import os

FILENAME = "expenses.csv"

def init_csv():
    if not os.path.exists(FILENAME):
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "amount", "category", "notes"])

if __name__ == "__main__":
    init_csv()
    print("CSV initialized.")