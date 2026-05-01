"""Scraping politesse-first des mentions légales / pages contact.

Logique :
1. Pour chaque site_web :
   a. Vérifier robots.txt (politesse + légal)
   b. Tenter /mentions-legales puis /contact (variants courants)
   c. Extraire emails via regex sur le HTML
   d. Filtrer faux positifs (jpg@, png@, sentry, etc.)
2. Rate limit : 1 req/s par domaine
3. Timeout strict 10s
4. User-Agent honnête
"""

from __future__ import annotations

import re
import time
import urllib.parse
import urllib.robotparser
from dataclasses import dataclass, field

import requests
from bs4 import BeautifulSoup
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_fixed

from ..common.logger import get_logger

logger = get_logger(__name__)

# ════════════════════════════════════════════════════════════════
# Configuration
# ════════════════════════════════════════════════════════════════

USER_AGENT = "RenoboostLeadsBot/0.1 (+contact@renoboost.fr)"
TIMEOUT_SECONDS = 10.0

# Chemins typiques où trouver les mentions légales
CHEMINS_MENTIONS_LEGALES = [
    "/mentions-legales",
    "/mentions-legales/",
    "/mentions",
    "/mentions/",
    "/legal",
    "/legal/",
    "/legalnotice",
    "/cgv",
    "/cgu",
]
CHEMINS_CONTACT = [
    "/contact",
    "/contact/",
    "/nous-contacter",
    "/contactez-nous",
    "/contactez-nous/",
    "/about",
    "/a-propos",
    "/qui-sommes-nous",
]

# Regex emails (rigoureuse mais pas trop : on accepte tirets, points, etc.)
EMAIL_REGEX = re.compile(
    r"[a-zA-Z0-9](?:[a-zA-Z0-9._-]{0,62}[a-zA-Z0-9])?"
    r"@"
    r"(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?\.)+"
    r"[a-zA-Z]{2,24}"
)

# Faux positifs courants à filtrer
EXTENSIONS_PARASITES = {
    "jpg", "jpeg", "png", "gif", "webp", "svg", "ico",
    "css", "js", "json", "xml",
    "ttf", "woff", "woff2", "otf", "eot",
    "pdf", "doc", "docx", "xls", "xlsx",
    "zip", "rar",
}

DOMAINES_PARASITES = {
    "sentry.io", "sentry.wixpress.com",
    "wixpress.com", "wix.com",
    "googleusercontent.com", "googletagmanager.com",
    "gstatic.com",
    "cloudflare.com", "cloudflareinsights.com",
    "facebook.com", "twitter.com", "instagram.com",
    "linkedin.com", "youtube.com",
    "example.com", "example.org",
    "domain.com", "domain.fr",
    "test.com", "test.fr",
}

# Préfixes/locaux suspects
LOCAUX_SUSPECTS = {
    "noreply", "no-reply", "donotreply", "do-not-reply",
    "name", "email", "yourname", "user",
    "abuse", "postmaster",
    "admin@admin", "root@root",
}


# ════════════════════════════════════════════════════════════════
# Modèles internes
# ════════════════════════════════════════════════════════════════


@dataclass
class ResultatScraping:
    domaine: str | None = None
    emails: list[str] = field(default_factory=list)
    page_source: str | None = None  # URL d'où viennent les emails
    raison_echec: str | None = None
    pages_visitees: list[str] = field(default_factory=list)


# ════════════════════════════════════════════════════════════════
# Helpers
# ════════════════════════════════════════════════════════════════


def extraire_domaine(url: str | None) -> str | None:
    """Extrait le domaine depuis une URL (ex: 'hotellesud.fr' depuis 'https://www.hotellesud.fr/contact')."""
    if not url:
        return None
    try:
        parsed = urllib.parse.urlparse(url if "://" in url else f"https://{url}")
        domaine = parsed.netloc or parsed.path
        # Strip www.
        if domaine.startswith("www."):
            domaine = domaine[4:]
        # Strip port
        if ":" in domaine:
            domaine = domaine.split(":")[0]
        return domaine.lower() or None
    except Exception:  # noqa: BLE001
        return None


def email_est_valide(email: str) -> bool:
    """Filtre les faux positifs."""
    if not email or "@" not in email:
        return False
    email = email.lower().strip()

    local, _, domaine = email.partition("@")
    if not local or not domaine or "." not in domaine:
        return False

    # Filtrer extensions de fichier (ex: name@2x.png)
    extension = domaine.rsplit(".", 1)[-1].lower()
    if extension in EXTENSIONS_PARASITES:
        return False

    # Filtrer domaines parasites
    for parasite in DOMAINES_PARASITES:
        if domaine == parasite or domaine.endswith("." + parasite):
            return False

    # Filtrer locaux suspects
    for suspect in LOCAUX_SUSPECTS:
        if local == suspect or local.startswith(suspect):
            return False

    # Filtrer locaux trop courts (1-2 chars suspect)
    if len(local) < 2:
        return False

    return True


def extraire_emails_du_html(html: str, domaine_attendu: str | None = None) -> list[str]:
    """Parse le HTML et extrait les emails présents (texte + attributs href).

    Si domaine_attendu fourni : ne retourne que les emails de ce domaine.
    """
    if not html:
        return []

    emails: set[str] = set()

    # 1. Extraction depuis le texte brut
    for m in EMAIL_REGEX.finditer(html):
        email = m.group(0).lower()
        if email_est_valide(email):
            emails.add(email)

    # 2. Extraction depuis les liens mailto:
    try:
        soup = BeautifulSoup(html, "lxml")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if href.lower().startswith("mailto:"):
                email_part = href[7:].split("?")[0].strip().lower()
                if email_est_valide(email_part):
                    emails.add(email_part)
    except Exception as e:  # noqa: BLE001 — on est tolérant sur HTML cassé
        logger.debug("Parsing HTML mailto échoué (HTML cassé) : %s", e)

    # Filtrage par domaine si demandé
    if domaine_attendu:
        emails = {e for e in emails if e.split("@", 1)[1] == domaine_attendu}

    return sorted(emails)


# ════════════════════════════════════════════════════════════════
# Scraper principal
# ════════════════════════════════════════════════════════════════


class ScraperContact:
    """Scraping HTTP simple, politesse-first."""

    def __init__(self, rate_limit_seconds: float = 1.0):
        self.rate_limit_seconds = rate_limit_seconds
        self._last_request_per_host: dict[str, float] = {}
        self._robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": USER_AGENT})

    def _attendre_rate_limit(self, host: str) -> None:
        last = self._last_request_per_host.get(host)
        if last is not None:
            ecoule = time.monotonic() - last
            if ecoule < self.rate_limit_seconds:
                time.sleep(self.rate_limit_seconds - ecoule + 0.05)
        self._last_request_per_host[host] = time.monotonic()

    def _verifier_robots(self, base_url: str, path: str) -> bool:
        """Renvoie True si le path est autorisé par robots.txt."""
        try:
            host = urllib.parse.urlparse(base_url).netloc
            if not host:
                return True

            if host not in self._robots_cache:
                rp = urllib.robotparser.RobotFileParser()
                robots_url = f"{base_url.rstrip('/')}/robots.txt"
                try:
                    rp.set_url(robots_url)
                    self._attendre_rate_limit(host)
                    rp.read()
                    self._robots_cache[host] = rp
                except Exception:  # noqa: BLE001
                    # Pas de robots.txt accessible → on accepte par défaut
                    self._robots_cache[host] = None  # type: ignore[assignment]

            rp = self._robots_cache[host]
            if rp is None:
                return True
            return rp.can_fetch(USER_AGENT, base_url + path)
        except Exception:  # noqa: BLE001
            return True

    @retry(
        retry=retry_if_exception_type(requests.RequestException),
        wait=wait_fixed(2),
        stop=stop_after_attempt(2),  # 1 retry max
        reraise=False,
    )
    def _fetch(self, url: str) -> str | None:
        try:
            self._attendre_rate_limit(urllib.parse.urlparse(url).netloc)
            resp = self.session.get(url, timeout=TIMEOUT_SECONDS, allow_redirects=True)
            if resp.status_code == 200:
                # On limite la taille (anti-bombe)
                content = resp.text
                if len(content) > 2_000_000:  # 2 Mo max
                    content = content[:2_000_000]
                return content
            return None
        except requests.RequestException:
            raise

    def _construire_base_url(self, site_web: str) -> str | None:
        """Construit l'URL de base en gérant http/https et trailing slash."""
        if not site_web:
            return None
        site_web = site_web.strip()
        if not site_web.startswith(("http://", "https://")):
            site_web = "https://" + site_web
        try:
            parsed = urllib.parse.urlparse(site_web)
            return f"{parsed.scheme}://{parsed.netloc}"
        except Exception:  # noqa: BLE001
            return None

    def scraper(self, site_web: str | None) -> ResultatScraping:
        """Scrape les emails depuis le site web.

        Tente d'abord /mentions-legales, puis /contact (variants).
        Retourne le premier résultat non vide trouvé.
        """
        if not site_web:
            return ResultatScraping(raison_echec="pas_de_site_web")

        base_url = self._construire_base_url(site_web)
        if not base_url:
            return ResultatScraping(raison_echec="url_invalide")

        domaine = extraire_domaine(base_url)
        result = ResultatScraping(domaine=domaine)

        # Test de connectivité de base
        homepage_html = self._fetch(base_url)
        if homepage_html is None:
            result.raison_echec = "site_inaccessible"
            return result
        result.pages_visitees.append(base_url)

        # Cherche dans la homepage
        emails_home = extraire_emails_du_html(homepage_html, domaine_attendu=domaine)

        # Tenter mentions légales en priorité
        for path in CHEMINS_MENTIONS_LEGALES + CHEMINS_CONTACT:
            if not self._verifier_robots(base_url, path):
                logger.debug("Robots.txt interdit %s%s", base_url, path)
                continue

            url = base_url + path
            try:
                html = self._fetch(url)
            except Exception as e:  # noqa: BLE001
                logger.debug("Scraping %s échoué : %s", url, e)
                continue

            if html is None:
                continue
            result.pages_visitees.append(url)

            emails = extraire_emails_du_html(html, domaine_attendu=domaine)
            if emails:
                result.emails = emails
                result.page_source = url
                return result

        # Fallback : emails de la homepage
        if emails_home:
            result.emails = emails_home
            result.page_source = base_url
            return result

        result.raison_echec = "aucun_email_trouve"
        return result
