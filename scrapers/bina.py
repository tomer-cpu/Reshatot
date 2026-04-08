"""
Bina engine - HTTP scraper for chains hosted on {prefix}.binaprojects.com

Used by: Bareket, Good Pharm, King Store, Maayan 2000, Shefa Birkat Hashem,
         Shuk HaIr, Super Sapir, Zol VeBegadol, Meshnat Yosef, City Market Kiryat Gat
"""

import logging
import re
from urllib.parse import urljoin, urlencode, quote
from bs4 import BeautifulSoup
from .base import BaseScraper
from config import BINA_DOMAIN

logger = logging.getLogger(__name__)

# Bina file type IDs
FILE_TYPE_MAP = {
    "all": "0",
    "stores": "1",
    "price": "2",
    "promo": "3",
    "pricefull": "4",
    "promofull": "5",
}


class BinaScraper(BaseScraper):
    """Scraper for chains using the Bina platform."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        prefix = chain_config["url_prefix"]
        self.base_url = f"http://{prefix}.{BINA_DOMAIN}/"
        self.page_url = f"http://{prefix}.{BINA_DOMAIN}/MainIO_Hok.aspx"
        self.download_base = f"http://{prefix}.{BINA_DOMAIN}/Download.aspx?FileNm="
        chain_id = self.chain_id
        if isinstance(chain_id, list):
            chain_id = chain_id[0]
        self._chain_id_str = chain_id

    def _build_url(self, file_type="all"):
        """Build the query URL for a specific file type."""
        params = {
            "_": self._chain_id_str,
            "wReshet": "הכל",
            "WFileType": FILE_TYPE_MAP.get(file_type, "0"),
        }
        return f"{self.page_url}?{urlencode(params, quote_via=quote)}"

    def _parse_file_links(self, html):
        """Extract file links from the HTML page."""
        soup = BeautifulSoup(html, "lxml")
        files = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if "Download.aspx" in href or href.endswith((".xml", ".gz", ".xml.gz")):
                filename = href.split("FileNm=")[-1] if "FileNm=" in href else href.split("/")[-1]
                download_url = href if href.startswith("http") else urljoin(self.base_url, href)
                files.append({"filename": filename, "url": download_url})
        return files

    def list_files(self):
        """List all available files."""
        all_files = []
        try:
            url = self._build_url("all")
            resp = self.session.get(url, timeout=30)
            resp.raise_for_status()
            all_files = self._parse_file_links(resp.text)
            logger.info(f"[{self.name}] Found {len(all_files)} files")
        except Exception as e:
            logger.error(f"[{self.name}] Error listing files: {e}")
        return all_files

    def fetch(self):
        """Download all files from Bina platform."""
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded
