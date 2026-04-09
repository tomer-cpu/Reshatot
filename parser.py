"""
XML Parser for Israeli supermarket price data files.

Parses the gzipped/plain XML files downloaded by the scrapers into
structured DataFrames for analysis.

File types:
- Stores:    Branch/store information (address, city, chain)
- PriceFull: Complete daily price snapshot per store
- PromoFull: Complete daily promotions per store
- Price:     Incremental price updates (hourly)
- Promo:     Incremental promotion updates (hourly)
"""

import gzip
import os
import re
import logging
import glob as glob_module
from xml.etree import ElementTree
from datetime import datetime

import pandas as pd

logger = logging.getLogger(__name__)


def _open_file(filepath):
    """Open a file, auto-detecting gzip."""
    if filepath.endswith(".gz"):
        return gzip.open(filepath, "rt", encoding="utf-8", errors="ignore")
    return open(filepath, "r", encoding="utf-8", errors="ignore")


def parse_stores_xml(filepath):
    """Parse a Stores XML file into a list of store dicts."""
    stores = []
    try:
        with _open_file(filepath) as f:
            tree = ElementTree.parse(f)
        root = tree.getroot()

        chain_id = ""
        chain_name = ""
        ci = root.find(".//ChainId")
        if ci is not None:
            chain_id = ci.text or ""
        cn = root.find(".//ChainName")
        if cn is not None:
            chain_name = cn.text or ""

        for store in root.iter("Store"):
            store_dict = {"chain_id": chain_id, "chain_name": chain_name}
            for child in store:
                store_dict[child.tag] = child.text or ""
            stores.append(store_dict)
    except Exception as e:
        logger.debug(f"Error parsing stores file {filepath}: {e}")
    return stores


def parse_prices_xml(filepath):
    """Parse a Prices/PriceFull XML file into a list of item dicts."""
    items = []
    try:
        with _open_file(filepath) as f:
            tree = ElementTree.parse(f)
        root = tree.getroot()

        chain_id = ""
        store_id = ""
        ci = root.find(".//ChainId")
        if ci is not None:
            chain_id = ci.text or ""
        si = root.find(".//StoreId")
        if si is not None:
            store_id = si.text or ""

        for item in root.iter("Item"):
            item_dict = {"chain_id": chain_id, "store_id": store_id}
            for child in item:
                if child.tag == "ItemPrice":
                    try:
                        item_dict[child.tag] = float(child.text)
                    except (ValueError, TypeError):
                        item_dict[child.tag] = child.text or ""
                elif child.tag == "ItemCode":
                    item_dict[child.tag] = (child.text or "").strip()
                else:
                    item_dict[child.tag] = child.text or ""
            items.append(item_dict)
    except Exception as e:
        logger.debug(f"Error parsing prices file {filepath}: {e}")
    return items


def parse_promos_xml(filepath):
    """Parse a Promos/PromoFull XML file into a list of promo dicts."""
    promos = []
    try:
        with _open_file(filepath) as f:
            tree = ElementTree.parse(f)
        root = tree.getroot()

        chain_id = ""
        store_id = ""
        ci = root.find(".//ChainId")
        if ci is not None:
            chain_id = ci.text or ""
        si = root.find(".//StoreId")
        if si is not None:
            store_id = si.text or ""

        for promo in root.iter("Promotion"):
            promo_dict = {"chain_id": chain_id, "store_id": store_id}
            for child in promo:
                promo_dict[child.tag] = child.text or ""
            promos.append(promo_dict)
    except Exception as e:
        logger.debug(f"Error parsing promos file {filepath}: {e}")
    return promos


def classify_file(filename):
    """Classify a file by type based on its name."""
    name_lower = filename.lower()
    if "storesfull" in name_lower or "store" in name_lower:
        return "stores"
    elif "pricefull" in name_lower:
        return "pricefull"
    elif "promofull" in name_lower or "promosfull" in name_lower:
        return "promofull"
    elif "promo" in name_lower:
        return "promo"
    elif "price" in name_lower:
        return "price"
    return "unknown"


def load_all_data(data_dir="data", file_type_filter=None, max_files_per_chain=None):
    """
    Load all downloaded data from the data directory.

    Returns dict with keys: stores, prices, promos (each a pd.DataFrame).
    """
    all_stores = []
    all_prices = []
    all_promos = []

    if not os.path.isdir(data_dir):
        logger.warning(f"Data directory not found: {data_dir}")
        return {"stores": pd.DataFrame(), "prices": pd.DataFrame(), "promos": pd.DataFrame()}

    for chain_dir in sorted(os.listdir(data_dir)):
        chain_path = os.path.join(data_dir, chain_dir)
        if not os.path.isdir(chain_path) or chain_dir.startswith("."):
            continue

        files = sorted(os.listdir(chain_path))
        stores_count = 0
        prices_count = 0
        promos_count = 0

        for filename in files:
            filepath = os.path.join(chain_path, filename)
            if not os.path.isfile(filepath):
                continue

            ftype = classify_file(filename)

            if file_type_filter and ftype not in file_type_filter:
                continue

            if ftype == "stores":
                if max_files_per_chain and stores_count >= max_files_per_chain:
                    continue
                records = parse_stores_xml(filepath)
                all_stores.extend(records)
                stores_count += 1

            elif ftype in ("price", "pricefull"):
                if max_files_per_chain and prices_count >= max_files_per_chain:
                    continue
                records = parse_prices_xml(filepath)
                all_prices.extend(records)
                prices_count += 1

            elif ftype in ("promo", "promofull"):
                if max_files_per_chain and promos_count >= max_files_per_chain:
                    continue
                records = parse_promos_xml(filepath)
                all_promos.extend(records)
                promos_count += 1

        logger.info(f"[{chain_dir}] Parsed: {stores_count} store files, "
                     f"{prices_count} price files, {promos_count} promo files")

    result = {
        "stores": pd.DataFrame(all_stores) if all_stores else pd.DataFrame(),
        "prices": pd.DataFrame(all_prices) if all_prices else pd.DataFrame(),
        "promos": pd.DataFrame(all_promos) if all_promos else pd.DataFrame(),
    }

    logger.info(f"Total: {len(result['stores'])} stores, "
                f"{len(result['prices'])} price records, "
                f"{len(result['promos'])} promo records")

    return result


def build_store_lookup(stores_df):
    """Build a lookup mapping (chain_id, store_id) -> store info (city, address, etc.)."""
    if stores_df.empty:
        return {}

    lookup = {}
    id_col = "StoreId" if "StoreId" in stores_df.columns else "storeid"
    city_col = "City" if "City" in stores_df.columns else "city"

    for _, row in stores_df.iterrows():
        key = (str(row.get("chain_id", "")), str(row.get(id_col, "")))
        lookup[key] = {
            "city": row.get(city_col, ""),
            "address": row.get("Address", row.get("address", "")),
            "store_name": row.get("StoreName", row.get("storename", "")),
            "chain_name": row.get("chain_name", ""),
        }
    return lookup
