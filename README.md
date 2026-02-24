# S&P 500 Stock Analysis

A full-stack web app for exploring historical price data for all S&P 500 stocks.

**Features**
- Search any S&P 500 stock by **ticker symbol** (e.g. `AAPL`) or **company name** (e.g. `Apple`)
- Interactive **closing price chart** with volume overlay
- **1Y / 2Y / 5Y** time range selector
- Period summary stats: Latest Close, Period High, Period Low, Return %
- SQLite database storing **5 years of daily OHLCV** data for ~500 stocks (~630K rows)

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3 · Flask · SQLAlchemy |
| Database | SQLite |
| Data source | yfinance |
| Frontend | Bootstrap 5 · Chart.js · Choices.js |

---

## Project Structure

```
stock_analysis/
├── backend/
│   ├── app.py           # Flask REST API (serves frontend + /api routes)
│   ├── models.py        # SQLAlchemy ORM (stocks + daily_prices tables)
│   ├── fetch_data.py    # One-time script: download & store S&P 500 price history
│   └── requirements.txt
├── frontend/
│   ├── index.html
│   ├── style.css
│   └── script.js
├── .gitignore
└── README.md
```

---

## Setup & Run

### 1. Install dependencies
```bash
cd backend
pip install -r requirements.txt
```

### 2. Populate the database (run once — takes ~5–15 min)
```bash
python fetch_data.py
```
This fetches the S&P 500 list from Wikipedia and downloads 5 years of daily prices via `yfinance`. The script is **idempotent** — safe to re-run.

### 3. Start the server
```bash
python app.py
```

### 4. Open the app
Navigate to **http://localhost:5000** in your browser.

---

## API Endpoints

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/stocks` | All S&P 500 stocks (ticker + name) |
| GET | `/api/stocks/search?q=<query>` | Search by ticker or company name |
| GET | `/api/stocks/<ticker>` | Stock metadata |
| GET | `/api/stocks/<ticker>/prices?period=1y` | Historical OHLCV (`1y`, `2y`, `5y`) |
| GET | `/api/stats` | DB row counts + latest date |

---

## Notes

- The SQLite database file (`backend/stock_data.db`) is excluded from git (see `.gitignore`). Run `fetch_data.py` after cloning to rebuild it.
- yfinance is used for historical data. Price data is sourced from Yahoo Finance.
- The chart supports **scroll-to-zoom** and **click-drag-to-pan**.