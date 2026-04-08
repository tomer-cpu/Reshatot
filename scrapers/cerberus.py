"""
Cerberus engine - FTP-based scraper for chains hosted on url.retail.publishedprices.co.il

Used by: Rami Levy, Cofix, Dor Alon, Keshet, Polizer, Salach Dabach,
         Stop Market, Super Yuda, Fresh Market, Tiv Taam, Yellow, Yohananof, Osher Ad
"""

import ftplib
import logging
import os
from .base import BaseScraper
from config import CERBERUS_HOST

logger = logging.getLogger(__name__)


class CerberusScraper(BaseScraper):
    """Scraper for chains using the Cerberus FTP server."""

    def __init__(self, chain_config, output_dir="data"):
        super().__init__(chain_config, output_dir)
        self.host = CERBERUS_HOST
        self.ftp_username = chain_config.get("ftp_username", "")
        self.ftp_password = chain_config.get("ftp_password", "")
        self.ftp_path = chain_config.get("ftp_path", "/")

    def _connect_ftp(self):
        """Establish FTP connection."""
        ftp = ftplib.FTP(self.host, timeout=30)
        ftp.login(user=self.ftp_username, passwd=self.ftp_password)
        if self.ftp_path != "/":
            ftp.cwd(self.ftp_path)
        return ftp

    def list_files(self):
        """List all available files on the FTP server."""
        files = []
        try:
            ftp = self._connect_ftp()
            file_list = ftp.nlst()
            for f in file_list:
                if f.lower().endswith((".xml", ".gz", ".zip", ".xml.gz")):
                    files.append(f)
            ftp.quit()
            logger.info(f"[{self.name}] Found {len(files)} files on FTP")
        except ftplib.all_errors as e:
            logger.error(f"[{self.name}] FTP error: {e}")
        return files

    def fetch(self):
        """Download all XML/GZ files from FTP."""
        self.ensure_output_dir()
        downloaded = []
        try:
            ftp = self._connect_ftp()
            file_list = ftp.nlst()

            for filename in file_list:
                if not filename.lower().endswith((".xml", ".gz", ".zip", ".xml.gz")):
                    continue
                filepath = os.path.join(self.output_dir, filename)
                try:
                    with open(filepath, "wb") as f:
                        ftp.retrbinary(f"RETR {filename}", f.write)
                    size = os.path.getsize(filepath)
                    logger.info(f"  [{self.name}] Downloaded: {filename} ({size} bytes)")
                    downloaded.append(filepath)
                except ftplib.all_errors as e:
                    logger.error(f"  [{self.name}] Failed to download {filename}: {e}")

            ftp.quit()
        except ftplib.all_errors as e:
            logger.error(f"[{self.name}] FTP connection error: {e}")

        return downloaded
