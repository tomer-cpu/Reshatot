"""
SQLite database layer for Israeli supermarket price data.

Handles import from XML files and provides efficient queries for
the competition dashboard. Supports incremental imports and
handles 10-30M+ price records efficiently.

Usage:
    python database.py --import-data                 # Import from ./data
    python database.py --import-data --data ./prices # Custom data dir
    python database.py --stats                       # Show DB statistics
    python database.py --reset                       # Drop and recreate tables
"""

import argparse
import logging
import os
import sqlite3
import sys
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from parser import (
    parse_stores_xml, parse_prices_xml, parse_promos_xml, classify_file,
)

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "prices.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS stores (
    chain_id TEXT NOT NULL,
    chain_name TEXT,
    store_id TEXT NOT NULL,
    store_name TEXT,
    city TEXT,
    address TEXT,
    store_type TEXT,
    PRIMARY KEY (chain_id, store_id)
);

CREATE TABLE IF NOT EXISTS prices (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    item_code TEXT NOT NULL,
    item_name TEXT,
    item_price REAL,
    unit_of_measure TEXT,
    quantity TEXT,
    manufacturer_name TEXT,
    manufacture_country TEXT,
    update_date TEXT,
    file_date TEXT
);

CREATE TABLE IF NOT EXISTS promos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    chain_id TEXT NOT NULL,
    store_id TEXT NOT NULL,
    promo_id TEXT,
    promo_description TEXT,
    start_date TEXT,
    end_date TEXT,
    min_qty TEXT,
    discount_rate TEXT,
    discount_type TEXT,
    item_code TEXT,
    item_name TEXT,
    file_date TEXT
);

CREATE TABLE IF NOT EXISTS import_log (
    filepath TEXT PRIMARY KEY,
    file_type TEXT,
    records_count INTEGER,
    imported_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_prices_item ON prices(item_code);
CREATE INDEX IF NOT EXISTS idx_prices_chain ON prices(chain_id);
CREATE INDEX IF NOT EXISTS idx_prices_store ON prices(chain_id, store_id);
CREATE INDEX IF NOT EXISTS idx_prices_item_chain ON prices(item_code, chain_id);
CREATE INDEX IF NOT EXISTS idx_stores_city ON stores(city);
CREATE INDEX IF NOT EXISTS idx_promos_item ON promos(item_code);
"""

# Materialized views for fast dashboard queries
VIEWS = """
CREATE VIEW IF NOT EXISTS v_prices_enriched AS
SELECT
    p.item_code,
    p.item_name,
    p.item_price,
    p.chain_id,
    p.store_id,
    COALESCE(s.chain_name, p.chain_id) AS chain_name,
    COALESCE(s.city, '') AS city,
    COALESCE(s.store_name, '') AS store_name
FROM prices p
LEFT JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id;
"""


class Database:
    """SQLite database wrapper for price data."""

    def __init__(self, db_path=None):
        self.db_path = db_path or DEFAULT_DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._conn = None

    def connect(self):
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
            self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
            self._conn.execute("PRAGMA temp_store=MEMORY")
        return self._conn

    def close(self):
        if self._conn:
            self._conn.close()
            self._conn = None

    def init_schema(self):
        conn = self.connect()
        conn.executescript(SCHEMA)
        conn.executescript(VIEWS)
        conn.commit()

    def reset(self):
        conn = self.connect()
        conn.executescript("""
            DROP TABLE IF EXISTS prices;
            DROP TABLE IF EXISTS stores;
            DROP TABLE IF EXISTS promos;
            DROP TABLE IF EXISTS import_log;
            DROP VIEW IF EXISTS v_prices_enriched;
        """)
        conn.commit()
        self.init_schema()

    def _is_imported(self, filepath):
        conn = self.connect()
        row = conn.execute(
            "SELECT 1 FROM import_log WHERE filepath = ?", (filepath,)
        ).fetchone()
        return row is not None

    def _log_import(self, filepath, file_type, count):
        conn = self.connect()
        conn.execute(
            "INSERT OR REPLACE INTO import_log VALUES (?, ?, ?, ?)",
            (filepath, file_type, count, datetime.now().isoformat()),
        )

    def import_stores(self, filepath):
        if self._is_imported(filepath):
            return 0
        records = parse_stores_xml(filepath)
        if not records:
            return 0

        conn = self.connect()
        count = 0
        for r in records:
            store_id = r.get("StoreId", r.get("storeid", ""))
            if not store_id:
                continue
            conn.execute(
                """INSERT OR REPLACE INTO stores
                   (chain_id, chain_name, store_id, store_name, city, address, store_type)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    r.get("chain_id", ""),
                    r.get("chain_name", ""),
                    store_id,
                    r.get("StoreName", r.get("storename", "")),
                    r.get("City", r.get("city", "")),
                    r.get("Address", r.get("address", "")),
                    r.get("StoreType", r.get("storetype", "")),
                ),
            )
            count += 1

        self._log_import(filepath, "stores", count)
        conn.commit()
        return count

    def import_prices(self, filepath, file_date=None):
        if self._is_imported(filepath):
            return 0
        records = parse_prices_xml(filepath)
        if not records:
            return 0

        conn = self.connect()
        batch = []
        for r in records:
            price = r.get("ItemPrice")
            if isinstance(price, str):
                try:
                    price = float(price)
                except (ValueError, TypeError):
                    price = None
            batch.append((
                r.get("chain_id", ""),
                r.get("store_id", ""),
                r.get("ItemCode", ""),
                r.get("ItemName", r.get("itemname", "")),
                price,
                r.get("UnitOfMeasure", r.get("unitofmeasure", "")),
                r.get("Quantity", r.get("quantity", "")),
                r.get("ManufacturerName", r.get("manufacturername", "")),
                r.get("ManufactureCountry", r.get("manufacturecountry", "")),
                r.get("PriceUpdateDate", r.get("priceupdatedate", "")),
                file_date or "",
            ))

        conn.executemany(
            """INSERT INTO prices
               (chain_id, store_id, item_code, item_name, item_price,
                unit_of_measure, quantity, manufacturer_name,
                manufacture_country, update_date, file_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            batch,
        )
        self._log_import(filepath, "prices", len(batch))
        conn.commit()
        return len(batch)

    def import_promos(self, filepath, file_date=None):
        if self._is_imported(filepath):
            return 0
        records = parse_promos_xml(filepath)
        if not records:
            return 0

        conn = self.connect()
        batch = []
        for r in records:
            batch.append((
                r.get("chain_id", ""),
                r.get("store_id", ""),
                r.get("PromotionId", r.get("promotionid", "")),
                r.get("PromotionDescription", r.get("promotiondescription", "")),
                r.get("StartDate", r.get("startdate", "")),
                r.get("EndDate", r.get("enddate", "")),
                r.get("MinQty", r.get("minqty", "")),
                r.get("DiscountRate", r.get("discountrate", "")),
                r.get("DiscountType", r.get("discounttype", "")),
                r.get("ItemCode", r.get("itemcode", "")),
                r.get("ItemName", r.get("itemname", "")),
                file_date or "",
            ))

        conn.executemany(
            """INSERT INTO promos
               (chain_id, store_id, promo_id, promo_description,
                start_date, end_date, min_qty, discount_rate,
                discount_type, item_code, item_name, file_date)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            batch,
        )
        self._log_import(filepath, "promos", len(batch))
        conn.commit()
        return len(batch)

    def import_data_dir(self, data_dir="data"):
        """Import all XML/GZ files from the data directory into SQLite."""
        self.init_schema()

        if not os.path.isdir(data_dir):
            logger.warning(f"Data directory not found: {data_dir}")
            return

        total_stores = 0
        total_prices = 0
        total_promos = 0
        total_files = 0
        start = time.time()

        for chain_dir in sorted(os.listdir(data_dir)):
            chain_path = os.path.join(data_dir, chain_dir)
            if not os.path.isdir(chain_path) or chain_dir.startswith("."):
                continue

            chain_stores = 0
            chain_prices = 0
            chain_promos = 0

            files = sorted(os.listdir(chain_path))
            for filename in files:
                filepath = os.path.join(chain_path, filename)
                if not os.path.isfile(filepath):
                    continue

                ftype = classify_file(filename)
                if ftype == "unknown":
                    continue

                total_files += 1

                if ftype == "stores":
                    count = self.import_stores(filepath)
                    chain_stores += count
                    total_stores += count
                elif ftype in ("price", "pricefull"):
                    count = self.import_prices(filepath)
                    chain_prices += count
                    total_prices += count
                elif ftype in ("promo", "promofull"):
                    count = self.import_promos(filepath)
                    chain_promos += count
                    total_promos += count

            if chain_stores or chain_prices or chain_promos:
                logger.info(
                    f"[{chain_dir}] Imported: {chain_stores} stores, "
                    f"{chain_prices} prices, {chain_promos} promos"
                )

        elapsed = time.time() - start
        logger.info(
            f"\nImport complete in {elapsed:.1f}s: "
            f"{total_files} files, {total_stores} stores, "
            f"{total_prices} prices, {total_promos} promos"
        )
        logger.info(f"Database: {self.db_path} ({os.path.getsize(self.db_path) / 1024 / 1024:.1f} MB)")

    def get_stats(self):
        conn = self.connect()
        self.init_schema()
        stats = {}
        for table in ["stores", "prices", "promos", "import_log"]:
            row = conn.execute(f"SELECT COUNT(*) as cnt FROM {table}").fetchone()
            stats[table] = row["cnt"]

        row = conn.execute("SELECT COUNT(DISTINCT item_code) as cnt FROM prices").fetchone()
        stats["unique_products"] = row["cnt"]
        row = conn.execute("SELECT COUNT(DISTINCT chain_id) as cnt FROM prices").fetchone()
        stats["unique_chains"] = row["cnt"]
        row = conn.execute("SELECT COUNT(DISTINCT city) as cnt FROM stores WHERE city != ''").fetchone()
        stats["unique_cities"] = row["cnt"]

        stats["db_size_mb"] = round(os.path.getsize(self.db_path) / 1024 / 1024, 1)
        return stats

    # ──────────────────────────────────────────
    # Dashboard query methods
    # ──────────────────────────────────────────

    def query_stats(self):
        conn = self.connect()
        return {
            "total_products": conn.execute("SELECT COUNT(DISTINCT item_code) FROM prices").fetchone()[0],
            "total_chains": conn.execute("SELECT COUNT(DISTINCT chain_id) FROM prices").fetchone()[0],
            "total_stores": conn.execute("SELECT COUNT(*) FROM stores").fetchone()[0],
            "total_price_records": conn.execute("SELECT COUNT(*) FROM prices").fetchone()[0],
            "total_cities": conn.execute(
                "SELECT COUNT(DISTINCT city) FROM stores WHERE city != ''"
            ).fetchone()[0],
            "data_loaded": True,
        }

    def query_chains(self):
        conn = self.connect()
        rows = conn.execute("""
            SELECT COALESCE(chain_name, chain_id) as chain_name, COUNT(*) as store_count
            FROM stores
            GROUP BY 1
            ORDER BY store_count DESC
        """).fetchall()
        return [dict(r) for r in rows]

    def query_cities(self, limit=50):
        conn = self.connect()
        rows = conn.execute("""
            SELECT s.city, COUNT(DISTINCT p.chain_id) as chain_count
            FROM prices p
            JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE s.city != ''
            GROUP BY s.city
            ORDER BY chain_count DESC
            LIMIT ?
        """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    def query_search(self, query, limit=20):
        conn = self.connect()
        if query.isdigit():
            where = "p.item_code LIKE ?"
            param = f"%{query}%"
        else:
            where = "p.item_name LIKE ?"
            param = f"%{query}%"

        rows = conn.execute(f"""
            SELECT
                p.item_code,
                p.item_name,
                ROUND(AVG(p.item_price), 2) as avg_price,
                ROUND(MIN(p.item_price), 2) as min_price,
                ROUND(MAX(p.item_price), 2) as max_price,
                COUNT(DISTINCT COALESCE(s.chain_name, p.chain_id)) as chain_count,
                COUNT(*) as record_count
            FROM prices p
            LEFT JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE {where} AND p.item_price > 0
            GROUP BY p.item_code, p.item_name
            ORDER BY record_count DESC
            LIMIT ?
        """, (param, limit)).fetchall()

        result = []
        for r in rows:
            d = dict(r)
            d["price_spread"] = round(d["max_price"] - d["min_price"], 2)
            result.append(d)
        return result

    def query_product_detail(self, item_code):
        conn = self.connect()

        # Product info
        info = conn.execute("""
            SELECT item_name, COUNT(*) as total_records
            FROM prices WHERE item_code = ?
        """, (item_code,)).fetchone()

        if not info or info["total_records"] == 0:
            return {}

        # By chain
        by_chain = conn.execute("""
            SELECT
                COALESCE(s.chain_name, p.chain_id) as chain,
                ROUND(AVG(p.item_price), 2) as avg_price,
                ROUND(MIN(p.item_price), 2) as min_price,
                ROUND(MAX(p.item_price), 2) as max_price,
                COUNT(DISTINCT p.store_id) as store_count
            FROM prices p
            LEFT JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE p.item_code = ? AND p.item_price > 0
            GROUP BY chain
            ORDER BY avg_price ASC
        """, (item_code,)).fetchall()

        # By city
        by_city_raw = conn.execute("""
            SELECT
                s.city,
                COALESCE(s.chain_name, p.chain_id) as chain,
                ROUND(AVG(p.item_price), 2) as avg_price
            FROM prices p
            JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE p.item_code = ? AND s.city != '' AND p.item_price > 0
            GROUP BY s.city, chain
        """, (item_code,)).fetchall()

        # Compute city competition
        city_data = {}
        for r in by_city_raw:
            city = r["city"]
            if city not in city_data:
                city_data[city] = []
            city_data[city].append({"chain": r["chain"], "avg_price": r["avg_price"]})

        by_city = []
        for city, chains in city_data.items():
            if len(chains) < 2:
                continue
            chains.sort(key=lambda x: x["avg_price"])
            cheapest = chains[0]
            expensive = chains[-1]
            gap_pct = round(
                (expensive["avg_price"] - cheapest["avg_price"]) / cheapest["avg_price"] * 100, 1
            ) if cheapest["avg_price"] > 0 else 0
            by_city.append({
                "city": city,
                "chains_count": len(chains),
                "cheapest_chain": cheapest["chain"],
                "cheapest_price": cheapest["avg_price"],
                "expensive_chain": expensive["chain"],
                "expensive_price": expensive["avg_price"],
                "price_gap": round(expensive["avg_price"] - cheapest["avg_price"], 2),
                "price_gap_pct": gap_pct,
            })
        by_city.sort(key=lambda x: x["price_gap_pct"], reverse=True)

        return {
            "item_code": item_code,
            "item_name": info["item_name"] or item_code,
            "total_records": info["total_records"],
            "by_chain": [dict(r) for r in by_chain],
            "by_city": by_city[:30],
        }

    def query_competition(self, city):
        conn = self.connect()

        # Chain price index in this city
        chain_index = conn.execute("""
            SELECT
                COALESCE(s.chain_name, p.chain_id) as chain,
                ROUND(AVG(p.item_price), 2) as avg_price,
                COUNT(DISTINCT p.store_id) as store_count
            FROM prices p
            JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE s.city = ? AND p.item_price > 0
            GROUP BY chain
            ORDER BY avg_price ASC
        """, (city,)).fetchall()

        if not chain_index:
            return {"city": city, "chains": [], "total_competitive_products": 0, "products": []}

        overall_avg = sum(r["avg_price"] for r in chain_index) / len(chain_index)
        chains = []
        for r in chain_index:
            idx = round(r["avg_price"] / overall_avg * 100, 1) if overall_avg > 0 else 100
            chains.append({
                "chain": r["chain"],
                "avg_price": r["avg_price"],
                "price_index": idx,
                "store_count": r["store_count"],
            })

        # Products with highest price spread in this city
        products = conn.execute("""
            SELECT
                p.item_code,
                p.item_name,
                ROUND(AVG(p.item_price), 2) as avg_price,
                ROUND(MIN(p.item_price), 2) as min_price,
                ROUND(MAX(p.item_price), 2) as max_price,
                COUNT(DISTINCT COALESCE(s.chain_name, p.chain_id)) as chain_count,
                ROUND((MAX(p.item_price) - MIN(p.item_price)) / MIN(p.item_price) * 100, 1) as spread_pct
            FROM prices p
            JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE s.city = ? AND p.item_price > 0
            GROUP BY p.item_code, p.item_name
            HAVING chain_count >= 2 AND min_price > 0
            ORDER BY spread_pct DESC
            LIMIT 30
        """, (city,)).fetchall()

        total_competitive = conn.execute("""
            SELECT COUNT(*) FROM (
                SELECT p.item_code
                FROM prices p
                JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
                WHERE s.city = ? AND p.item_price > 0
                GROUP BY p.item_code
                HAVING COUNT(DISTINCT p.chain_id) >= 2
            )
        """, (city,)).fetchone()[0]

        # Get chain-level prices for each top product
        product_list = []
        for prod in products:
            chain_prices_rows = conn.execute("""
                SELECT
                    COALESCE(s.chain_name, p.chain_id) as chain,
                    ROUND(AVG(p.item_price), 2) as avg_price
                FROM prices p
                JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
                WHERE s.city = ? AND p.item_code = ? AND p.item_price > 0
                GROUP BY chain
                ORDER BY avg_price ASC
            """, (city, prod["item_code"])).fetchall()

            product_list.append({
                "item_code": prod["item_code"],
                "item_name": prod["item_name"] or "",
                "avg_price": prod["avg_price"],
                "min_price": prod["min_price"],
                "max_price": prod["max_price"],
                "spread_pct": prod["spread_pct"],
                "chain_count": prod["chain_count"],
                "chain_prices": {r["chain"]: r["avg_price"] for r in chain_prices_rows},
            })

        return {
            "city": city,
            "chains": chains,
            "total_competitive_products": total_competitive,
            "products": product_list,
        }

    def query_top_spreads(self, limit=50):
        conn = self.connect()
        rows = conn.execute("""
            SELECT
                p.item_code,
                p.item_name,
                ROUND(AVG(p.item_price), 2) as avg_price,
                ROUND(MIN(p.item_price), 2) as min_price,
                ROUND(MAX(p.item_price), 2) as max_price,
                COUNT(DISTINCT COALESCE(s.chain_name, p.chain_id)) as chain_count,
                ROUND((MAX(p.item_price) - MIN(p.item_price)) / MIN(p.item_price) * 100, 1) as spread_pct
            FROM prices p
            LEFT JOIN stores s ON p.chain_id = s.chain_id AND p.store_id = s.store_id
            WHERE p.item_price > 0
            GROUP BY p.item_code, p.item_name
            HAVING chain_count >= 3 AND min_price > 0
            ORDER BY spread_pct DESC
            LIMIT ?
        """, (limit,)).fetchall()

        return [dict(r) for r in rows]


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

    arg_parser = argparse.ArgumentParser(description="Database management for price data")
    arg_parser.add_argument("--import-data", action="store_true", help="Import XML files into SQLite")
    arg_parser.add_argument("--data", default="data", help="Data directory (default: ./data)")
    arg_parser.add_argument("--db", default=None, help="Database path (default: data/prices.db)")
    arg_parser.add_argument("--stats", action="store_true", help="Show database statistics")
    arg_parser.add_argument("--reset", action="store_true", help="Reset database (drop all tables)")
    args = arg_parser.parse_args()

    db = Database(args.db)

    if args.reset:
        db.reset()
        print("Database reset.")
    elif args.import_data:
        db.import_data_dir(args.data)
    elif args.stats:
        db.init_schema()
        stats = db.get_stats()
        print(f"\n{'='*50}")
        print(f"  Database Statistics")
        print(f"{'='*50}")
        print(f"  Stores:           {stats['stores']:>12,}")
        print(f"  Price records:    {stats['prices']:>12,}")
        print(f"  Promo records:    {stats['promos']:>12,}")
        print(f"  Imported files:   {stats['import_log']:>12,}")
        print(f"  Unique products:  {stats['unique_products']:>12,}")
        print(f"  Unique chains:    {stats['unique_chains']:>12,}")
        print(f"  Cities:           {stats['unique_cities']:>12,}")
        print(f"  DB size:          {stats['db_size_mb']:>11.1f} MB")
        print()
    else:
        arg_parser.print_help()

    db.close()


if __name__ == "__main__":
    main()
