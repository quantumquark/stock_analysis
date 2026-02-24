"""
fetch_data.py
-------------
One-time (idempotent) script to:
  1. Scrape the S&P 500 constituent list from Wikipedia
  2. Insert stocks into the `stocks` table
  3. Download 5 years of daily OHLCV data for all tickers via yfinance
  4. Insert price rows into the `daily_prices` table

Run:
    python fetch_data.py

This takes ~5-15 minutes depending on network speed.
It is safe to re-run -- existing records are skipped.
"""

import io
import time
import requests
import pandas as pd
import yfinance as yf
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from tqdm import tqdm

from models import Stock, DailyPrice, get_engine, get_session, init_db


# ---------------------------------------------------------------------------
# 1. Fetch S&P 500 list from Wikipedia
# ---------------------------------------------------------------------------

def get_sp500_list():
    print("Fetching S&P 500 list from Wikipedia...")
    url = "https://en.wikipedia.org/wiki/List_of_S%26P_500_companies"
    # Use requests with a browser User-Agent — Wikipedia blocks Python's urllib
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        )
    }
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    tables = pd.read_html(io.StringIO(resp.text))
    df = tables[0]
    df = df.rename(columns={
        "Symbol": "ticker",
        "Security": "name",
        "GICS Sector": "sector",
        "GICS Sub-Industry": "industry",
    })
    # Clean up tickers (some have dots that yfinance needs as dashes)
    df["ticker"] = df["ticker"].str.replace(".", "-", regex=False)
    return df[["ticker", "name", "sector", "industry"]].to_dict("records")


# ---------------------------------------------------------------------------
# 2. Insert stocks into DB
# ---------------------------------------------------------------------------

def upsert_stocks(session, stocks):
    print(f"Inserting {len(stocks)} stocks into database...")
    for s in stocks:
        stmt = sqlite_insert(Stock).values(
            ticker=s["ticker"],
            name=s["name"],
            sector=s.get("sector"),
            industry=s.get("industry"),
        ).on_conflict_do_update(
            index_elements=["ticker"],
            set_=dict(name=s["name"], sector=s.get("sector"), industry=s.get("industry")),
        )
        session.execute(stmt)
    session.commit()
    print("Stocks inserted.")


# ---------------------------------------------------------------------------
# 3. Download 5 years of daily prices and insert into DB
# ---------------------------------------------------------------------------

BATCH_SIZE = 50  # Download N tickers at a time to avoid rate limits


def _extract_ticker_rows(raw, ticker):
    """
    Extract OHLCV rows for a single ticker from a yfinance DataFrame.
    Handles yfinance >= 1.0 MultiIndex columns: (Price, Ticker).
    """
    rows = []
    try:
        # yfinance 1.x always returns MultiIndex (Price, Ticker)
        tickers_in_cols = raw.columns.get_level_values(1).unique().tolist()
        if ticker not in tickers_in_cols:
            return rows
        df = raw.xs(ticker, axis=1, level=1).copy()
    except (KeyError, AttributeError):
        return rows

    if df.empty:
        return rows

    df = df.reset_index()
    date_col = "Date" if "Date" in df.columns else df.columns[0]

    for _, row in df.iterrows():
        close_val = row.get("Close")
        if close_val is None or pd.isna(close_val):
            continue
        date_val = row[date_col]
        if hasattr(date_val, "date"):
            date_val = date_val.date()
        rows.append({
            "ticker": ticker,
            "date": date_val,
            "open": float(row["Open"]) if not pd.isna(row.get("Open")) else None,
            "high": float(row["High"]) if not pd.isna(row.get("High")) else None,
            "low": float(row["Low"]) if not pd.isna(row.get("Low")) else None,
            "close": float(close_val),
            "volume": int(row["Volume"]) if not pd.isna(row.get("Volume")) else None,
        })
    return rows


def download_and_store_prices(session, tickers):
    engine = get_engine()
    total = len(tickers)
    print(f"\nDownloading 5-year daily prices for {total} tickers (batch size={BATCH_SIZE})...")

    batches = [tickers[i: i + BATCH_SIZE] for i in range(0, total, BATCH_SIZE)]

    for batch_num, batch in enumerate(tqdm(batches, desc="Batches"), start=1):
        try:
            raw = yf.download(
                tickers=batch,
                period="5y",
                interval="1d",
                auto_adjust=True,
                progress=False,
            )
        except Exception as e:
            print(f"  [WARN] Batch {batch_num} download error: {e}")
            time.sleep(2)
            continue

        rows = []
        for ticker in batch:
            rows.extend(_extract_ticker_rows(raw, ticker))

        if rows:
            try:
                stmt = sqlite_insert(DailyPrice).values(rows).on_conflict_do_nothing(
                    index_elements=["ticker", "date"]
                )
                with engine.begin() as conn:
                    conn.execute(stmt)
            except Exception as db_err:
                print(f"  [WARN] DB insert error in batch {batch_num}: {db_err}")

        # Polite delay to avoid rate limiting
        time.sleep(0.5)

    print("\nPrice data download complete.")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("=" * 60)
    print("  S&P 500 Data Fetcher")
    print("=" * 60)

    # Initialize DB tables
    init_db()

    session = get_session()

    try:
        # Step 1: Get stock list
        stocks = get_sp500_list()

        # Step 2: Insert stocks
        upsert_stocks(session, stocks)

        # Step 3: Download and store prices
        tickers = [s["ticker"] for s in stocks]
        download_and_store_prices(session, tickers)

        # Summary
        price_count = session.query(DailyPrice).count()
        stock_count = session.query(Stock).count()
        print(f"\nDone! Database summary:")
        print(f"  Stocks : {stock_count}")
        print(f"  Prices : {price_count:,} rows")

    finally:
        session.close()


if __name__ == "__main__":
    main()
