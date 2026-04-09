"""Base scraper class with common functionality."""

import gzip
import os
import re
import logging
import requests
from datetime import datetime, date
from xml.etree import ElementTree

logger = logging.getLogger(__name__)

# Common date patterns found in Israeli supermarket price filenames
# e.g. PriceFull7290027600007-001-202604091200.gz
FILENAME_DATE_PATTERNS = [
    re.compile(r"(\d{4})(\d{2})(\d{2})\d{4}"),   # 202604091200
    re.compile(r"(\d{4})-(\d{2})-(\d{2})"),        # 2026-04-09
    re.compile(r"(\d{2})(\d{2})(\d{4})"),           # 09042026
]


def extract_date_from_filename(filename):
    """Try to extract a date from a price data filename."""
    for pattern in FILENAME_DATE_PATTERNS:
        match = pattern.search(filename)
        if match:
            groups = match.groups()
            try:
                if len(groups[0]) == 4:  # YYYY first
                    return date(int(groups[0]), int(groups[1]), int(groups[2]))
                else:  # DD or MM first, YYYY last
                    return date(int(groups[2]), int(groups[1]), int(groups[0]))
            except ValueError:
                continue
    return None


def extract_date_from_xml(filepath):
    """Try to extract the DumpDate from an XML or gzipped XML file."""
    try:
        if filepath.endswith(".gz"):
            with gzip.open(filepath, "rt", encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)
        else:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read(4096)

        match = re.search(r"<DumpDate>(\d{4})-(\d{2})-(\d{2})", content)
        if match:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
    except Exception:
        pass
    return None


def check_file_freshness(filepath, filename):
    """Check if a downloaded file is from today. Returns (is_fresh, file_date)."""
    today = date.today()

    file_date = extract_date_from_filename(filename)
    if file_date:
        return file_date == today, file_date

    file_date = extract_date_from_xml(filepath)
    if file_date:
        return file_date == today, file_date

    return None, None


class BaseScraper:
    """Base class for all chain scrapers."""

    def __init__(self, chain_config, output_dir="data"):
        self.config = chain_config
        self.name = chain_config["name"]
        self.name_he = chain_config.get("name_he", "")
        self.chain_id = chain_config["chain_id"]
        self.output_dir = os.path.join(output_dir, self._safe_name())
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })

    def _safe_name(self):
        """Return a filesystem-safe name for the chain."""
        return self.name.replace(" ", "_").replace("&", "and").replace("/", "_")

    def ensure_output_dir(self):
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch(self):
        """Fetch all available files. Override in subclasses."""
        raise NotImplementedError

    def download_file(self, url, filename):
        """Download a file from URL and save to output directory."""
        self.ensure_output_dir()
        filepath = os.path.join(self.output_dir, filename)
        try:
            resp = self.session.get(url, timeout=60)
            resp.raise_for_status()
            with open(filepath, "wb") as f:
                f.write(resp.content)
            logger.info(f"  [{self.name}] Downloaded: {filename} ({len(resp.content)} bytes)")
            return filepath
        except requests.RequestException as e:
            logger.error(f"  [{self.name}] Failed to download {filename}: {e}")
            return None

    def list_files(self):
        """List available files without downloading. Override in subclasses."""
        raise NotImplementedError

    def verify_freshness(self):
        """Check all downloaded files in output_dir and report freshness."""
        if not os.path.isdir(self.output_dir):
            return {"chain": self.name, "chain_he": self.name_he,
                    "status": "no_data", "total_files": 0,
                    "fresh": 0, "stale": 0, "unknown": 0, "files": []}

        results = []
        for filename in os.listdir(self.output_dir):
            filepath = os.path.join(self.output_dir, filename)
            if not os.path.isfile(filepath):
                continue
            is_fresh, file_date = check_file_freshness(filepath, filename)
            results.append({
                "filename": filename,
                "date": str(file_date) if file_date else "unknown",
                "is_fresh": is_fresh,
            })

        fresh_count = sum(1 for r in results if r["is_fresh"] is True)
        stale_count = sum(1 for r in results if r["is_fresh"] is False)
        unknown_count = sum(1 for r in results if r["is_fresh"] is None)

        return {
            "chain": self.name,
            "chain_he": self.name_he,
            "total_files": len(results),
            "fresh": fresh_count,
            "stale": stale_count,
            "unknown": unknown_count,
            "status": "fresh" if fresh_count > 0 and stale_count == 0 else
                      "stale" if stale_count > 0 else
                      "unknown",
            "files": results,
        }
