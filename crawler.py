import json
import time
import requests
import re
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup

# --- CONFIGURATION EN BRUT ---
API_BASE_URL = "https://script.google.com/macros/s/AKfycbyhXWiqjOZ--EAM0mItqB9-Jh0wyG28iKYN7-Nz61dxKSpDFhqmrb2swXjL0OxK4FVGjA/exec"
WEBHOOK_TOKEN = "MonSuperTokenSecret2026"

MAX_SITES_ENVOYES = 20
SCORE_MINIMUM = 5  # Exige au moins VF (3 pts) + HD (2 pts)

MOTS_INTERDITS = ['facebook','twitter','instagram','youtube','wikipedia','t.me','google','login','signup','amazon','netflix','X.com','Fsound','cloudflarestatus','cdn1.telesco']
MOTS_STREAM = ['stream','film','serie','anime','episode','watch','movie','streaming']
EXTENSIONS_AUTORISEES = ['.com', '.net', '.org', '.lol', '.xyz', '.site', '.tv', '.me', '.plus', '.best', '.to', '.is', '.cc', '.sx', '.pe', '.ch', '.ws', '.ru', '.io', '.sh', '.ag', '.vip', '.pro']

# --- CONFIGURATION RÉSEAU ROBUSTE ---
session = requests.Session()
retry = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
adapter = HTTPAdapter(max_retries=retry)
session.mount('http://', adapter)
session.mount('https://', adapter)
HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

def obtenir_domaine(url):
    try:
        return urlparse(url).netloc
    except:
        return ""

def recuperer_sites_existants():
    try:
        r = session.get(API_BASE_URL, timeout=10)
        data = r.json()
        if data.get("succes"):
            return {site["url"].strip() for site in data["donnees"]}
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
    """Analyse le contenu du site, donne un score hybride et génère les tags"""
    try:
        r = session.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200: return 0, ""
        
        html = r.text.lower()
        score = 0
        tags_trouves = []
        
        # 1. Analyse de la thématique globale (Issu du Code 1)
        for mot in MOTS_STREAM:
            if mot in html:
                score += 1
                break # On ajoute le point 1 seule fois si c'est bien un site de stream
                
        if "iframe" in html or "video" in html or "player" in html:
            score += 2
        
        # 2. Analyse précise Qualité/Langue (Issu du Code 2)
        if "vf" in html or "français" in html or "francais" in html:
            score += 3
            tags_trouves.append("VF")
        if "vostfr" in html or "vost" in html:
            score += 1
            tags_trouves.append("VOSTFR")
            
        if "1080p" in html or "720p" in html or " hd " in html or "4k" in html:
            score += 2
            tags_trouves.append("HD")
            
        tags_string = ", ".join(tags_trouves)
        return score, tags_string
    except:
        return 0, ""

def extraire_liens_source(url_source):
    """Extraction surpuissante (DOM + Regex)"""
    liens_valides = set()
    try:
        r = session.get(url_source, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Extraction via balises <a>
        for a in soup.find_all("a", href=True):
            lien = a["href"].strip()
            if url_valide(lien): liens_valides.add(lien)
            
        # Extraction via Regex pour les liens cachés dans le texte brut
        motif_url = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        liens_texte = re.findall(motif_url, r.text)
        for l in liens_texte:
            if url_valide(l): liens_valides.add(l)
    except Exception as e:
        print(f"Erreur scan {url_source}: {e}")
    return liens_valides

def main():
    print("--- Démarrage du Crawler Élite Fusionné ---")
    existants = recuperer_sites_existants()
    domaines_vus = set()
    nouveaux_sites_data = []

    try:
        with open("sources.txt", "r") as f:
            sources = [s.strip() for s in f if s.strip() and s.startswith('http')]
    except FileNotFoundError:
        print("Erreur : sources.txt introuvable.")
        return

    for source in sources:
        print(f"\nRecherche dans : {source}")
        liens_trouves = extraire_liens_source(source)
        
        for lien in liens_trouves:
            dom = obtenir_domaine(lien)
            if dom in domaines_vus or lien in existants: continue
            domaines_vus.add(dom)
            
            score, tags = evaluer_et_tagger_site(lien)
            if score >= SCORE_MINIMUM:
                nom_propre = dom.replace('www.', '').capitalize()
                print(f"  [Top Qualité] {nom_propre} | {tags} | Score: {score}")
                
                nouveaux_sites_data.append({
                    "nom": nom_propre,
                    "categorie": "Films & Séries",
                    "url": lien,
                    "tags": tags
                })
            
            if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES: break
        
        if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES: break
        time.sleep(1) # Politesse réseau entre les sources

    if nouveaux_sites_data:
        print(f"\nEnvoi de {len(nouveaux_sites_data)} pépites au Sheet...")
        url_webhook = f"{API_BASE_URL}?token={WEBHOOK_TOKEN}"
        try:
            r = session.post(url_webhook, json={"nouveaux_sites": nouveaux_sites_data}, timeout=15)
            print(f"Réponse serveur : {r.text}")
        except Exception as e:
            print(f"Erreur d'envoi : {e}")
    else:
        print("\nAucun site n'a réussi le test de qualité aujourd'hui.")

if __name__ == "__main__":
    main()
