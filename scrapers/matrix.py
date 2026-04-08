"""
Matrix engine - HTTP scraper for chains hosted on laibcatalog.co.il

Used by: Het Cohen, Mahsanei HaShuk

Also includes Victory API scraper (same base domain, different endpoint).
"""

import logging
from urllib.parse import urljoin
from bs4 import BeautifulSoup
from .base import BaseScraper
from config import MATRIX_BASE_URL

logger = logging.getLogger(__name__)


class MatrixScraper(BaseScraper):
    """Scraper for chains using the Matrix/laibcatalog platform."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = MATRIX_BASE_URL
        self.page_url = f"{MATRIX_BASE_URL}/NBCompetitionRegulations.aspx"
        self.chain_hebrew_name = chain_config.get("name_he", "")

    def _parse_file_links(self, html):
        """Extract file links from the Matrix page, filtering by Hebrew chain name."""
        soup = BeautifulSoup(html, "lxml")
        files = []
        for row in soup.find_all("tr"):
            cells = row.find_all("td")
            if not cells:
                continue
            row_text = row.get_text()
            if self.chain_hebrew_name and self.chain_hebrew_name not in row_text:
                continue
            for link in row.find_all("a", href=True):
                href = link["href"]
                if any(ext in href.lower() for ext in [".xml", ".gz", ".zip", ".gzip"]):
                    filename = href.split("/")[-1]
                    url = href if href.startswith("http") else urljoin(self.base_url, href)
                    files.append({"filename": filename, "url": url})
        return files

    def list_files(self):
        """List all available files."""
        all_files = []
        try:
            resp = self.session.get(self.page_url, timeout=30)
            resp.raise_for_status()
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


class VictoryScraper(BaseScraper):
    """Scraper for Victory using the laibcatalog REST API."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.base_url = chain_config.get("base_url", MATRIX_BASE_URL)
        self.api_url = chain_config.get("api_url", f"{MATRIX_BASE_URL}/webapi/api/getfiles")

    def list_files(self):
        """List all available files from the Victory API."""
        all_files = []
        chain_ids = self.chain_id if isinstance(self.chain_id, list) else [self.chain_id]

        for edi in chain_ids:
            try:
                resp = self.session.get(
                    self.api_url,
                    params={"edi": edi},
                    timeout=30,
                )
                resp.raise_for_status()
                data = resp.json()
                if isinstance(data, list):
                    for entry in data:
                        filename = entry.get("fileName") or entry.get("name", "")
                        if not filename:
                            continue
                        url = f"{self.base_url}/webapi/{edi}/{filename}"
                        all_files.append({"filename": filename, "url": url})
            except Exception as e:
                logger.error(f"[{self.name}] Error fetching files for EDI {edi}: {e}")

        logger.info(f"[{self.name}] Found {len(all_files)} files")
        return all_files

    def fetch(self):
        """Download all Victory files."""
        files = self.list_files()
        downloaded = []
        for file_info in files:
            result = self.download_file(file_info["url"], file_info["filename"])
            if result:
                downloaded.append(result)
        return downloaded
