"""
Web-based scrapers for chains with custom HTTP endpoints.

Includes: Super Pharm, Hazi Hinam, Wolt, Meshnat Yosef (Workers),
          Netiv HaHesed, City Market Shops.
"""

import logging
import re
import json
from datetime import datetime, timedelta
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper

logger = logging.getLogger(__name__)


class SuperPharmScraper(BaseScraper):
    """Scraper for Super Pharm price data (prices.super-pharm.co.il)."""

    FILE_TYPES = {
        "1": "StoresFull",
        "2": "Price",
        "3": "Promo",
        "4": "PriceFull",
        "5": "PromoFull",
    }

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = chain_config["base_url"]

    def _get_total_pages(self, html):
        soup = BeautifulSoup(html, "lxml")
        buttons = soup.select('.mvc-grid-pager button[data-page]')
        if not buttons:
            return 1
        return max(int(btn.get("data-page", 1)) for btn in buttons)

    def _parse_file_links(self, html):
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
        all_files = []
        try:
            resp = self.session.get(self.base_url, timeout=30)
            resp.raise_for_status()
            page_files = self._parse_file_links(resp.text)
            all_files.extend(page_files)
            total_pages = self._get_total_pages(resp.text)
            for page in range(2, total_pages + 1):
                resp = self.session.get(f"{self.base_url}?page={page}", timeout=30)
                resp.raise_for_status()
                all_files.extend(self._parse_file_links(resp.text))
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
        logger.info(f"[{self.name}] Found {len(all_files)} files")
        return all_files

    def fetch(self):
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded


class HaziHinamScraper(BaseScraper):
    """Scraper for Hazi Hinam / City Market Shops price data."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = chain_config["base_url"]

    def _get_total_pages(self, html):
        soup = BeautifulSoup(html, "lxml")
        pages = soup.select(".pagination-item a")
        if not pages:
            return 1
        max_page = 1
        for a in pages:
            href = a.get("href", "")
            match = re.search(r"p=(\d+)", href)
            if match:
                max_page = max(max_page, int(match.group(1)))
        return max_page

    def _parse_file_links(self, html):
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
        all_files = []
        try:
            today = datetime.now().strftime("%d/%m/%Y")
            yesterday = (datetime.now() - timedelta(days=1)).strftime("%d/%m/%Y")
            for date in [today, yesterday]:
                url = f"{self.base_url}?date={date}"
                resp = self.session.get(url, timeout=30)
                resp.raise_for_status()
                page_files = self._parse_file_links(resp.text)
                all_files.extend(page_files)
                total_pages = self._get_total_pages(resp.text)
                for page in range(2, total_pages + 1):
                    resp = self.session.get(f"{url}&p={page}", timeout=30)
                    resp.raise_for_status()
                    all_files.extend(self._parse_file_links(resp.text))
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
        logger.info(f"[{self.name}] Found {len(all_files)} files")
        return all_files

    def fetch(self):
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded


class WoltScraper(BaseScraper):
    """Scraper for Wolt price data."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = chain_config["base_url"]

    def list_files(self):
        all_files = []
        base = self.base_url.rsplit("/", 1)[0]
        for days_back in range(10):
            date = datetime.now() - timedelta(days=days_back)
            date_str = date.strftime("%Y-%m-%d")
            url = f"{base}/{date_str}/index.html"
            try:
                resp = self.session.get(url, timeout=15)
                if resp.status_code != 200:
                    continue
                soup = BeautifulSoup(resp.text, "lxml")
                for link in soup.find_all("a", href=True):
                    href = link["href"]
                    if any(ext in href.lower() for ext in [".xml", ".gz", ".zip"]):
                        filename = href.split("/")[-1]
                        file_url = href if href.startswith("http") else urljoin(url, href)
                        all_files.append({"filename": filename, "url": file_url})
                if all_files:
                    break
            except Exception:
                continue
        logger.info(f"[{self.name}] Found {len(all_files)} files")
        return all_files

    def fetch(self):
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded


class MeshnatYosefWebScraper(BaseScraper):
    """Scraper for Meshnat Yosef via Cloudflare Workers."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = chain_config["base_url"]

    def list_files(self):
        all_files = []
        try:
            resp = self.session.get(self.base_url, timeout=30)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, list):
                for entry in data:
                    if isinstance(entry, str):
                        filename = entry
                    elif isinstance(entry, dict):
                        filename = entry.get("name", entry.get("fileName", ""))
                    else:
                        continue
                    if filename:
                        url = urljoin(self.base_url, filename)
                        all_files.append({"filename": filename, "url": url})
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
        logger.info(f"[{self.name}] Found {len(all_files)} files")
        return all_files

    def fetch(self):
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded


class NetivHasedScraper(BaseScraper):
    """Scraper for Netiv HaHesed via direct IP."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = chain_config["base_url"]

    def _parse_directory_listing(self, html):
        soup = BeautifulSoup(html, "lxml")
        files = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if any(ext in href.lower() for ext in [".xml", ".gz", ".zip"]):
                filename = href.split("/")[-1]
                url = urljoin(self.base_url, href)
                files.append({"filename": filename, "url": url})
        return files

    def list_files(self):
        all_files = []
        try:
            resp = self.session.get(self.base_url, timeout=30)
            resp.raise_for_status()
            all_files = self._parse_directory_listing(resp.text)
        except Exception as e:
            logger.error(f"[{self.name}] Error: {e}")
        logger.info(f"[{self.name}] Found {len(all_files)} files")
        return all_files

    def fetch(self):
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded
