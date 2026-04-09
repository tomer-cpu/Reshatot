#!/usr/bin/env python3
"""
רשתות - Israeli Supermarket Price Data Fetcher

Fetches price data published by Israeli supermarket chains as required
by the Price Transparency Law (חוק קידום התחרות בענף המזון - שקיפות מחירים).

Data source: https://www.gov.il/he/departments/legalInfo/cpfta_prices_regulations

Usage:
    python main.py                      # List all chains
    python main.py --fetch              # Fetch data from all chains
    python main.py --fetch --chain Shufersal  # Fetch from specific chain
    python main.py --list-files --chain "Rami Levy"  # List files without downloading
"""

import argparse
import logging
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import (
    Engine, get_all_chains,
    CERBERUS_CHAINS, BINA_CHAINS, SHUFERSAL_CONFIG,
    MATRIX_CHAINS, VICTORY_CONFIG, PUBLISH_PRICE_CHAINS,
    SUPER_PHARM_CONFIG, HAZI_HINAM_CONFIG, WOLT_CONFIG,
    MESHNAT_YOSEF_WEB_CONFIG, NETIV_HASED_CONFIG, CITY_MARKET_SHOPS_CONFIG,
)
from scrapers.cerberus import CerberusScraper
from scrapers.bina import BinaScraper
from scrapers.shufersal import ShufersalScraper
from scrapers.matrix import MatrixScraper, VictoryScraper
from scrapers.publish_price import PublishPriceScraper
from scrapers.web_scrapers import (
    SuperPharmScraper, HaziHinamScraper, WoltScraper,
    MeshnatYosefWebScraper, NetivHasedScraper,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


ENGINE_TO_SCRAPER = {
    Engine.CERBERUS: CerberusScraper,
    Engine.BINA: BinaScraper,
    Engine.SHUFERSAL: ShufersalScraper,
    Engine.MATRIX: MatrixScraper,
    Engine.VICTORY_API: VictoryScraper,
    Engine.PUBLISH_PRICE: PublishPriceScraper,
    Engine.SUPER_PHARM: SuperPharmScraper,
    Engine.HAZI_HINAM: HaziHinamScraper,
    Engine.WOLT: WoltScraper,
    Engine.MESHNAT_YOSEF_WEB: MeshnatYosefWebScraper,
    Engine.NETIV_HASED: NetivHasedScraper,
}


def create_scraper(chain_config, output_dir="data"):
    """Create the appropriate scraper instance for a chain."""
    engine = chain_config["engine"]
    scraper_class = ENGINE_TO_SCRAPER.get(engine)
    if not scraper_class:
        logger.warning(f"No scraper for engine {engine.value}")
        return None
    return scraper_class(chain_config, output_dir)


def print_chains_table():
    """Print a formatted table of all supported chains."""
    chains = get_all_chains()
    print(f"\n{'='*80}")
    print(f"  רשתות שיווק - Israeli Supermarket Chains ({len(chains)} chains)")
    print(f"  Data mandated by Price Transparency Law (חוק שקיפות מחירים)")
    print(f"{'='*80}\n")
    print(f"  {'#':<4} {'Chain Name':<30} {'שם הרשת':<20} {'Engine':<15}")
    print(f"  {'-'*4} {'-'*30} {'-'*20} {'-'*15}")
    for i, chain in enumerate(chains, 1):
        name = chain["name"]
        name_he = chain.get("name_he", "")
        engine = chain["engine"].value
        print(f"  {i:<4} {name:<30} {name_he:<20} {engine:<15}")
    print()


def run_verify(chain_filter=None, output_dir="data"):
    """Verify freshness of downloaded files."""
    from datetime import date
    chains = get_all_chains()
    if chain_filter:
        filter_lower = chain_filter.lower()
        chains = [
            c for c in chains
            if filter_lower in c["name"].lower() or filter_lower in c.get("name_he", "")
        ]

    print(f"\n{'='*60}")
    print(f"  Freshness Report - {date.today()}")
    print(f"{'='*60}")
    print(f"  {'Chain':<30} {'Status':<10} {'Fresh':<8} {'Stale':<8} {'Total':<8}")
    print(f"  {'-'*30} {'-'*10} {'-'*8} {'-'*8} {'-'*8}")

    for chain_config in chains:
        scraper = create_scraper(chain_config, output_dir)
        if not scraper:
            continue
        result = scraper.verify_freshness()
        icon = "V" if result["status"] == "fresh" else "X" if result["status"] == "stale" else "-"
        print(
            f"  {result['chain']:<30} {icon:<10} "
            f"{result.get('fresh', 0):<8} {result.get('stale', 0):<8} "
            f"{result['total_files']:<8}"
        )
    print()


def run_fetch(chain_filter=None, output_dir="data", list_only=False):
    """Fetch (or list) price data from chains."""
    chains = get_all_chains()

    if chain_filter:
        filter_lower = chain_filter.lower()
        chains = [
            c for c in chains
            if filter_lower in c["name"].lower() or filter_lower in c.get("name_he", "")
        ]
        if not chains:
            logger.error(f"No chain found matching '{chain_filter}'")
            return

    total_files = 0
    successful_chains = 0
    failed_chains = []

    for chain in chains:
        logger.info(f"\n{'─'*60}")
        logger.info(f"Processing: {chain['name']} ({chain.get('name_he', '')})")
        logger.info(f"Engine: {chain['engine'].value}")
        logger.info(f"{'─'*60}")

        scraper = create_scraper(chain, output_dir)
        if not scraper:
            failed_chains.append(chain["name"])
            continue

        try:
            if list_only:
                files = scraper.list_files()
                for f in files:
                    fname = f if isinstance(f, str) else f.get("filename", f)
                    print(f"  - {fname}")
                total_files += len(files)
            else:
                downloaded = scraper.fetch()
                total_files += len(downloaded)
            successful_chains += 1
        except Exception as e:
            logger.error(f"[{chain['name']}] Error: {e}")
            failed_chains.append(chain["name"])

    # Summary
    print(f"\n{'='*60}")
    print(f"  Summary")
    print(f"{'='*60}")
    action = "Found" if list_only else "Downloaded"
    print(f"  Chains processed: {successful_chains}/{len(chains)}")
    print(f"  {action} files: {total_files}")
    if failed_chains:
        print(f"  Failed chains: {', '.join(failed_chains)}")
    if not list_only:
        print(f"  Output directory: {os.path.abspath(output_dir)}")
    print()


def main():
    parser = argparse.ArgumentParser(
        description="רשתות - Fetch price data from Israeli supermarket chains",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                              List all supported chains
  python main.py --fetch                      Download data from all chains
  python main.py --fetch --chain Shufersal    Download from Shufersal only
  python main.py --list-files                 List available files (no download)
  python main.py --list-files --chain Victory List Victory files only
  python main.py --fetch --output ./prices    Save to custom directory
        """,
    )
    parser.add_argument(
        "--fetch", action="store_true",
        help="Fetch/download price data files",
    )
    parser.add_argument(
        "--list-files", action="store_true",
        help="List available files without downloading",
    )
    parser.add_argument(
        "--verify", action="store_true",
        help="Verify freshness of already-downloaded files",
    )
    parser.add_argument(
        "--chain", type=str, default=None,
        help="Filter by chain name (partial match, case-insensitive)",
    )
    parser.add_argument(
        "--output", type=str, default="data",
        help="Output directory for downloaded files (default: ./data)",
    )

    args = parser.parse_args()

    if args.verify:
        run_verify(chain_filter=args.chain, output_dir=args.output)
    elif args.fetch or args.list_files:
        run_fetch(
            chain_filter=args.chain,
            output_dir=args.output,
            list_only=args.list_files,
        )
    else:
        print_chains_table()


if __name__ == "__main__":
    main()
