"""
app.py
------
Flask REST API for the Stock Analysis web app.

Endpoints:
  GET /api/stocks                         -> all stocks (ticker + name) for dropdown
  GET /api/stocks/search?q=<query>        -> fuzzy search by ticker or company name
  GET /api/stocks/<ticker>                -> metadata for a single stock
  GET /api/stocks/<ticker>/prices         -> historical OHLCV
                                             ?period=1y|2y|5y  (default 1y)

Run:
    python app.py
Server starts at http://localhost:5000
"""

import os
from datetime import date, timedelta

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
from sqlalchemy import func

from models import Stock, DailyPrice, get_session, init_db

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

FRONTEND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
CORS(app)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def period_to_start_date(period: str) -> date:
    today = date.today()
    mapping = {"1y": 365, "2y": 730, "5y": 1825}
    days = mapping.get(period, 365)
    return today - timedelta(days=days)


# ---------------------------------------------------------------------------
# Routes — serve frontend
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")


# ---------------------------------------------------------------------------
# API Routes
# ---------------------------------------------------------------------------

@app.route("/api/stocks", methods=["GET"])
def list_stocks():
    """Return all S&P 500 stocks for the autocomplete dropdown."""
    session = get_session()
    try:
        stocks = session.query(Stock).order_by(Stock.ticker).all()
        return jsonify([{"ticker": s.ticker, "name": s.name} for s in stocks])
    finally:
        session.close()


@app.route("/api/stocks/search", methods=["GET"])
def search_stocks():
    """
    Search stocks by ticker symbol or company name.
    Query param: q (string)
    Returns up to 20 matches.
    """
    q = request.args.get("q", "").strip().upper()
    if not q:
        return jsonify([])

    session = get_session()
    try:
        q_lower = q.lower()
        results = (
            session.query(Stock)
            .filter(
                (func.upper(Stock.ticker).like(f"{q}%"))
                | (func.lower(Stock.name).like(f"%{q_lower}%"))
            )
            .order_by(
                # Exact ticker match first
                (func.upper(Stock.ticker) == q).desc(),
                Stock.ticker,
            )
            .limit(20)
            .all()
        )
        return jsonify([{"ticker": s.ticker, "name": s.name, "sector": s.sector} for s in results])
    finally:
        session.close()


@app.route("/api/stocks/<ticker>", methods=["GET"])
def get_stock(ticker: str):
    """Return metadata for a single stock."""
    session = get_session()
    try:
        stock = session.query(Stock).filter(Stock.ticker == ticker.upper()).first()
        if not stock:
            return jsonify({"error": f"Stock '{ticker}' not found"}), 404
        return jsonify(stock.to_dict())
    finally:
        session.close()


@app.route("/api/stocks/<ticker>/prices", methods=["GET"])
def get_prices(ticker: str):
    """
    Return daily OHLCV data for a ticker.
    Query param: period  (1y | 2y | 5y, default 1y)
    """
    period = request.args.get("period", "1y")
    start = period_to_start_date(period)

    session = get_session()
    try:
        prices = (
            session.query(DailyPrice)
            .filter(
                DailyPrice.ticker == ticker.upper(),
                DailyPrice.date >= start,
            )
            .order_by(DailyPrice.date)
            .all()
        )
        if not prices:
            return jsonify({"error": f"No price data found for '{ticker}'"}), 404

        return jsonify([p.to_dict() for p in prices])
    finally:
        session.close()


@app.route("/api/stats", methods=["GET"])
def stats():
    """Quick DB stats — useful for health checks."""
    session = get_session()
    try:
        stock_count = session.query(Stock).count()
        price_count = session.query(DailyPrice).count()
        latest = session.query(func.max(DailyPrice.date)).scalar()
        return jsonify({
            "stocks": stock_count,
            "price_rows": price_count,
            "latest_date": latest.isoformat() if latest else None,
        })
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Ensure DB exists (tables created if missing)
    init_db()
    print("\n S&P 500 Stock Analysis API")
    print(" Open http://localhost:5000 in your browser\n")
    app.run(debug=True, port=5000)
