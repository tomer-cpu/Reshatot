"""
Shufersal scraper - Custom HTTP scraper for prices.shufersal.co.il

Shufersal publishes prices through a paginated web interface with
category-based file listings.
"""

import logging
import re
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper
from config import SHUFERSAL_CONFIG, FileType

logger = logging.getLogger(__name__)


class ShufersalScraper(BaseScraper):
    """Scraper for Shufersal price data."""

    def __init__(self, chain_config=None, output_dir="data"):
        super().__init__(chain_config or SHUFERSAL_CONFIG, output_dir)
        self.base_url = SHUFERSAL_CONFIG["base_url"]
        self.update_url = SHUFERSAL_CONFIG["update_url"]
        self.categories = SHUFERSAL_CONFIG["categories"]

    def _get_total_pages(self, html):
        """Extract total number of pages from pagination."""
        soup = BeautifulSoup(html, "lxml")
        pages = soup.select("table tfoot a")
        if not pages:
            return 1
        max_page = 1
        for link in pages:
            href = link.get("href", "")
            match = re.search(r"page=(\d+)", href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        return max_page

    def _parse_file_links(self, html):
        """Extract file download links from page HTML."""
        soup = BeautifulSoup(html, "lxml")
        files = []
        for row in soup.select("tr"):
            link = row.select_one("a[href]")
            if not link:
                continue
            href = link.get("href", "")
            if not href or not any(ext in href.lower() for ext in [".xml", ".gz", ".zip"]):
                continue
            filename = href.split("/")[-1]
            url = href if href.startswith("http") else urljoin(self.base_url, href)
            files.append({"filename": filename, "url": url})
        return files

    def _fetch_category(self, category_id):
        """Fetch all files for a specific category."""
        files = []
        page = 1

        while True:
            url = f"{self.update_url}?catID={category_id}&storeId=&page={page}"
            try:
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                page_files = self._parse_file_links(resp.text)
                if not page_files:
                    break
                files.extend(page_files)

                total_pages = self._get_total_pages(resp.text)
                if page >= total_pages:
                    break
                page += 1
            except Exception as e:
                logger.error(f"  [{self.name}] Error fetching category {category_id} page {page}: {e}")
                break

        return files

    def list_files(self):
        """List all available files across all categories."""
        all_files = []
        for file_type, cat_id in self.categories.items():
            logger.info(f"  [{self.name}] Listing {file_type.value} files (category {cat_id})...")
            files = self._fetch_category(cat_id)
            all_files.extend(files)
        logger.info(f"[{self.name}] Found {len(all_files)} total files")
        return all_files

    def fetch(self):
        """Download all files from Shufersal."""
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded
