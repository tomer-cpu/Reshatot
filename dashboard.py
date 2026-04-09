#!/usr/bin/env python3
"""
Competition Dashboard - תחרות בין רשתות

Web dashboard providing insights on price competition between
Israeli supermarket chains by product and geographic region.

Backed by SQLite for efficient queries over millions of records.

Usage:
    python database.py --import-data       # First: import data to SQLite
    python dashboard.py                    # Start on port 5000
    python dashboard.py --port 8080        # Custom port
"""

import argparse
import logging
import os
import sys

from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database import Database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)
db = Database()


# ──────────────────────────────────────────────
# API Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/stats")
def api_stats():
    return jsonify(db.query_stats())


@app.route("/api/chains")
def api_chains():
    return jsonify(db.query_chains())


@app.route("/api/cities")
def api_cities():
    return jsonify(db.query_cities())


@app.route("/api/search")
def api_search():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])
    return jsonify(db.query_search(query))


@app.route("/api/product/<item_code>")
def api_product_detail(item_code):
    return jsonify(db.query_product_detail(item_code))


@app.route("/api/competition")
def api_competition():
    city = request.args.get("city", "").strip()
    if not city:
        return jsonify({})
    return jsonify(db.query_competition(city))


@app.route("/api/top-spreads")
def api_top_spreads():
    return jsonify(db.query_top_spreads())


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    arg_parser = argparse.ArgumentParser(description="Competition Dashboard")
    arg_parser.add_argument("--port", type=int, default=5000)
    arg_parser.add_argument("--db", default=None, help="Database path (default: data/prices.db)")
    arg_parser.add_argument("--host", default="0.0.0.0")
    args = arg_parser.parse_args()

    global db
    db = Database(args.db)
    db.init_schema()

    stats = db.get_stats()
    print(f"\n  Dashboard: http://localhost:{args.port}")
    print(f"  Database:  {db.db_path}")
    print(f"  Records:   {stats['prices']:,} prices, {stats['stores']:,} stores")
    print(f"  Products:  {stats['unique_products']:,} | Chains: {stats['unique_chains']}")
    print(f"  Cities:    {stats['unique_cities']}\n")

    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
