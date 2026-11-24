import csv
import os

FILENAME = "expenses.csv"

def init_csv():
    if not os.path.exists(FILENAME):
        with open(FILENAME, mode="w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["date", "amount", "category", "notes"])

def add_expenses():
    init_csv()
    while True:
        print("\n--- Add New Expense ---")
        date = input("Date (YYYY-MM-DD): ").strip()
        while True:
            try:
                amount = float(input("Amount: ").strip())
                break
            except ValueError:
                print("Invalid amount. Please enter a valid number.")
        category = input("Category (e.g., Food, Transport, Entertainment): ").strip()
        notes = input("Notes (optional, press Enter to skip): ").strip()

        with open(FILENAME, mode="a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([date, amount, category, notes])

        print("Expense saved successfully!")
        cont = input("Add another expense? (y/n): ").strip().lower()
        if cont != "y":
            break

if __name__ == "__main__":
    add_expenses()