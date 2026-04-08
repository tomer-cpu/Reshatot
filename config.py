"""
Configuration for all Israeli supermarket chains required to publish price data
under the Price Transparency Law (חוק שקיפות מחירים).

Data source: https://www.gov.il/he/departments/legalInfo/cpfta_prices_regulations
"""

from enum import Enum


class Engine(Enum):
    CERBERUS = "cerberus"       # FTP-based via url.retail.publishedprices.co.il
    BINA = "bina"               # HTTP via {prefix}.binaprojects.com
    SHUFERSAL = "shufersal"     # Custom HTTP at prices.shufersal.co.il
    MATRIX = "matrix"           # HTTP via laibcatalog.co.il
    VICTORY_API = "victory_api" # REST API via laibcatalog.co.il/webapi
    PUBLISH_PRICE = "publish_price"  # HTTP via prices.{infix}.co.il
    SUPER_PHARM = "super_pharm"      # Custom HTTP
    HAZI_HINAM = "hazi_hinam"        # Custom HTTP
    WOLT = "wolt"               # Custom HTTP
    MESHNAT_YOSEF_WEB = "meshnat_yosef_web"  # Cloudflare Workers
    NETIV_HASED = "netiv_hased"  # Direct IP HTTP


class FileType(Enum):
    STORE = "stores"
    PRICE = "price"
    PROMO = "promo"
    PRICE_FULL = "pricefull"
    PROMO_FULL = "promofull"


# ──────────────────────────────────────────────
# Cerberus FTP chains (url.retail.publishedprices.co.il)
# ──────────────────────────────────────────────
CERBERUS_HOST = "url.retail.publishedprices.co.il"

CERBERUS_CHAINS = [
    {
        "name": "Rami Levy",
        "name_he": "רמי לוי",
        "chain_id": "7290058140886",
        "ftp_username": "RamiLevi",
    },
    {
        "name": "Cofix",
        "name_he": "קופיקס",
        "chain_id": "7291056200008",
        "ftp_username": "SuperCofixApp",
    },
    {
        "name": "Dor Alon",
        "name_he": "דור אלון",
        "chain_id": ["7290492000005", "729049000005"],
        "ftp_username": "doralon",
    },
    {
        "name": "Keshet Taamim",
        "name_he": "קשת טעמים",
        "chain_id": "7290785400000",
        "ftp_username": "Keshet",
    },
    {
        "name": "Polizer",
        "name_he": "פוליצר",
        "chain_id": "7291059100008",
        "ftp_username": "politzer",
    },
    {
        "name": "Salach Dabach",
        "name_he": "סאלח דבאח",
        "chain_id": "7290526500006",
        "ftp_username": "SalachD",
        "ftp_password": "12345",
    },
    {
        "name": "Stop Market",
        "name_he": "סטופ מרקט",
        "chain_id": ["72906390", "7290639000004"],
        "ftp_username": "Stop_Market",
    },
    {
        "name": "Super Yuda",
        "name_he": "סופר יודה",
        "chain_id": ["7290058198450", "7290058177776"],
        "ftp_username": "yuda_ho",
        "ftp_password": "Yud@147",
        "ftp_path": "/Yuda",
    },
    {
        "name": "Fresh Market & Super Dosh",
        "name_he": "פרש מרקט וסופר דוש",
        "chain_id": "7290876100000",
        "ftp_username": "freshmarket",
    },
    {
        "name": "Tiv Taam",
        "name_he": "טיב טעם",
        "chain_id": "7290873255550",
        "ftp_username": "TivTaam",
    },
    {
        "name": "Yellow (Paz)",
        "name_he": "יילו",
        "chain_id": "7290644700005",
        "ftp_username": "Paz_bo",
        "ftp_password": "paz468",
    },
    {
        "name": "Yohananof",
        "name_he": "יוחננוף",
        "chain_id": "7290803800003",
        "ftp_username": "yohananof",
    },
    {
        "name": "Osher Ad",
        "name_he": "אושר עד",
        "chain_id": "7290103152017",
        "ftp_username": "osherad",
    },
]

# ──────────────────────────────────────────────
# Bina HTTP chains ({prefix}.binaprojects.com)
# ──────────────────────────────────────────────
BINA_DOMAIN = "binaprojects.com"

BINA_CHAINS = [
    {
        "name": "Bareket",
        "name_he": "ברקת",
        "chain_id": "7290875100001",
        "url_prefix": "superbareket",
    },
    {
        "name": "Good Pharm",
        "name_he": "גוד פארם",
        "chain_id": "7290058197699",
        "url_prefix": "goodpharm",
    },
    {
        "name": "King Store",
        "name_he": "קינג סטור",
        "chain_id": "7290058108879",
        "url_prefix": "kingstore",
    },
    {
        "name": "Maayan 2000",
        "name_he": "מעיין 2000",
        "chain_id": "7290058159628",
        "url_prefix": "maayan2000",
    },
    {
        "name": "Shefa Birkat Hashem",
        "name_he": "שפע ברכת השם",
        "chain_id": "7290058134977",
        "url_prefix": "shefabirkathashem",
    },
    {
        "name": "Shuk HaIr",
        "name_he": "שוק העיר",
        "chain_id": "7290058148776",
        "url_prefix": "shuk-hayir",
    },
    {
        "name": "Super Sapir",
        "name_he": "סופר ספיר",
        "chain_id": "7290058156016",
        "url_prefix": "supersapir",
    },
    {
        "name": "Zol VeBegadol",
        "name_he": "זול ובגדול",
        "chain_id": "7290058173198",
        "url_prefix": "zolvebegadol",
    },
    {
        "name": "Meshnat Yosef",
        "name_he": "משנת יוסף",
        "chain_id": ["5144744100001", "7290058289400"],
        "url_prefix": "ktshivuk",
    },
    {
        "name": "City Market Kiryat Gat",
        "name_he": "סיטי מרקט קרית גת",
        "chain_id": ["7290058288526", "7290058266241", "7290058288090"],
        "url_prefix": "citymarketkiryatgat",
    },
]

# ──────────────────────────────────────────────
# Shufersal (custom HTTP scraper)
# ──────────────────────────────────────────────
SHUFERSAL_CONFIG = {
    "name": "Shufersal",
    "name_he": "שופרסל",
    "chain_id": "7290027600007",
    "base_url": "https://prices.shufersal.co.il",
    "update_url": "https://prices.shufersal.co.il/FileObject/UpdateCategory",
    "categories": {
        FileType.STORE: "5",
        FileType.PRICE: "1",
        FileType.PROMO: "3",
        FileType.PRICE_FULL: "2",
        FileType.PROMO_FULL: "4",
    },
}

# ──────────────────────────────────────────────
# Matrix chains (laibcatalog.co.il)
# ──────────────────────────────────────────────
MATRIX_BASE_URL = "https://laibcatalog.co.il"

MATRIX_CHAINS = [
    {
        "name": "Het Cohen",
        "name_he": "ח. כהן",
        "chain_id": ["7290455000004"],
    },
    {
        "name": "Mahsanei HaShuk",
        "name_he": "מחסני השוק",
        "chain_id": ["7290661400001", "7290633800006"],
    },
]

# ──────────────────────────────────────────────
# Victory (REST API via laibcatalog.co.il)
# ──────────────────────────────────────────────
VICTORY_CONFIG = {
    "name": "Victory",
    "name_he": "ויקטורי",
    "chain_id": ["7290696200003", "7290058103393"],
    "base_url": "https://laibcatalog.co.il",
    "api_url": "https://laibcatalog.co.il/webapi/api/getfiles",
}

# ──────────────────────────────────────────────
# PublishPrice chains (prices.{infix}.co.il)
# ──────────────────────────────────────────────
PUBLISH_PRICE_CHAINS = [
    {
        "name": "Quik",
        "name_he": "קוויק",
        "chain_id": "7291029710008",
        "site_infix": "quik",
    },
]

# ──────────────────────────────────────────────
# Super Pharm (custom multi-page HTTP)
# ──────────────────────────────────────────────
SUPER_PHARM_CONFIG = {
    "name": "Super Pharm",
    "name_he": "סופר פארם",
    "chain_id": "7290172900007",
    "base_url": "http://prices.super-pharm.co.il",
}

# ──────────────────────────────────────────────
# Hazi Hinam (custom HTTP)
# ──────────────────────────────────────────────
HAZI_HINAM_CONFIG = {
    "name": "Hazi Hinam",
    "name_he": "חצי חינם",
    "chain_id": "7290700100008",
    "base_url": "https://shop.hazi-hinam.co.il/Prices",
}

# ──────────────────────────────────────────────
# Wolt
# ──────────────────────────────────────────────
WOLT_CONFIG = {
    "name": "Wolt",
    "name_he": "וולט",
    "chain_id": "7290058249350",
    "base_url": "https://wm-gateway.wolt.com/isr-prices/public/v1/index.html",
}

# ──────────────────────────────────────────────
# Meshnat Yosef (Cloudflare Workers)
# ──────────────────────────────────────────────
MESHNAT_YOSEF_WEB_CONFIG = {
    "name": "Meshnat Yosef (Web)",
    "name_he": "משנת יוסף",
    "chain_id": "5144744100002",
    "base_url": "https://list-files.w5871031-kt.workers.dev/",
}

# ──────────────────────────────────────────────
# Netiv HaHesed (direct IP)
# ──────────────────────────────────────────────
NETIV_HASED_CONFIG = {
    "name": "Netiv HaHesed",
    "name_he": "נתיב החסד",
    "chain_id": "7290058160839",
    "base_url": "http://141.226.203.152/",
}

# ──────────────────────────────────────────────
# City Market Shops (custom multi-page)
# ──────────────────────────────────────────────
CITY_MARKET_SHOPS_CONFIG = {
    "name": "City Market Shops",
    "name_he": "סיטי מרקט",
    "chain_id": "7290000000003",
    "base_url": "http://www.citymarket-shops.co.il/",
}


def get_all_chains():
    """Return a flat list of all chain configurations with their engine type."""
    chains = []

    for chain in CERBERUS_CHAINS:
        chains.append({**chain, "engine": Engine.CERBERUS})

    for chain in BINA_CHAINS:
        chains.append({**chain, "engine": Engine.BINA})

    chains.append({**SHUFERSAL_CONFIG, "engine": Engine.SHUFERSAL})

    for chain in MATRIX_CHAINS:
        chains.append({**chain, "engine": Engine.MATRIX})

    chains.append({**VICTORY_CONFIG, "engine": Engine.VICTORY_API})

    for chain in PUBLISH_PRICE_CHAINS:
        chains.append({**chain, "engine": Engine.PUBLISH_PRICE})

    chains.append({**SUPER_PHARM_CONFIG, "engine": Engine.SUPER_PHARM})
    chains.append({**HAZI_HINAM_CONFIG, "engine": Engine.HAZI_HINAM})
    chains.append({**WOLT_CONFIG, "engine": Engine.WOLT})
    chains.append({**MESHNAT_YOSEF_WEB_CONFIG, "engine": Engine.MESHNAT_YOSEF_WEB})
    chains.append({**NETIV_HASED_CONFIG, "engine": Engine.NETIV_HASED})
    chains.append({**CITY_MARKET_SHOPS_CONFIG, "engine": Engine.HAZI_HINAM})

    return chains
