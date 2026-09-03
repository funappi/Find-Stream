import os
import json
import time
import requests
import re
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import cloudscraper

# --- CONFIGURATION SÉCURISÉE (Via GitHub Secrets) ---
API_BASE_URL = os.environ.get('API_BASE_URL')
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN')

MAX_SITES_ENVOYES = 20
SCORE_MINIMUM = 6  # Score exigeant (Garantit Vrai Stream + Qualité)

# Tout en minuscules impérativement pour le filtrage
MOTS_INTERDITS = [
    'facebook','twitter','instagram','youtube','wikipedia','t.me','google',
    'login','signup','amazon','netflix','x.com','fsound','cloudflarestatus',
    'cdn1.telesco','brave.com','captcha','bot','verify'
]
MOTS_STREAM = ['stream','film','serie','anime','episode','watch','movie','streaming','saison']
LECTEURS_VIDEO = [
    'iframe','vidoza','uqload','doodstream','mystream','uptobox','gounlimited',
    'uptostream','embed','player','.m3u8','jwplayer','<video'
]
EXTENSIONS_AUTORISEES = [
    '.com','.net','.org','.lol','.xyz','.site','.tv','.me','.plus','.best',
    '.to','.is','.cc','.sx','.pe','.ch','.ws','.ru','.io','.sh','.ag','.vip','.pro',
    '.art','.ink','.one','.dad','.cash','.markets','.wales'
]

# --- CONFIGURATION RÉSEAU ROBUSTE ---
scraper = cloudscraper.create_scraper()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
scraper.mount('http://', adapter)
scraper.mount('https://', adapter)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def obtenir_domaine(url):
    try: return urlparse(url).netloc
    except: return ""

def recuperer_sites_existants():
    """Récupère les URLs déjà dans la base pour éviter les doublons."""
    try:
        r = scraper.get(API_BASE_URL, timeout=10)
        data = r.json()
        if data.get("succes"):
            existants = {site["url"].strip() for site in data["donnees"]}
            print(f"  → {len(existants)} sites déjà en base.")
            return existants
    except Exception as e:
        print(f"Note : Base de données inaccessible ({e})")
    return set()

def url_valide(url):
    if not url or not url.startswith("http"): return False
    domaine = obtenir_domaine(url).lower()
    if not any(domaine.endswith(ext) for ext in EXTENSIONS_AUTORISEES): return False
    url_lower = url.lower()
    for mot in MOTS_INTERDITS:
        if mot in url_lower: return False
    return True

def evaluer_et_tagger_site(url):
    """Télécharge la page et calcule un score de qualité streaming."""
    try:
        r = scraper.get(url, headers=HEADERS, timeout=12)
        if r.status_code != 200:
            print(f"    [SKIP] {url} → HTTP {r.status_code}")
            return 0, ""

        html = r.text.lower()

        # Détection Cloudflare : si bloqué, on abandonne
        if "cloudflare" in html and "checking your browser" in html:
            print(f"    [SKIP] {url} → Bloqué Cloudflare")
            return 0, ""

        score = 0
        tags_trouves = []

        # Test d'authenticité : doit avoir du texte streaming ET un lecteur vidéo
        a_du_streaming = any(mot in html for mot in MOTS_STREAM)
        a_des_lecteurs = any(lecteur in html for lecteur in LECTEURS_VIDEO)

        if not a_du_streaming or not a_des_lecteurs:
            return 0, ""

        score += 3  # Plateforme de streaming certifiée

        # Qualité : Langue
        if "vf" in html or "français" in html or "francais" in html:
            score += 3
            tags_trouves.append("VF")

        if "vostfr" in html or "vost" in html:
            score += 1
            tags_trouves.append("VOSTFR")

        # Qualité : Résolution
        if "1080p" in html or "720p" in html or " hd " in html or "4k" in html:
            score += 2
            tags_trouves.append("HD")

        tags_string = ", ".join(tags_trouves)
        return score, tags_string

    except Exception as e:
        print(f"    [ERREUR] {url} → {e}")
        return 0, ""

def extraire_liens_source(url_source):
    """Scrape une page source et retourne tous les liens valides trouvés."""
    liens_valides = set()
    try:
        r = scraper.get(url_source, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")

        # Extraction via balises <a>
        for a in soup.find_all("a", href=True):
            lien = a["href"].strip()
            if url_valide(lien):
                liens_valides.add(lien)

        # Extraction via regex dans le texte brut (captures les liens non balisés)
        motif_url = r'https?://[^\s<>"\']+|www\.[^\s<>"\']+'
        for l in re.findall(motif_url, r.text):
            # Nettoyer les caractères parasites en fin d'URL
            l = re.sub(r'[)\].,;!?\'">]+$', '', l)
            if url_valide(l):
                liens_valides.add(l)

    except Exception as e:
        print(f"  [SOURCE ERREUR] {url_source} → {e}")

    return liens_valides

def main():
    print("=" * 60)
    print("  Crawler FindStream — Anti-Cloudflare + Filtre Strict")
    print("=" * 60)

    if not API_BASE_URL or not WEBHOOK_TOKEN:
        print("ERREUR CRITIQUE : Variables d'environnement manquantes (API_BASE_URL, WEBHOOK_TOKEN).")
        return

    existants = recuperer_sites_existants()
    domaines_vus = set()
    noms_vus = set()
    nouveaux_sites_data = []

    # --- CHARGEMENT ET DÉDUPLICATION DES SOURCES ---
    try:
        with open("sources.txt", "r") as f:
            # FIX : list(dict.fromkeys(...)) supprime les doublons en gardant l'ordre
            sources = list(dict.fromkeys([
                s.strip() for s in f
                if s.strip() and s.strip().startswith('http')
            ]))
        print(f"\n{len(sources)} sources uniques chargées.\n")
    except FileNotFoundError:
        print("ERREUR : Fichier sources.txt introuvable.")
        return

    # --- CRAWL ---
    for source in sources:
        print(f"\n→ Analyse : {source}")
        liens_trouves = extraire_liens_source(source)
        print(f"  {len(liens_trouves)} liens candidats trouvés.")

        for lien in liens_trouves:
            dom = obtenir_domaine(lien)
            # Construire un nom propre lisible (ex: "coflix.wales" → "Coflix")
            nom_base = dom.replace('www.', '').split('.')[0]
            nom_propre = nom_base.capitalize()

            # Vérifier les doublons (domaine exact OU même nom de base)
            if dom in domaines_vus or lien in existants or nom_base.lower() in noms_vus:
                continue

            domaines_vus.add(dom)

            score, tags = evaluer_et_tagger_site(lien)
            if score >= SCORE_MINIMUM:
                noms_vus.add(nom_base.lower())
                print(f"  ✅ [VALIDÉ] {nom_propre} | Score: {score} | Tags: {tags} | URL: {lien}")

                nouveaux_sites_data.append({
                    "nom": nom_propre,
                    "categorie": "Films & Séries",
                    "url": lien,
                    "tags": tags
                })
            else:
                if score > 0:
                    print(f"  ⚠️  [SCORE FAIBLE] {nom_propre} | Score: {score} (min requis: {SCORE_MINIMUM})")

            if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES:
                break

        if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES:
            print(f"\nLimite de {MAX_SITES_ENVOYES} sites atteinte.")
            break

        time.sleep(1)  # Pause polie entre les sources

    # --- ENVOI AU GOOGLE SHEET ---
    print("\n" + "=" * 60)
    if nouveaux_sites_data:
        print(f"  → Envoi de {len(nouveaux_sites_data)} nouveaux sites...")
        url_webhook = f"{API_BASE_URL}?token={WEBHOOK_TOKEN}"
        try:
            r = scraper.post(url_webhook, json={"nouveaux_sites": nouveaux_sites_data}, timeout=15)
            print(f"  → Réponse serveur : {r.text}")
        except Exception as e:
            print(f"  → ERREUR d'envoi : {e}")
    else:
        print("  → Aucun nouveau site de qualité trouvé aujourd'hui.")
    print("=" * 60)

if __name__ == "__main__":
    main()
