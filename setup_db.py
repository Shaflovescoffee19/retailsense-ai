"""
Run this once to generate the SQLite database from the CSV.
Usage: python setup_db.py
"""

import sqlite3
import pandas as pd
import os

CSV_PATH = "superstore.csv"
DB_PATH = "retailsense.db"

if not os.path.exists(CSV_PATH):
    print("ERROR: superstore.csv not found. Please place it in this directory.")
    exit(1)

print("Loading CSV...")
df = pd.read_csv(CSV_PATH)
print(f"  Rows: {len(df):,}, Columns: {len(df.columns)}")

print("Writing to SQLite...")
conn = sqlite3.connect(DB_PATH)
df.to_sql("sales", conn, if_exists="replace", index=False)
conn.close()

print(f"Done! Database saved to {DB_PATH}")
