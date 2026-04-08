"""Base scraper class with common functionality."""

import os
import logging
import requests
from datetime import datetime

logger = logging.getLogger(__name__)


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
