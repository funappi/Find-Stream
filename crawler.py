import os
import re
import time
import cloudscraper
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# ============================================================
# CONFIGURATION
# ============================================================
API_BASE_URL = os.environ.get("API_BASE_URL")
WEBHOOK_TOKEN = os.environ.get("WEBHOOK_TOKEN")

MAX_SITES_ENVOYES = 20
SCORE_MINIMUM = 6
TAILLE_LOT = 5                 # envoi au webhook tous les 5 sites qualifiés
BUDGET_SECONDES = 8 * 60       # on s'arrête proprement avant le timeout de 10 min du workflow

# ============================================================
# FILTRES & RÈGLES D'ANALYSE
# ============================================================
# Noms de marque cherchés dans le nom de domaine uniquement.
MARQUES_INTERDITES = [
    "facebook", "twitter", "instagram", "youtube", "wikipedia",
    "google", "amazon", "netflix", "fsound", "cloudflarestatus", "telesco"
]

# Domaines exacts (et leurs sous-domaines). Un test de sous-chaîne sur toute l'URL
# rejetait à tort des domaines légitimes ("t.me" dans "hot.me", "x.com" dans "max.com").
DOMAINES_INTERDITS = ["t.me", "x.com", "brave.com"]

# Mots cherchés dans le chemin et la requête (pages de connexion, captcha, ...).
MOTS_INTERDITS_CHEMIN = ["login", "signup", "captcha", "verify", "/bot"]

MOTS_STREAM = [
    "stream", "film", "serie", "anime", "episode",
    "watch", "movie", "streaming", "saison"
]

LECTEURS_VIDEO = [
    "iframe", "vidoza", "uqload", "doodstream", "mystream", "uptobox",
    "gounlimited", "uptostream", "embed", "player", ".m3u8", "jwplayer", "<video"
]

EXTENSIONS_AUTORISEES = [
    ".com", ".net", ".org", ".lol", ".xyz", ".site", ".tv", ".me",
    ".plus", ".best", ".to", ".is", ".cc", ".sx", ".pe", ".ch",
    ".ws", ".ru", ".io", ".sh", ".ag", ".vip", ".pro"
]

# ============================================================
# CONFIGURATION CLIENT HTTP
# ============================================================
scraper = cloudscraper.create_scraper()

retry = Retry(
    total=3,
    backoff_factor=1,
    status_forcelist=[429, 500, 502, 503, 504],
    allowed_methods=["GET", "POST"]
)

adapter = HTTPAdapter(max_retries=retry)
scraper.mount("http://", adapter)
scraper.mount("https://", adapter)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
}

# ============================================================
# OUTILS & NORMALISATION
# ============================================================
def obtenir_domaine(url):
    """Extrait le nom de domaine en minuscules."""
    try:
        return urlparse(url).netloc.lower()
    except Exception:
        return ""

def normaliser_url(url):
    """Nettoie les espaces et les ponctuations résiduelles en fin d'URL."""
    if not url:
        return ""
    url = url.strip()
    return re.sub(r"[)\].,;!?'\"]+$", "", url)

def domaine_interdit(domaine):
    """Rejette réseaux sociaux, CDN et services connus d'après le nom de domaine seul."""
    domaine = domaine.split(":")[0]
    if any(domaine == d or domaine.endswith("." + d) for d in DOMAINES_INTERDITS):
        return True
    return any(marque in domaine for marque in MARQUES_INTERDITES)

def url_valide(url):
    """Valide l'URL selon le format, l'extension et les mots interdits."""
    if not url:
        return False
    url_propre = normaliser_url(url)
    if not url_propre.startswith(("http://", "https://")):
        return False

    domaine = obtenir_domaine(url_propre)
    if not domaine or not any(domaine.endswith(ext) for ext in EXTENSIONS_AUTORISEES):
        return False

    if domaine_interdit(domaine):
        return False

    parsed = urlparse(url_propre)
    chemin = (parsed.path + "?" + parsed.query).lower()
    if any(mot in chemin for mot in MOTS_INTERDITS_CHEMIN):
        return False

    return True

# ============================================================
# INTERACTION API / BASE EXISTANTE
# ============================================================
def recuperer_sites_existants():
    """Charge les URLs déjà indexées dans le backend."""
    try:
        r = scraper.get(API_BASE_URL, headers=HEADERS, timeout=10)
        r.raise_for_status()
        data = r.json()
        if data.get("succes"):
            existants = {
                site["url"].strip()
                for site in data.get("donnees", [])
                if isinstance(site, dict) and site.get("url")
            }
            print(f"  → {len(existants)} sites déjà répertoriés dans la base.")
            return existants
        print("  → Note : L'API a répondu mais avec 'succes' = False.")
    except Exception as e:
        print(f"  → Note : Base de données inaccessible ({e})")
    return set()

# ============================================================
# ANALYSE ET ÉVALUATION DU SITE
# ============================================================
def evaluer_et_tagger_site(url):
    """Évalue la pertinence streaming, la langue et la résolution."""
    try:
        r = scraper.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return 0, ""

        html = r.text.lower()
        if "cloudflare" in html or "checking your browser" in html:
            return 0, ""

        a_du_streaming = any(mot in html for mot in MOTS_STREAM)
        a_des_lecteurs = any(lecteur in html for lecteur in LECTEURS_VIDEO)

        if not a_du_streaming or not a_des_lecteurs:
            return 0, ""

        score = 3
        tags_trouves = []

        # Détection Langue
        if any(kw in html for kw in ["vf", "français", "francais"]):
            score += 3
            tags_trouves.append("VF")

        if any(kw in html for kw in ["vostfr", "vost"]):
            score += 1
            tags_trouves.append("VOSTFR")

        # Détection Résolution
        if any(kw in html for kw in ["1080p", "720p", " hd ", "4k"]):
            score += 2
            tags_trouves.append("HD")

        return score, ", ".join(tags_trouves)
    except Exception:
        return 0, ""

# ============================================================
# EXTRACTION & CHARGEMENT
# ============================================================
def extraire_liens_source(url_source):
    """Extrait les URLs via balises <a> et regex brute dans le document."""
    liens_valides = set()
    try:
        r = scraper.get(url_source, headers=HEADERS, timeout=15)
        if r.status_code != 200:
            print(f"  → Source ignorée (HTTP {r.status_code})")
            return liens_valides

        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            lien = normaliser_url(a["href"])
            if url_valide(lien):
                liens_valides.add(lien)

        motif_url = r'https?://[^\s<>"\'\]]+|www\.[^\s<>"\'\]]+'
        for brut in re.findall(motif_url, r.text):
            lien = normaliser_url(brut)
            if url_valide(lien):
                liens_valides.add(lien)

    except Exception as e:
        print(f"  → Erreur sur la source {url_source} : {e}")

    return liens_valides

def charger_sources():
    """Charge le fichier sources.txt avec déduplication conservant l'ordre."""
    try:
        with open("sources.txt", "r", encoding="utf-8") as f:
            sources = []
            for ligne in f:
                s = normaliser_url(ligne)
                if s and s.startswith(("http://", "https://")):
                    sources.append(s)
            return list(dict.fromkeys(sources))
    except FileNotFoundError:
        print("ERREUR : Fichier sources.txt introuvable.")
        return []
    except Exception as e:
        print(f"ERREUR lors de la lecture de sources.txt : {e}")
        return []

def envoyer_nouveaux_sites(nouveaux_sites_data):
    """Transmet la charge utile validée au webhook API.

    Retourne le nombre de sites réellement envoyés (0 en cas d'échec : l'appelant
    pourra les renvoyer avec le lot suivant)."""
    if not nouveaux_sites_data:
        return 0

    url_webhook = f"{API_BASE_URL}?token={WEBHOOK_TOKEN}"
    try:
        r = scraper.post(
            url_webhook,
            headers={**HEADERS, "Content-Type": "application/json"},
            json={"nouveaux_sites": nouveaux_sites_data},
            timeout=15
        )
        print(f"  → HTTP {r.status_code} | Réponse serveur : {r.text}")
        return len(nouveaux_sites_data) if 200 <= r.status_code < 300 else 0
    except Exception as e:
        print(f"  → ERREUR lors de l'envoi : {e}")
        return 0

def budget_depasse(debut):
    """Vrai quand le temps alloué au run est écoulé."""
    return time.monotonic() - debut > BUDGET_SECONDES

# ============================================================
# EXÉCUTION PRINCIPALE
# ============================================================
def main():
    print("=" * 60)
    print("  Crawler FindStream — V-Unified")
    print("=" * 60)

    if not API_BASE_URL or not WEBHOOK_TOKEN:
        print("ERREUR CRITIQUE : API_BASE_URL ou WEBHOOK_TOKEN non défini(s).")
        return

    debut = time.monotonic()
    existants = recuperer_sites_existants()
    domaines_existants = {obtenir_domaine(u).removeprefix("www.") for u in existants}
    domaines_vus = set()
    noms_vus = set()
    nouveaux_sites_data = []
    envoyes = 0  # nombre de sites de nouveaux_sites_data déjà transmis au webhook

    sources = charger_sources()
    if not sources:
        print("Aucune source valide à analyser.")
        return

    print(f"\n→ {len(sources)} sources uniques chargées.")

    for index, source in enumerate(sources, start=1):
        print(f"\n[{index}/{len(sources)}] Analyse : {source}")
        liens_trouves = extraire_liens_source(source)
        print(f"  → {len(liens_trouves)} liens candidats détectés.")

        for lien in liens_trouves:
            if budget_depasse(debut):
                break

            dom = obtenir_domaine(lien)
            if not dom:
                continue

            nom_propre = dom.replace("www.", "").capitalize()

            # Évite les doublons de domaine (déjà en base ou déjà vus), d'URL et de nom de marque
            if (dom in domaines_vus or lien in existants
                    or dom.removeprefix("www.") in domaines_existants
                    or nom_propre.lower() in noms_vus):
                continue

            domaines_vus.add(dom)

            score, tags = evaluer_et_tagger_site(lien)
            if score >= SCORE_MINIMUM:
                noms_vus.add(nom_propre.lower())
                print(f"  [QUALITÉ VALIDÉE] {nom_propre} | Tags: {tags} | Score: {score}")

                nouveaux_sites_data.append({
                    "nom": nom_propre,
                    "categorie": "Films & Séries",
                    "url": lien,
                    "tags": tags
                })

                # Envoi par lots : un timeout du job ne fait plus perdre toute la nuit.
                if len(nouveaux_sites_data) - envoyes >= TAILLE_LOT:
                    envoyes += envoyer_nouveaux_sites(nouveaux_sites_data[envoyes:])

            if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES:
                break

        if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES:
            print(f"\n→ Limite de {MAX_SITES_ENVOYES} sites atteinte.")
            break

        if budget_depasse(debut):
            print(f"\n→ Budget de temps ({BUDGET_SECONDES // 60} min) atteint : arrêt propre.")
            break

        time.sleep(1)

    print("\n" + "=" * 60)
    if len(nouveaux_sites_data) > envoyes:
        envoyes += envoyer_nouveaux_sites(nouveaux_sites_data[envoyes:])
    if nouveaux_sites_data:
        print(f"→ {envoyes}/{len(nouveaux_sites_data)} nouveaux sites injectés.")
    else:
        print("→ Aucun nouveau site qualifié trouvé.")
    print("=" * 60)

if __name__ == "__main__":
    main()
