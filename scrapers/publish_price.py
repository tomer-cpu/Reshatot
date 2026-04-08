"""
PublishPrice engine - HTTP scraper for chains hosted on prices.{infix}.co.il

Used by: Quik
"""

import logging
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)


class PublishPriceScraper(BaseScraper):
    """Scraper for chains using the PublishPrice platform."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        infix = chain_config["site_infix"]
        self.base_url = f"https://prices.{infix}.co.il/"

    def _parse_files_from_js(self, html):
        """Extract file list from embedded JavaScript variables."""
        files = []
        path_match = re.search(r'const\s+path\s*=\s*["\']([^"\']+)["\']', html)
        files_match = re.search(r'const\s+files\s*=\s*(\[.*?\])', html, re.DOTALL)

        base_path = path_match.group(1) if path_match else ""

        if files_match:
            import json
            try:
                file_list = json.loads(files_match.group(1))
                for entry in file_list:
                    if isinstance(entry, str):
                        filename = entry
                    elif isinstance(entry, dict):
                        filename = entry.get("name", entry.get("fileName", ""))
                    else:
                        continue
                    if filename:
                        url = urljoin(self.base_url, f"{base_path}/{filename}")
                        files.append({"filename": filename, "url": url})
            except json.JSONDecodeError:
                pass

        return files

    def _parse_file_links(self, html):
        """Fallback: parse file links from HTML."""
        soup = BeautifulSoup(html, "lxml")
        files = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if any(ext in href.lower() for ext in [".xml", ".gz", ".zip"]):
                filename = href.split("/")[-1]
                url = href if href.startswith("http") else urljoin(self.base_url, href)
                files.append({"filename": filename, "url": url})
        return files

    def list_files(self):
        """List all available files."""
        all_files = []
        try:
            resp = self.session.get(self.base_url, timeout=30)
            resp.raise_for_status()
            all_files = self._parse_files_from_js(resp.text)
            if not all_files:
                all_files = self._parse_file_links(resp.text)
            logger.info(f"[{self.name}] Found {len(all_files)} files")
        except Exception as e:
            logger.error(f"[{self.name}] Error listing files: {e}")
        return all_files

    def fetch(self):
        """Download all files."""
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded
