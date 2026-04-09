#!/usr/bin/env python3
"""
Competition Dashboard - תחרות בין רשתות

Web dashboard providing insights on price competition between
Israeli supermarket chains by product and geographic region.

Usage:
    python dashboard.py                    # Start on port 5000
    python dashboard.py --port 8080        # Custom port
    python dashboard.py --data ./prices    # Custom data directory
"""

import argparse
import json
import logging
import os
import sys

from flask import Flask, render_template, jsonify, request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
from parser import load_all_data, build_store_lookup

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Global data store - loaded on startup
DATA = {
    "stores": pd.DataFrame(),
    "prices": pd.DataFrame(),
    "promos": pd.DataFrame(),
    "store_lookup": {},
    "loaded": False,
}


def init_data(data_dir="data"):
    """Load and prepare all data for the dashboard."""
    logger.info(f"Loading data from {data_dir}...")
    result = load_all_data(data_dir)
    DATA["stores"] = result["stores"]
    DATA["prices"] = result["prices"]
    DATA["promos"] = result["promos"]
    DATA["store_lookup"] = build_store_lookup(result["stores"])
    DATA["loaded"] = True

    # Enrich prices with city info from store lookup
    if not DATA["prices"].empty and DATA["store_lookup"]:
        DATA["prices"]["city"] = DATA["prices"].apply(
            lambda row: DATA["store_lookup"].get(
                (str(row.get("chain_id", "")), str(row.get("store_id", ""))), {}
            ).get("city", ""),
            axis=1,
        )
        DATA["prices"]["chain_name_resolved"] = DATA["prices"].apply(
            lambda row: DATA["store_lookup"].get(
                (str(row.get("chain_id", "")), str(row.get("store_id", ""))), {}
            ).get("chain_name", row.get("chain_id", "")),
            axis=1,
        )

    logger.info(f"Data loaded: {len(DATA['stores'])} stores, "
                f"{len(DATA['prices'])} prices, {len(DATA['promos'])} promos")


# ──────────────────────────────────────────────
# API Routes
# ──────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("dashboard.html")


@app.route("/api/stats")
def api_stats():
    """Overall statistics."""
    prices = DATA["prices"]
    stores = DATA["stores"]

    chain_col = "chain_name_resolved" if "chain_name_resolved" in prices.columns else "chain_id"

    stats = {
        "total_products": int(prices["ItemCode"].nunique()) if "ItemCode" in prices.columns else 0,
        "total_chains": int(prices[chain_col].nunique()) if chain_col in prices.columns else 0,
        "total_stores": len(DATA["store_lookup"]),
        "total_price_records": len(prices),
        "total_cities": int(prices["city"].nunique()) if "city" in prices.columns else 0,
        "data_loaded": DATA["loaded"],
    }
    return jsonify(stats)


@app.route("/api/chains")
def api_chains():
    """List all chains with store count."""
    stores = DATA["stores"]
    if stores.empty:
        return jsonify([])

    chain_col = "chain_name" if "chain_name" in stores.columns else "chain_id"
    result = stores.groupby(chain_col).size().reset_index(name="store_count")
    result = result.sort_values("store_count", ascending=False)
    return jsonify(result.to_dict(orient="records"))


@app.route("/api/cities")
def api_cities():
    """List all cities with chain presence."""
    prices = DATA["prices"]
    if prices.empty or "city" not in prices.columns:
        return jsonify([])

    chain_col = "chain_name_resolved" if "chain_name_resolved" in prices.columns else "chain_id"
    cities = prices[prices["city"] != ""].groupby("city")[chain_col].nunique().reset_index(
        name="chain_count"
    )
    cities = cities.sort_values("chain_count", ascending=False)
    return jsonify(cities.head(50).to_dict(orient="records"))


@app.route("/api/search")
def api_search():
    """Search products by name or barcode."""
    query = request.args.get("q", "").strip()
    if not query or DATA["prices"].empty:
        return jsonify([])

    prices = DATA["prices"]
    name_col = "ItemName" if "ItemName" in prices.columns else None

    if query.isdigit():
        mask = prices["ItemCode"].astype(str).str.contains(query, na=False)
    elif name_col:
        mask = prices[name_col].str.contains(query, case=False, na=False)
    else:
        return jsonify([])

    matches = prices[mask]
    if matches.empty:
        return jsonify([])

    # Get unique products
    group_cols = ["ItemCode"]
    if name_col:
        group_cols.append(name_col)

    products = matches.groupby(group_cols).agg(
        avg_price=("ItemPrice", "mean"),
        min_price=("ItemPrice", "min"),
        max_price=("ItemPrice", "max"),
        chain_count=(
            "chain_name_resolved" if "chain_name_resolved" in matches.columns else "chain_id",
            "nunique",
        ),
        record_count=("ItemPrice", "count"),
    ).reset_index()

    products = products.sort_values("record_count", ascending=False).head(20)

    result = []
    for _, row in products.iterrows():
        item = {
            "item_code": str(row["ItemCode"]),
            "item_name": row.get("ItemName", ""),
            "avg_price": round(float(row["avg_price"]), 2),
            "min_price": round(float(row["min_price"]), 2),
            "max_price": round(float(row["max_price"]), 2),
            "chain_count": int(row["chain_count"]),
            "price_spread": round(float(row["max_price"] - row["min_price"]), 2),
        }
        result.append(item)

    return jsonify(result)


@app.route("/api/product/<item_code>")
def api_product_detail(item_code):
    """Get detailed price comparison for a specific product across chains and cities."""
    prices = DATA["prices"]
    if prices.empty:
        return jsonify({})

    mask = prices["ItemCode"].astype(str) == str(item_code)
    product = prices[mask]
    if product.empty:
        return jsonify({})

    chain_col = "chain_name_resolved" if "chain_name_resolved" in product.columns else "chain_id"
    name_col = "ItemName" if "ItemName" in product.columns else None

    item_name = product[name_col].iloc[0] if name_col and not product[name_col].empty else item_code

    # Price by chain
    by_chain = product.groupby(chain_col).agg(
        avg_price=("ItemPrice", "mean"),
        min_price=("ItemPrice", "min"),
        max_price=("ItemPrice", "max"),
        store_count=("store_id", "nunique"),
    ).reset_index()
    by_chain = by_chain.sort_values("avg_price")
    by_chain.columns = ["chain", "avg_price", "min_price", "max_price", "store_count"]

    # Price by city (competition zones)
    by_city = []
    if "city" in product.columns:
        city_data = product[product["city"] != ""].groupby(["city", chain_col]).agg(
            avg_price=("ItemPrice", "mean"),
        ).reset_index()
        city_data.columns = ["city", "chain", "avg_price"]

        # For each city, compute competition metrics
        for city in city_data["city"].unique():
            city_rows = city_data[city_data["city"] == city]
            if len(city_rows) < 2:
                continue
            cheapest = city_rows.loc[city_rows["avg_price"].idxmin()]
            most_expensive = city_rows.loc[city_rows["avg_price"].idxmax()]
            by_city.append({
                "city": city,
                "chains_count": len(city_rows),
                "cheapest_chain": cheapest["chain"],
                "cheapest_price": round(float(cheapest["avg_price"]), 2),
                "expensive_chain": most_expensive["chain"],
                "expensive_price": round(float(most_expensive["avg_price"]), 2),
                "price_gap": round(float(most_expensive["avg_price"] - cheapest["avg_price"]), 2),
                "price_gap_pct": round(
                    float((most_expensive["avg_price"] - cheapest["avg_price"])
                          / cheapest["avg_price"] * 100), 1
                ) if cheapest["avg_price"] > 0 else 0,
            })
        by_city.sort(key=lambda x: x["price_gap_pct"], reverse=True)

    return jsonify({
        "item_code": item_code,
        "item_name": item_name,
        "total_records": len(product),
        "by_chain": [
            {k: round(v, 2) if isinstance(v, float) else v for k, v in row.items()}
            for row in by_chain.to_dict(orient="records")
        ],
        "by_city": by_city[:30],
    })


@app.route("/api/competition")
def api_competition():
    """
    Competition analysis for a specific city/region.
    Shows which chains compete and their price positioning.
    """
    city = request.args.get("city", "").strip()
    prices = DATA["prices"]
    if prices.empty or not city:
        return jsonify({})

    chain_col = "chain_name_resolved" if "chain_name_resolved" in prices.columns else "chain_id"

    city_data = prices[prices.get("city", pd.Series()) == city] if "city" in prices.columns else pd.DataFrame()
    if city_data.empty:
        return jsonify({"city": city, "chains": [], "products": []})

    # Chains active in this city
    chains_in_city = city_data[chain_col].unique().tolist()

    # Find products sold by multiple chains (actual competition)
    product_chains = city_data.groupby("ItemCode")[chain_col].nunique()
    competitive_products = product_chains[product_chains >= 2].index

    competitive_data = city_data[city_data["ItemCode"].isin(competitive_products)]

    name_col = "ItemName" if "ItemName" in competitive_data.columns else None

    # Top products with highest price variance (most competitive)
    group_cols = ["ItemCode"]
    if name_col:
        group_cols.append(name_col)

    product_stats = competitive_data.groupby(group_cols).agg(
        avg_price=("ItemPrice", "mean"),
        min_price=("ItemPrice", "min"),
        max_price=("ItemPrice", "max"),
        chain_count=(chain_col, "nunique"),
    ).reset_index()

    product_stats["spread_pct"] = (
        (product_stats["max_price"] - product_stats["min_price"])
        / product_stats["min_price"] * 100
    ).fillna(0)
    product_stats = product_stats.sort_values("spread_pct", ascending=False)

    top_products = []
    for _, row in product_stats.head(30).iterrows():
        item_code = row["ItemCode"]
        item_prices = competitive_data[competitive_data["ItemCode"] == item_code]
        chain_prices = item_prices.groupby(chain_col)["ItemPrice"].mean().sort_values()

        top_products.append({
            "item_code": str(item_code),
            "item_name": row.get("ItemName", ""),
            "avg_price": round(float(row["avg_price"]), 2),
            "min_price": round(float(row["min_price"]), 2),
            "max_price": round(float(row["max_price"]), 2),
            "spread_pct": round(float(row["spread_pct"]), 1),
            "chain_count": int(row["chain_count"]),
            "chain_prices": {
                chain: round(float(price), 2)
                for chain, price in chain_prices.items()
            },
        })

    # Chain-level price index in this city (average basket)
    chain_avg = city_data.groupby(chain_col)["ItemPrice"].mean().sort_values()
    overall_avg = city_data["ItemPrice"].mean()

    chain_index = []
    for chain, avg in chain_avg.items():
        index_val = (avg / overall_avg * 100) if overall_avg > 0 else 100
        store_count = city_data[city_data[chain_col] == chain]["store_id"].nunique()
        chain_index.append({
            "chain": chain,
            "avg_price": round(float(avg), 2),
            "price_index": round(float(index_val), 1),
            "store_count": int(store_count),
        })

    return jsonify({
        "city": city,
        "chains": chain_index,
        "total_competitive_products": len(competitive_products),
        "products": top_products,
    })


@app.route("/api/top-spreads")
def api_top_spreads():
    """Products with the largest price spread across chains (biggest competition gaps)."""
    prices = DATA["prices"]
    if prices.empty:
        return jsonify([])

    chain_col = "chain_name_resolved" if "chain_name_resolved" in prices.columns else "chain_id"
    name_col = "ItemName" if "ItemName" in prices.columns else None

    # Only products in 3+ chains
    product_chains = prices.groupby("ItemCode")[chain_col].nunique()
    multi_chain = product_chains[product_chains >= 3].index
    filtered = prices[prices["ItemCode"].isin(multi_chain)]

    group_cols = ["ItemCode"]
    if name_col:
        group_cols.append(name_col)

    stats = filtered.groupby(group_cols).agg(
        avg_price=("ItemPrice", "mean"),
        min_price=("ItemPrice", "min"),
        max_price=("ItemPrice", "max"),
        chain_count=(chain_col, "nunique"),
    ).reset_index()

    stats["spread_pct"] = (
        (stats["max_price"] - stats["min_price"]) / stats["min_price"] * 100
    ).fillna(0)
    stats = stats[stats["min_price"] > 0].sort_values("spread_pct", ascending=False).head(50)

    result = []
    for _, row in stats.iterrows():
        result.append({
            "item_code": str(row["ItemCode"]),
            "item_name": row.get("ItemName", ""),
            "avg_price": round(float(row["avg_price"]), 2),
            "min_price": round(float(row["min_price"]), 2),
            "max_price": round(float(row["max_price"]), 2),
            "spread_pct": round(float(row["spread_pct"]), 1),
            "chain_count": int(row["chain_count"]),
        })

    return jsonify(result)


# ──────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────

def main():
    arg_parser = argparse.ArgumentParser(description="Competition Dashboard")
    arg_parser.add_argument("--port", type=int, default=5000)
    arg_parser.add_argument("--data", default="data", help="Data directory")
    arg_parser.add_argument("--host", default="0.0.0.0")
    args = arg_parser.parse_args()

    init_data(args.data)
    print(f"\n  Dashboard: http://localhost:{args.port}")
    print(f"  Data dir:  {os.path.abspath(args.data)}\n")
    app.run(host=args.host, port=args.port, debug=False)


if __name__ == "__main__":
    main()
