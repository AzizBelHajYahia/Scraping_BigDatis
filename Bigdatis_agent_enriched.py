"""
╔══════════════════════════════════════════════════════════════════════════════╗
║       BIGDATIS — AGENT COLLECTE + ENRICHISSEMENT MUBAWAB (TOUT EN UN)      ║
║                                                                              ║
║  Pour chaque dataset :                                                       ║
║    1. Collecte les nouvelles annonces depuis l'API Bigdatis                  ║
║    2. Pour chaque nouvelle annonce, cherche une URL Mubawab dans "sources"   ║
║    3. Si URL Mubawab trouvée → scrape la page (Selenium) pour enrichir       ║
║    4. Sauvegarde les nouvelles annonces dans Supabase                         ║
║                                                                              ║
║  Chaque ligne stocke les colonnes Bigdatis + Mubawab (+ payload JSON)        ║
╚══════════════════════════════════════════════════════════════════════════════╝

Usage :
    python bigdatis_agent_enriched.py                        # tous les datasets
    python bigdatis_agent_enriched.py --only bureaux_sale    # un seul dataset
    python bigdatis_agent_enriched.py --skip terrain_agri    # exclure
    python bigdatis_agent_enriched.py --test                 # 10 annonces max
    python bigdatis_agent_enriched.py --supabase-table bigdatis_enriched_listings

Scheduling (toutes les 6h) :
    Linux/Mac → crontab -e → 0 */6 * * * python3 /chemin/bigdatis_agent_enriched.py
    Windows   → Planificateur de tâches → toutes les 6h
"""

import os
import sys
import re
import json
import time
import logging
import argparse
import requests
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

# Selenium + BeautifulSoup (pour enrichissement Mubawab)
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from bs4 import BeautifulSoup
from urllib.parse import urljoin


# ══════════════════════════════════════════════════════════════════════════════
#  CONFIGURATION DES DATASETS
#  → supabase_table : table de destination dans Supabase
# ══════════════════════════════════════════════════════════════════════════════

DATASETS = {
    "bureaux_rent": {
        "label":          "Bureaux — Location",
        "property_types": {"office": "Bureau"},
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "bureaux_sale": {
        "label":          "Bureaux — Vente",
        "property_types": {"office": "Bureau"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "commercial_rent": {
        "label":          "Locaux commerciaux — Location",
        "property_types": {"commercialPremise": "Local commercial"},
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "commercial_sale": {
        "label":          "Locaux commerciaux — Vente",
        "property_types": {"commercialPremise": "Local commercial"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "duplex_rent": {
        "label":          "Duplex/Triplex — Location",
        "property_types": {"duplex": "Duplex/Triplex"},
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "duplex_sale": {
        "label":          "Duplex/Triplex — Vente",
        "property_types": {"duplex": "Duplex/Triplex"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "villafloor_rent": {
        "label":          "RDC/Étage de villa — Location",
        "property_types": {"villaFloor": "RDC/Étage de villa"},
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "villafloor_sale": {
        "label":          "RDC/Étage de villa — Vente",
        "property_types": {"villaFloor": "RDC/Étage de villa"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "immeubles_rent": {
        "label":          "Immeubles — Location",
        "property_types": {
            "residentialBuilding": "Immeuble résidentiel",
            "officeBuilding":      "Immeuble de bureaux",
        },
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "immeubles_sale": {
        "label":          "Immeubles — Vente",
        "property_types": {
            "residentialBuilding": "Immeuble résidentiel",
            "officeBuilding":      "Immeuble de bureaux",
        },
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "terrain_const": {
        "label":          "Terrains constructibles — Vente",
        "property_types": {"buildingLot": "Terrain constructible"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "terrain_agri": {
        "label":          "Terrains agricoles — Vente",
        "property_types": {"farmland": "Terrain agricole"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "house_rent": {
        "label":          "Maisons — Location",
        "property_types": {"house": "Maison"},
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "house_sale": {
        "label":          "Maisons — Vente",
        "property_types": {"house": "Maison"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
    },
    "apartment_rent": {
        "label":          "Appartements — Location",
        "property_types": {"apartment": "Appartement"},
        "transaction":    "rental",
        "supabase_table": "bigdatis_enriched_listings",
},
    "apartment_sale": {
        "label":          "Appartements — Vente",
        "property_types": {"apartment": "Appartement"},
        "transaction":    "sale",
        "supabase_table": "bigdatis_enriched_listings",
},
}

# Colonnes ajoutées par l'enrichissement Mubawab (dans l'ordre du CSV enrichi)
MUBAWAB_COLS = [
    "mubawab_url", "property_id", "reference", "title_scraped", "type_scraped",
    "transaction_type_scraped", "price_scraped", "price_numeric", "price_per_m2",
    "currency", "location", "city", "neighbourhood", "latitude", "longitude",
    "google_maps_url", "area_m2", "rooms", "bedrooms", "bathrooms", "floor",
    "total_floors", "furnished", "condition", "construction_year", "amenities",
    "image_count_scraped", "image_urls_scraped", "video_url", "agency_name",
    "agency_url", "agent_name", "phone_numbers", "date_posted", "date_updated",
    "description_scraped", "page_load_method", "enriched_at",
]

AMENITIES_LIST = [
    'Piscine', 'Ascenseur', 'Terrasse', 'Balcon', 'Jardin', 'Garage',
    'Parking', 'Climatisation', 'Chauffage central', 'Chauffage',
    'Meublé', 'Cuisine équipée', 'Concierge', 'Gardien', 'Sécurité',
    'Interphone', 'Digicode', 'Vue sur mer', 'Vue sur lac', 'Vue sur montagne',
    'Proche mer', 'Proche lac', 'Proche école', 'Proche commerce',
    'Accès handicapé', 'Fibre optique', 'Double vitrage', 'Cave',
    'Buanderie', 'Dressing', 'Cheminée', 'Sauna', 'Jacuzzi',
    'Salle de sport', 'Garderie', 'Divertissement',
]

SEARCH_URL = "https://server.bigdatis.tn/api/properties/search"
DETAIL_URL = "https://server.bigdatis.tn/api/properties/show"
LOG_DIR    = "logs"
SUPABASE_DEFAULT_TABLE = "bigdatis_enriched_listings"

BIGDATIS_HEADERS = {
    "User-Agent":   "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Content-Type": "application/json",
    "Accept":       "application/json",
    "Origin":       "https://bigdatis.tn",
    "Referer":      "https://bigdatis.tn/",
}


def _load_supabase_config(table_name: str | None = None) -> dict:
    load_dotenv()
    supabase_url = os.getenv("SUPABASE_URL", "").rstrip("/")
    supabase_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY") or os.getenv("SUPABASE_ANON_KEY")
    resolved_table = table_name or os.getenv("SUPABASE_TABLE") or SUPABASE_DEFAULT_TABLE

    if not supabase_url:
        raise RuntimeError("SUPABASE_URL is missing. Set it in the environment or .env file.")
    if not supabase_key:
        raise RuntimeError(
            "SUPABASE_SERVICE_ROLE_KEY or SUPABASE_ANON_KEY is missing. Set one of them in the environment or .env file."
        )

    return {
        "url": supabase_url,
        "key": supabase_key,
        "table": resolved_table,
    }


def _supabase_headers(cfg: dict) -> dict:
    return {
        "apikey": cfg["key"],
        "Authorization": f"Bearer {cfg['key']}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }


def _supabase_api_url(cfg: dict, path: str) -> str:
    return f"{cfg['url']}/rest/v1/{path.lstrip('/')}"


def _load_existing_ids_supabase(cfg: dict, dataset_key: str) -> set:
    ids = set()
    offset = 0
    page_size = 1000

    while True:
        response = requests.get(
            _supabase_api_url(cfg, cfg["table"]),
            headers=_supabase_headers(cfg),
            params={
                "select": "bigdatis_id",
                "dataset_key": f"eq.{dataset_key}",
                "limit": str(page_size),
                "offset": str(offset),
            },
            timeout=30,
        )
        if response.status_code not in (200, 206):
            raise RuntimeError(
                f"Supabase read failed for {dataset_key}: {response.status_code} {response.text[:200]}"
            )

        rows = response.json() or []
        for row in rows:
            value = row.get("bigdatis_id")
            if value is not None:
                ids.add(str(value))

        if len(rows) < page_size:
            break
        offset += page_size

    logging.info(f"  Supabase existant : {len(ids):,} annonces déjà enregistrées")
    return ids


def _to_supabase_record(row: dict, dataset_key: str) -> dict:
    # Flatten all listing fields into table columns while keeping full payload.
    flattened = dict(row)
    flattened.pop("id", None)

    return {
        **flattened,
        "dataset_key": dataset_key,
        "bigdatis_id": row.get("id"),
        "payload": row,
    }


def _to_supabase_record_minimal(row: dict, dataset_key: str) -> dict:
    return {
        "dataset_key": dataset_key,
        "bigdatis_id": row.get("id"),
        "mubawab_url": row.get("mubawab_url"),
        "enriched_at": row.get("enriched_at"),
        "scraped_at": row.get("scraped_at"),
        "payload": row,
    }


def _upsert_rows_supabase(cfg: dict, rows: list, dataset_key: str):
    if not rows:
        return

    use_flatten = os.getenv("SUPABASE_FLATTEN_COLUMNS", "1") != "0"
    records = [_to_supabase_record(row, dataset_key) for row in rows] if use_flatten else [
        _to_supabase_record_minimal(row, dataset_key) for row in rows
    ]

    response = requests.post(
        _supabase_api_url(cfg, cfg["table"]),
        headers={**_supabase_headers(cfg), "Prefer": "resolution=merge-duplicates,return=minimal"},
        params={"on_conflict": "dataset_key,bigdatis_id"},
        json=records,
        timeout=60,
    )

    # Backward compatibility with old minimal schema.
    if use_flatten and response.status_code >= 400 and "does not exist" in (response.text or ""):
        logging.warning(
            "  ⚠ Colonnes manquantes dans la table Supabase pour mode flatten. "
            "Fallback vers schema minimal (payload)."
        )
        response = requests.post(
            _supabase_api_url(cfg, cfg["table"]),
            headers={**_supabase_headers(cfg), "Prefer": "resolution=merge-duplicates,return=minimal"},
            params={"on_conflict": "dataset_key,bigdatis_id"},
            json=[_to_supabase_record_minimal(row, dataset_key) for row in rows],
            timeout=60,
        )

    if response.status_code not in (200, 201, 204):
        raise RuntimeError(
            f"Supabase write failed for {dataset_key}: {response.status_code} {response.text[:300]}"
        )

    logging.info(f"  💾 {len(records):,} ligne(s) envoyée(s) vers Supabase → {cfg['table']}")


# ══════════════════════════════════════════════════════════════════════════════
#  LOGGING
# ══════════════════════════════════════════════════════════════════════════════

def setup_logging() -> str:
    os.makedirs(LOG_DIR, exist_ok=True)
    log_file = os.path.join(LOG_DIR, f"agent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler(log_file, encoding="utf-8"),
            logging.StreamHandler(sys.stdout),
        ],
    )
    return log_file


# ══════════════════════════════════════════════════════════════════════════════
#  BIGDATIS HTTP HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _post(payload: dict, retries=3, base_delay=2.0):
    for attempt in range(retries):
        try:
            r = requests.post(SEARCH_URL, headers=BIGDATIS_HEADERS, json=payload, timeout=30)
            if r.status_code == 429:
                wait = base_delay * (2 ** attempt)
                logging.warning(f"429 rate-limit → attente {wait:.0f}s")
                time.sleep(wait); continue
            if r.status_code == 500:
                # Erreur serveur permanente — inutile de réessayer indéfiniment
                logging.warning(f"Erreur POST: 500 Server Error (tentative {attempt+1}/{retries})")
                if attempt < retries - 1:
                    time.sleep(base_delay * (2 ** attempt))
                continue
            r.raise_for_status()
            return r.json()
        except requests.exceptions.Timeout:
            logging.warning(f"Timeout POST (tentative {attempt+1}/{retries})")
            time.sleep(base_delay * (2 ** attempt))
        except requests.exceptions.HTTPError:
            raise  # déjà loggé au-dessus
        except Exception as e:
            logging.warning(f"Erreur POST: {str(e)[:60]}")
            time.sleep(base_delay * (2 ** attempt))
    return None


def _get_detail(pid, retries=5, base_delay=2.0):
    url = f"{DETAIL_URL}/{pid}"
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=BIGDATIS_HEADERS, timeout=20)
            if r.status_code == 429:
                time.sleep(base_delay * (2 ** attempt)); continue
            if r.status_code != 200:
                time.sleep(base_delay * (2 ** attempt)); continue
            data = r.json()
            if not isinstance(data, dict) or "id" not in data:
                time.sleep(base_delay * (2 ** attempt)); continue
            return data
        except Exception as e:
            logging.warning(f"Erreur GET detail {pid}: {str(e)[:60]}")
            time.sleep(base_delay * (2 ** attempt))
    return None


def _get_sources(pid, retries=5, base_delay=2.0):
    url = f"{DETAIL_URL}/{pid}/sources"
    for attempt in range(retries):
        try:
            r = requests.get(url, headers=BIGDATIS_HEADERS, timeout=20)
            if r.status_code == 429:
                time.sleep(base_delay * (2 ** attempt)); continue
            if r.status_code != 200:
                time.sleep(base_delay * (2 ** attempt)); continue
            data = r.json()
            if isinstance(data, list):
                return data
            time.sleep(base_delay * (2 ** attempt))
        except Exception:
            time.sleep(base_delay * (2 ** attempt))
    return None


def make_payload(property_type: str, transaction: str, page: int, limit: int = 100) -> dict:
    return {
        "filter": {
            "agencies": [],
            "area":     {"min": None, "max": None, "excludeMissing": False},
            "contactHasPhone": False,
            "excludedFlags":   [],
            "includedFlags":   [],
            "location":        {"id": None, "additionalIds": []},
            "price":           {"min": None, "max": None, "excludeMissing": False},
            "propertyFilters": [
                {"property": "transactionType", "values": [transaction]},
                {"property": "propertyType",    "values": [property_type]},
            ],
        },
        "orderBy": "date",
        "page":    page,
        "limit":   limit,
    }


# ══════════════════════════════════════════════════════════════════════════════
#  EXTRACTION URL MUBAWAB depuis le champ "sources" de Bigdatis
# ══════════════════════════════════════════════════════════════════════════════

def extract_mubawab_url(sources_raw) -> str | None:
    """
    Cherche une URL Mubawab dans le champ 'sources' d'une annonce Bigdatis.
    sources_raw peut être une liste de dicts ou une string JSON.
    """
    if not sources_raw:
        return None
    try:
        if isinstance(sources_raw, str):
            sources = json.loads(sources_raw)
        else:
            sources = sources_raw
        for src in sources:
            url = src.get("url") or ""
            if "mubawab.tn" in url:
                return url
    except Exception:
        pass
    return None


# ══════════════════════════════════════════════════════════════════════════════
#  SELENIUM DRIVER (partagé sur tout le run)
# ══════════════════════════════════════════════════════════════════════════════

class SeleniumDriver:
    """Wrapper autour de Firefox Selenium — ouvert une seule fois par run."""

    def __init__(self, headless: bool = True):
        self.driver = None
        self.headless = headless

    def start(self):
        options = webdriver.FirefoxOptions()
        if self.headless:
            options.add_argument("--headless")
        options.set_preference(
            "general.useragent.override",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
        )
        self.driver = webdriver.Firefox(options=options)
        self.driver.set_page_load_timeout(30)
        self.driver.implicitly_wait(10)
        logging.info("🦊 Firefox démarré")

    def stop(self):
        if self.driver:
            self.driver.quit()
            self.driver = None
            logging.info("🦊 Firefox fermé")

    def get_soup(self, url: str):
        """Charge l'URL avec Selenium et retourne un BeautifulSoup JS-rendu."""
        try:
            self.driver.get(url)
            WebDriverWait(self.driver, 15).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            time.sleep(2)
            return BeautifulSoup(self.driver.page_source, "html.parser")
        except Exception as e:
            logging.warning(f"Selenium load error ({url[:60]}): {e}")
            return None


# ══════════════════════════════════════════════════════════════════════════════
#  ENRICHISSEMENT MUBAWAB  (extraction de tous les champs depuis la page)
# ══════════════════════════════════════════════════════════════════════════════

def _extract_coordinates(soup):
    """Extrait lat/lng depuis la page JS-rendue (5 méthodes successives)."""
    # Méthode 1 : hidden inputs
    lat_f = soup.find("input", {"id": "latField"})
    lng_f = soup.find("input", {"id": "lngField"})
    if lat_f and lng_f:
        try:
            lat, lng = float(lat_f.get("value", "")), float(lng_f.get("value", ""))
            if 30.0 <= lat <= 40.0 and 7.0 <= lng <= 12.0:
                return lat, lng
        except (ValueError, TypeError):
            pass

    # Méthode 2 : let lat = Number(...)
    for script in soup.find_all("script", type="text/javascript"):
        src = script.string or ""
        if "let lat" not in src:
            continue
        lm = re.search(r"let\s+lat\s*=\s*Number\(([-\d.]+)\)", src)
        nm = re.search(r"let\s+lon\s*=\s*Number\(([-\d.]+)\)", src)
        if lm and nm:
            try:
                lat, lng = float(lm.group(1)), float(nm.group(1))
                if 30.0 <= lat <= 40.0 and 7.0 <= lng <= 12.0:
                    return lat, lng
            except (ValueError, TypeError):
                pass

    # Méthode 3 : patterns JSON dans scripts
    for script in soup.find_all("script"):
        text = script.string or ""
        for pat in [
            r'"latitude"\s*:\s*"?([-\d.]+)"?\s*,\s*"longitude"\s*:\s*"?([-\d.]+)"?',
            r'"lat"\s*:\s*"?([-\d.]+)"?\s*,\s*"l(?:ng|on)"\s*:\s*"?([-\d.]+)"?',
            r'new\s+google\.maps\.LatLng\(([-\d.]+)\s*,\s*([-\d.]+)\)',
        ]:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                try:
                    lat, lng = float(m.group(1)), float(m.group(2))
                    if 30.0 <= lat <= 40.0 and 7.0 <= lng <= 12.0:
                        return lat, lng
                except (ValueError, IndexError):
                    pass

    return None, None


def _extract_amenities(soup) -> list:
    """Extrait les équipements depuis la page JS-rendue."""
    parts = []
    container_classes = re.compile(
        r"adEquipment|equipement|listEquipments|amenities|options|"
        r"criteriaList|adFeature|adCriteria|adCarac|caracteristique|facilities",
        re.I
    )
    for tag in soup.find_all(class_=container_classes):
        parts.append(tag.get_text(" ", strip=True))
    for el in soup.find_all(["li", "span", "p"]):
        raw = el.get_text(" ", strip=True)
        if 3 <= len(raw) <= 80 and not re.search(r"TND|DT|€|\d{4,}", raw):
            parts.append(raw)
    parts.append(soup.get_text(" ", strip=True))
    combined = " | ".join(parts)

    found = []
    for kw in sorted(AMENITIES_LIST, key=len, reverse=True):
        pattern = r"(?<![A-Za-zÀ-ÿ])" + re.escape(kw) + r"(?![A-Za-zÀ-ÿ])"
        if re.search(pattern, combined, re.IGNORECASE):
            found.append(kw)
    return found


def scrape_mubawab_page(url: str, selenium: SeleniumDriver) -> dict:
    """
    Scrape une page Mubawab avec Selenium et retourne un dict
    avec toutes les colonnes MUBAWAB_COLS remplies.
    """
    result = {col: None for col in MUBAWAB_COLS}
    result["mubawab_url"] = url
    result["enriched_at"] = datetime.now().isoformat()

    soup = selenium.get_soup(url)
    if not soup:
        result["page_load_method"] = "failed"
        return result

    result["page_load_method"] = "static+selenium"
    full_text = soup.get_text(" ", strip=True)

    # ── property_id ──────────────────────────────────────────────────────────
    id_m = re.search(r"/(?:a|pa)/(\d+)/", url)
    if id_m:
        result["property_id"] = int(id_m.group(1))

    # ── reference ────────────────────────────────────────────────────────────
    ref_m = re.search(r"[Rr]éf\.?\s*[:#]?\s*([A-Z0-9][A-Z0-9\-]{3,})", full_text)
    if ref_m:
        val = ref_m.group(1)
        if any(c.isdigit() for c in val):
            result["reference"] = val

    # ── title ────────────────────────────────────────────────────────────────
    h1 = soup.find("h1")
    if h1:
        result["title_scraped"] = h1.get_text(strip=True)

    # ── transaction_type + type ───────────────────────────────────────────────
    title_lower = (result["title_scraped"] or "").lower()
    if "louer" in title_lower or "location" in title_lower:
        result["transaction_type_scraped"] = "Location"
    elif "vendre" in title_lower or "vente" in title_lower:
        result["transaction_type_scraped"] = "Vente"

    for ptype in ["Appartement", "Villa", "Studio", "Duplex", "Penthouse",
                  "Rez-de-chaussée", "Maison", "Bureau", "Local", "Terrain"]:
        if ptype.lower() in title_lower:
            result["type_scraped"] = ptype
            break

    # ── price ────────────────────────────────────────────────────────────────
    price_tag = soup.find("h3", class_=re.compile(r"orangeTit", re.I))
    if not price_tag:
        price_tag = soup.find(class_=re.compile(r"price", re.I))
    if price_tag:
        price_text = price_tag.get_text(strip=True)
        pm = re.search(r"([\d][\d\s\.]*(?:TND|EUR|€|DT))", price_text)
        result["price_scraped"] = pm.group(1).strip() if pm else price_text
        num_str = re.sub(r"[^\d]", "", pm.group(1) if pm else price_text)
        if num_str.isdigit():
            result["price_numeric"] = int(num_str)
        result["currency"] = "TND" if ("TND" in price_text or "DT" in price_text) else (
            "EUR" if ("€" in price_text or "EUR" in price_text) else None
        )

    # ── location ──────────────────────────────────────────────────────────────
    loc_tag = soup.find(class_=re.compile(r"greyTit", re.I))
    if loc_tag:
        result["location"] = re.sub(r"\s+", " ", loc_tag.get_text(" ", strip=True)).strip()
    if result["location"]:
        parts = re.split(r"\s+à\s+", result["location"], maxsplit=1)
        if len(parts) == 2:
            result["neighbourhood"] = parts[0].strip()
            result["city"]          = parts[1].strip()
        else:
            result["city"] = result["location"]

    # ── coordinates ───────────────────────────────────────────────────────────
    lat, lng = _extract_coordinates(soup)
    result["latitude"]  = lat
    result["longitude"] = lng
    if lat and lng:
        result["google_maps_url"] = f"https://www.google.com/maps?q={lat},{lng}"

    # ── size & layout ─────────────────────────────────────────────────────────
    candidate_blocks = []
    for tag in soup.find_all(class_=re.compile(
        r"adMainFeature|criteriaList|featureList|adFeature|adDetails|adCriteria|adCarac|specs",
        re.I
    )):
        candidate_blocks.append(tag.get_text(" ", strip=True))
    for li in soup.find_all("li"):
        t = li.get_text(" ", strip=True)
        if re.search(r"m²|[Pp]ièces?|[Cc]hambres?|[Ss]alles?\s*de\s*bain|[Éé]tage", t):
            candidate_blocks.append(t)
    search_text = " ".join(candidate_blocks) if candidate_blocks else full_text

    size_patterns = {
        "area_m2":    [r"(\d[\d\s]*[\.,]?\d*)\s*m²", r"[Ss]uperficie\s*[:\-]?\s*(\d+)"],
        "rooms":      [r"(\d+)\s*[Pp]ièces?"],
        "bedrooms":   [r"(\d+)\s*[Cc]hambres?"],
        "bathrooms":  [r"(\d+)\s*[Ss]alles?\s*(?:de\s*)?[Bb]ains?", r"(\d+)\s*SDB"],
        "floor":      [r"[Éé]tage\s*[:\-]?\s*(\d+)", r"(\d+)\s*(?:er|ème|e)\s*[Éé]tage"],
        "total_floors": [r"(?:sur|/)\s*(\d+)\s*[Éé]tages?"],
        "construction_year": [r"[Aa]nn[ée]e\s*(?:de\s*)?[Cc]onstruction\s*[:\-]?\s*(20\d\d|19\d\d)"],
    }
    for key, pats in size_patterns.items():
        for pat in pats:
            mm = re.search(pat, search_text, re.IGNORECASE)
            if mm:
                val = mm.group(1).replace(",", ".").replace("\u00a0", "").replace(" ", "")
                result[key] = val
                break

    if result.get("price_numeric") and result.get("area_m2"):
        try:
            result["price_per_m2"] = round(int(result["price_numeric"]) / float(result["area_m2"]), 1)
        except (ValueError, ZeroDivisionError):
            pass

    # ── furnished ─────────────────────────────────────────────────────────────
    if re.search(r"\b(?:non[- ]meublé|vide)\b", full_text, re.I):
        result["furnished"] = "Non meublé"
    elif re.search(r"\bmeublé\b", full_text, re.I):
        result["furnished"] = "Meublé"

    # ── condition ─────────────────────────────────────────────────────────────
    for cond in ["Neuf", "Bon état", "À rénover", "En construction", "Sur plan"]:
        if re.search(r"(?:^|[\s:;,|>])" + re.escape(cond) + r"(?:$|[\s:;,|<])",
                     search_text, re.IGNORECASE):
            result["condition"] = cond
            break

    # ── amenities ─────────────────────────────────────────────────────────────
    found_amenities = _extract_amenities(soup)
    if found_amenities:
        result["amenities"] = "; ".join(found_amenities)

    # ── images ────────────────────────────────────────────────────────────────
    image_urls = []
    for img in soup.find_all("img"):
        for attr in ("src", "data-src", "data-lazy-src", "data-original"):
            src = (img.get(attr) or "").strip()
            if src and "mubawab-media.com/ad/" in src:
                full_img = src if src.startswith("http") else urljoin("https://www.mubawab.tn", src)
                if full_img not in image_urls:
                    image_urls.append(full_img)
                break
    property_images = [u for u in dict.fromkeys(image_urls)
                       if not re.search(r"/(business|promotion|assets)/", u, re.I)]
    result["image_count_scraped"] = len(property_images)
    result["image_urls_scraped"]  = " | ".join(property_images) if property_images else None

    # ── video ─────────────────────────────────────────────────────────────────
    video = soup.find("iframe", src=re.compile(r"youtube|vimeo|video", re.I))
    if video:
        result["video_url"] = video.get("src", "")

    # ── agency ────────────────────────────────────────────────────────────────
    agency_img = soup.find("img", src=re.compile(r"/(business|promotion)/", re.I))
    if agency_img:
        alt = (agency_img.get("alt") or "").strip()
        if alt and alt.lower() not in ("", "logo", "agency", "agence"):
            result["agency_name"] = alt
    if not result["agency_name"]:
        for tag in soup.find_all(class_=re.compile(r"agencyName|agenceName|promoteur|agence", re.I)):
            txt = tag.get_text(strip=True)
            if txt:
                result["agency_name"] = txt
                break

    agency_link = soup.find("a", href=re.compile(r"/fr/(?:ic|ag|promoteur)/", re.I))
    if agency_link:
        href = agency_link.get("href", "")
        result["agency_url"] = href if href.startswith("http") else "https://www.mubawab.tn" + href

    for tag in soup.find_all(class_=re.compile(r"agentName|sellerName|vendeur", re.I)):
        txt = tag.get_text(strip=True)
        if txt:
            result["agent_name"] = txt
            break

    # ── phones ────────────────────────────────────────────────────────────────
    raw_phones = re.findall(
        r"(?:\+?216[\s\-]?)?(?:2\d|5\d|7\d|9\d)[\s\-]?\d{3}[\s\-]?\d{3}", full_text
    )
    seen_ph, phones = set(), []
    for p in raw_phones:
        digits = re.sub(r"[\s\-]", "", re.sub(r"^\+?216", "", p))
        if digits not in seen_ph and len(digits) == 8:
            seen_ph.add(digits)
            phones.append(re.sub(r"[\s\-]", "", p))
    if phones:
        result["phone_numbers"] = " | ".join(phones)

    # ── dates ─────────────────────────────────────────────────────────────────
    pub_meta = soup.find("meta", property=re.compile(r"article:published_time", re.I))
    if pub_meta:
        result["date_posted"] = pub_meta.get("content", "")
    mod_meta = soup.find("meta", property=re.compile(r"article:modified_time", re.I))
    if mod_meta:
        result["date_updated"] = mod_meta.get("content", "")

    # ── description ───────────────────────────────────────────────────────────
    desc_tag = None
    for attr, val in [
        ("class", re.compile(r"adDescription|descriptionAd|annonce[-_]desc|propertyDescription", re.I)),
        ("id",    re.compile(r"description|desc", re.I)),
    ]:
        desc_tag = soup.find("div", {attr: val})
        if desc_tag:
            break
    if desc_tag:
        result["description_scraped"] = re.sub(r"\s+", " ", desc_tag.get_text(" ", strip=True))[:1000]

    return result


# ══════════════════════════════════════════════════════════════════════════════
#  CONSTRUCTION D'UNE LIGNE BIGDATIS (37 colonnes de base)
# ══════════════════════════════════════════════════════════════════════════════

def process_annonce_bigdatis(
    annonce: dict,
    page: int,
    type_name: str,
    transaction: str,
    property_type_code: str | None = None,
) -> dict | None:
    """Transforme un objet JSON Bigdatis en dict plat (colonnes de base)."""
    try:
        properties = annonce.get("properties") or {}

        raw_sources = annonce.get("sources_with_urls") or annonce.get("sources") or []
        sources = []
        for src in raw_sources:
            entry = {
                "sourceId":     src.get("sourceId"),
                "url":          src.get("url"),
                "price":        src.get("price"),
                "sellerType":   src.get("sellerType"),
                "lastModified": None,
            }
            ts = src.get("lastModified")
            if ts:
                try:
                    entry["lastModified"] = datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    entry["lastModified"] = ts
            sources.append(entry)

        image_urls = []
        if isinstance(annonce.get("imageUrls"), list):
            image_urls = annonce["imageUrls"]
        elif isinstance(annonce.get("images"), list):
            for img in annonce["images"]:
                if isinstance(img, dict) and img.get("url"):
                    image_urls.append(img["url"])
                elif isinstance(img, str):
                    image_urls.append(img)

        images_detailed = []
        if isinstance(annonce.get("images"), list):
            for img in annonce["images"]:
                if isinstance(img, dict):
                    images_detailed.append({
                        "url":      img.get("url"),
                        "sourceId": img.get("sourceId"),
                        "adUrl":    img.get("adUrl"),
                    })

        contacts = []
        for c in (annonce.get("contacts") or []):
            contacts.append({
                "sellerType":  c.get("sellerType"),
                "contactName": c.get("contactName"),
                "active":      c.get("active"),
            })

        def clean(val):
            if val is None: return None
            s = str(val).strip()
            return s if s else None

        def ts_to_str(ts):
            if not ts: return None
            try:    return datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")
            except: return None

        def json_or_none(obj):
            if not obj: return None
            s = json.dumps(obj, ensure_ascii=False)
            return None if s in ("[]", "{}", "null") else s

        typo = clean(properties.get("typology"))

        return {
            "id":                    annonce.get("id"),
            "ids_alt":               json_or_none(annonce.get("idsAlt")),
            "titre":                 clean(annonce.get("title")),
            "description":           clean(annonce.get("description")),
            "prix":                  annonce.get("price"),
            "surface":               annonce.get("area"),
            "typologie":             typo.upper() if typo else None,
            "type_bien":             type_name,
            "property_listing_type": type_name,
            "type_bien_code":        properties.get("propertyType"),
            "property_listing_type_code": property_type_code or properties.get("propertyType"),
            "type_transaction":      properties.get("transactionType", transaction),
            "type_vendeur":          properties.get("sellerType"),
            "seller_types":          json_or_none(annonce.get("sellerTypes")),
            "location_id":           annonce.get("locationId"),
            "thumbnail_url":         clean(annonce.get("thumbnailUrl")),
            "image_urls":            json_or_none(image_urls),
            "images_detailed":       json_or_none(images_detailed),
            "nb_images":             len(image_urls),
            "sources":               json_or_none(sources),
            "contacts":              json_or_none(contacts),
            "flags":                 json_or_none(annonce.get("flags") or []),
            "nb_sources":            len(sources),
            "nb_sources_with_urls":  len([s for s in sources if s.get("url")]),
            "nb_sources_total":      annonce.get("sourcesCount", 0),
            "nb_sources_actifs":     annonce.get("activeSourcesCount", 0),
            "nb_contacts":           len(contacts),
            "nb_contacts_actifs":    annonce.get("activeContactsCount", 0),
            "nb_ads_total":          annonce.get("adsCount", 0),
            "nb_ads_actifs":         annonce.get("activeAdsCount", 0),
            "nb_commentaires":       annonce.get("commentsCount", 0),
            "first_seen_at":         ts_to_str(annonce.get("firstSeenAt")),
            "created_at":            ts_to_str(annonce.get("createdAt")),
            "modified_at":           ts_to_str(annonce.get("modifiedAt")),
            "price_dropped_at":      ts_to_str(annonce.get("priceDroppedAt")),
            "timestamp":             ts_to_str(annonce.get("timestamp")),
            "prix_timestamp":        ts_to_str(annonce.get("priceTimestamp")),
            "page":                  page,
            "scraped_at":            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            # colonnes Mubawab initialisées à None (remplies ensuite si URL trouvée)
            **{col: None for col in MUBAWAB_COLS},
        }
    except Exception as e:
        logging.error(f"process_annonce_bigdatis error (id={annonce.get('id')}): {e}")
        return None


# ══════════════════════════════════════════════════════════════════════════════
#  CORE : surveille UN dataset
# ══════════════════════════════════════════════════════════════════════════════

def run_dataset(dataset_key: str, cfg: dict, supabase_cfg: dict,
                test_mode: bool, selenium: SeleniumDriver) -> dict:
    label        = cfg["label"]
    property_map = cfg["property_types"]
    transaction  = cfg["transaction"]
    table_name   = cfg.get("supabase_table") or supabase_cfg["table"]
    max_props    = 10 if test_mode else float("inf")
    checkpoint_size = max(1, int(os.getenv("SUPABASE_CHECKPOINT_SIZE", "20")))

    logging.info(f"\n{'═'*65}")
    logging.info(f"  📂  {label.upper()}")
    logging.info(f"{'═'*65}")

    start_time        = time.time()
    existing_ids      = _load_existing_ids_supabase({**supabase_cfg, "table": table_name}, dataset_key)
    new_rows          = []
    saved_count       = 0
    detail_fails      = 0
    api_errors        = 0
    mubawab_enriched  = 0

    for prop_code, prop_name in property_map.items():
        logging.info(f"\n  🏷  {prop_code} ({prop_name}) | {transaction}")

        seen_ids = set()
        page     = 1

        while len(new_rows) < max_props:
            logging.info(f"  📡 Page {page}…")
            base_payload = make_payload(prop_code, transaction, page)
            result = _post(base_payload)

            # Repli automatique sur limit réduit si le serveur répond 500
            if result is None:
                logging.warning(f"  ⚠ Échec limit=100 → tentative limit=50…")
                result = _post(make_payload(prop_code, transaction, page, limit=50))
            if result is None:
                logging.warning(f"  ⚠ Échec limit=50 → tentative limit=20…")
                result = _post(make_payload(prop_code, transaction, page, limit=20))
            if result is None:
                api_errors += 1
                logging.error(
                    f"  Échec page {page} après tous les replis — arrêt du dataset\n"
                    f"  ℹ  Le serveur Bigdatis retourne 500 pour ce type de propriété.\n"
                    f"  ℹ  Ce n'est pas un bug du script — réessayez plus tard."
                )
                break

            annonces = result.get("results", []) if isinstance(result, dict) else result
            if not annonces:
                logging.info("  Page vide — fin de pagination")
                break

            truly_new = [
                a for a in annonces
                if str(a.get("id")) not in existing_ids
                and str(a.get("id")) not in seen_ids
            ]
            seen_ids.update(str(a.get("id")) for a in annonces)

            logging.info(f"  Page {page} : {len(annonces)} | {len(truly_new)} nouvelles")

            if page > 1 and not truly_new:
                logging.info("  Aucune nouvelle → arrêt anticipé")
                break

            for annonce in truly_new:
                if len(new_rows) >= max_props:
                    break

                pid = annonce.get("id")
                logging.info(f"    → ID {pid}")

                # ── 1. Détail Bigdatis ────────────────────────────────────
                detail = _get_detail(pid)
                if not detail:
                    logging.warning(f"    ✗ Détail introuvable — ignoré")
                    detail_fails += 1
                    time.sleep(1.0)
                    continue
                annonce = detail
                time.sleep(1.0)

                # ── 2. Sources Bigdatis ───────────────────────────────────
                sources_data = _get_sources(pid)
                if sources_data:
                    annonce["sources_with_urls"] = sources_data
                time.sleep(1.0)

                # ── 3. Construction ligne de base ─────────────────────────
                row = process_annonce_bigdatis(
                    annonce,
                    page,
                    prop_name,
                    transaction,
                    property_type_code=prop_code,
                )
                if not row:
                    logging.error(f"    ✗ process_annonce_bigdatis échoué")
                    continue

                # ── 4. Enrichissement Mubawab (si URL trouvée) ────────────
                mubawab_url = extract_mubawab_url(sources_data or annonce.get("sources"))
                if mubawab_url:
                    logging.info(f"    🔍 Mubawab URL trouvée → scrape…")
                    mubawab_data = scrape_mubawab_page(mubawab_url, selenium)
                    # Fusionner les colonnes Mubawab dans la ligne
                    for col in MUBAWAB_COLS:
                        row[col] = mubawab_data.get(col)
                    mubawab_enriched += 1
                    lat = row.get("latitude")
                    logging.info(
                        f"    ✓ Enrichi | ville:{row.get('city','—')} | "
                        f"coords:{'✓' if lat else '✗'} | "
                        f"équip:{len((row.get('amenities') or '').split(';')) if row.get('amenities') else 0}"
                    )
                    time.sleep(2.0)
                else:
                    logging.info(f"    — Pas d'URL Mubawab (sources: {len(sources_data or [])})")

                new_rows.append(row)

                # Checkpoint Supabase périodique pour limiter la mémoire et éviter la perte en cas d'arrêt.
                if len(new_rows) - saved_count >= checkpoint_size:
                    _upsert_rows_supabase(
                        {**supabase_cfg, "table": table_name},
                        new_rows[saved_count:len(new_rows)],
                        dataset_key,
                    )
                    saved_count = len(new_rows)

            if len(annonces) < 100:
                logging.info("  Dernière page atteinte")
                break

            page += 1
            time.sleep(2.0)

    # Sauvegarde finale (reste après le dernier checkpoint).
    if saved_count < len(new_rows):
        _upsert_rows_supabase({**supabase_cfg, "table": table_name}, new_rows[saved_count:], dataset_key)

    elapsed = time.time() - start_time
    return {
        "dataset":          dataset_key,
        "label":            label,
        "table":            table_name,
        "new_annonces":     len(new_rows),
        "existing_before":  len(existing_ids),
        "mubawab_enriched": mubawab_enriched,
        "detail_fails":     detail_fails,
        "api_errors":       api_errors,
        "duration_s":       round(elapsed, 1),
    }


# ══════════════════════════════════════════════════════════════════════════════
#  RAPPORT GLOBAL
# ══════════════════════════════════════════════════════════════════════════════

def print_global_report(all_stats: list, total_elapsed: float):
    sep = "═" * 78
    logging.info(f"\n\n{sep}")
    logging.info("  📋  RAPPORT GLOBAL")
    logging.info(sep)
    logging.info(f"  {'Dataset':<22} {'Avant':>7} {'Nouveaux':>9} {'Après':>8} {'Mubawab':>8} {'Durée':>7}")
    logging.info(f"  {'─'*22} {'─'*7} {'─'*9} {'─'*8} {'─'*8} {'─'*7}")

    total_avant = total_new = total_apres = total_mub = 0
    for s in all_stats:
        avant    = s["existing_before"]
        nouveaux = s["new_annonces"]
        apres    = avant + nouveaux
        mub      = s["mubawab_enriched"]
        pct_mub  = f"{mub/max(nouveaux,1)*100:.0f}%" if nouveaux else "─"

        total_avant  += avant
        total_new    += nouveaux
        total_apres  += apres
        total_mub    += mub

        status = "✅" if nouveaux > 0 else "─ "
        logging.info(
            f"  {status} {s['label']:<20} {avant:>7,} {nouveaux:>+9,} "
            f"{apres:>8,} {mub:>5,}({pct_mub:>3}) {s['duration_s']:>6.0f}s"
        )

    logging.info(f"  {'─'*22} {'─'*7} {'─'*9} {'─'*8} {'─'*8} {'─'*7}")
    pct_total = f"{total_mub/max(total_new,1)*100:.0f}%"
    logging.info(
        f"  {'TOTAL':<22} {total_avant:>7,} {total_new:>+9,} "
        f"{total_apres:>8,} {total_mub:>5,}({pct_total:>3}) {total_elapsed:>6.0f}s"
    )
    logging.info(sep)

    errors = [s for s in all_stats if s["api_errors"] or s["detail_fails"]]
    if errors:
        logging.info("\n  ⚠️  Erreurs :")
        for s in errors:
            if s["api_errors"]:
                logging.info(f"    • {s['label']} : {s['api_errors']} erreurs API")
            if s["detail_fails"]:
                logging.info(f"    • {s['label']} : {s['detail_fails']} détails introuvables")

    logging.info(sep)
    if total_new == 0:
        logging.info("  ℹ️  Aucune nouvelle annonce à insérer dans Supabase.")
    else:
        logging.info(f"  🎉  {total_new} nouvelle(s) annonce(s) | {total_mub} enrichie(s) via Mubawab !")
    logging.info(sep)


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Agent Bigdatis + enrichissement Mubawab — tous les datasets"
    )
    parser.add_argument("--supabase-table", default=None, help="Table Supabase de destination")
    parser.add_argument("--only",     nargs="+", metavar="DATASET", choices=list(DATASETS.keys()))
    parser.add_argument("--skip",     nargs="+", metavar="DATASET", choices=list(DATASETS.keys()))
    parser.add_argument("--test",     action="store_true", help="10 annonces max par dataset")
    parser.add_argument("--no-headless", action="store_true", help="Ouvrir Firefox en mode visible")
    args = parser.parse_args()

    log_file = setup_logging()
    supabase_cfg = _load_supabase_config(args.supabase_table)

    to_run = list(DATASETS.keys())
    if args.only:
        to_run = [k for k in to_run if k in args.only]
    if args.skip:
        to_run = [k for k in to_run if k not in args.skip]

    logging.info("╔" + "═"*63 + "╗")
    logging.info("║   BIGDATIS + MUBAWAB — AGENT COLLECTE & ENRICHISSEMENT       ║")
    logging.info("╚" + "═"*63 + "╝")
    logging.info(f"  📝 Log       : {log_file}")
    logging.info(f"  🗄  Supabase  : {supabase_cfg['url']}")
    logging.info(f"  🗃  Table     : {supabase_cfg['table']}")
    logging.info(f"  🗂  Datasets  : {len(to_run)} / {len(DATASETS)}")
    logging.info(f"  🧪 Test mode : {'OUI (10 max/dataset)' if args.test else 'NON'}")
    logging.info(f"  🦊 Headless  : {'NON (visible)' if args.no_headless else 'OUI'}")
    logging.info(f"  ⏰ Démarré   : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Démarrer Firefox une seule fois pour tout le run
    selenium = SeleniumDriver(headless=not args.no_headless)
    selenium.start()

    global_start = time.time()
    all_stats    = []

    try:
        for key in to_run:
            cfg   = DATASETS[key]
            stats = run_dataset(key, cfg, supabase_cfg, args.test, selenium)
            all_stats.append(stats)
            time.sleep(3.0)
    finally:
        selenium.stop()

    total_elapsed = time.time() - global_start
    print_global_report(all_stats, total_elapsed)


if __name__ == "__main__":
    main()