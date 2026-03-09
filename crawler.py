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

# Paramètres de Chasse
MAX_SITES_ENVOYES = 20
SCORE_MINIMUM = 5  # Un site doit avoir des mots comme 'streaming' ou 'vf' pour être accepté

# Listes de filtrage intelligent
MOTS_INTERDITS = ['facebook','twitter','instagram','youtube','wikipedia','t.me','google','login','signup','amazon','netflix']
MOTS_STREAM = ['stream','film','serie','anime','episode','vostfr','vf','watch','movie','streaming']

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
    """Télécharge la base actuelle pour éviter les doublons"""
    try:
        r = session.get(API_BASE_URL, timeout=10)
        data = r.json()
        if data.get("succes"):
            return {site["url"].strip() for site in data["donnees"]}
    except Exception as e:
        print(f"Note : Base de données inaccessible ({e})")
    return set()

def url_valide(url):
    """Vérifie si l'URL n'est pas dans la liste noire"""
    if not url or not url.startswith("http"):
        return False
    for mot in MOTS_INTERDITS:
        if mot in url.lower():
            return False
    return True

def evaluer_qualite_site(url):
    """Analyse le contenu du site pour lui donner une note de pertinence"""
    try:
        r = session.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200:
            return 0
        
        html = r.text.lower()
        score = 0
        
        # Points pour les mots clés
        for mot in MOTS_STREAM:
            if mot in html:
                score += 1
        
        # Points bonus pour les lecteurs vidéo
        if "iframe" in html or "video" in html or "player" in html:
            score += 3
        if "vostfr" in html or " vf " in html:
            score += 2
            
        return score
    except:
        return 0

def extraire_liens_source(url_source):
    """Extrait tous les liens valides d'une page source"""
    liens_valides = set()
    try:
        r = session.get(url_source, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        
        # Extraction via balises <a>
        for a in soup.find_all("a", href=True):
            lien = a["href"].strip()
            if url_valide(lien):
                liens_valides.add(lien)
                
        # Extraction via Regex (pour les liens en texte brut)
        motif_url = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        liens_texte = re.findall(motif_url, r.text)
        for l in liens_texte:
            if url_valide(l):
                liens_valides.add(l)
                
    except Exception as e:
        print(f"Erreur scan {url_source}: {e}")
    return liens_valides

def main():
    print("--- Démarrage du Crawler Elite ---")
    existants = recuperer_sites_existants()
    domaines_vus = set()
    nouveaux_liens = []

    try:
        with open("sources.txt", "r") as f:
            sources = [s.strip() for s in f if s.strip() and s.startswith('http')]
    except FileNotFoundError:
        print("Erreur : sources.txt introuvable.")
        return

    for source in sources:
        print(f"Analyse de la source : {source}")
        liens_trouves = extraire_liens_source(source)
        
        for lien in liens_trouves:
            dom = obtenir_domaine(lien)
            
            # 1. Éviter de scanner deux fois le même domaine durant cette session
            if dom in domaines_vus or lien in existants:
                continue
            
            domaines_vus.add(dom)
            
            # 2. Évaluer si c'est un vrai site de stream ou une pub/erreur
            score = evaluer_qualite_site(lien)
            if score >= SCORE_MINIMUM:
                print(f"  [Top Qualité] Trouvé : {lien} (Score: {score})")
                nouveaux_liens.append(lien)
            
            if len(nouveaux_liens) >= MAX_SITES_ENVOYES:
                break
        
        if len(nouveaux_liens) >= MAX_SITES_ENVOYES:
            break
        time.sleep(1)

    # Envoi final
    if nouveaux_liens:
        print(f"Envoi de {len(nouveaux_liens)} sites vérifiés au Google Sheet...")
        url_webhook = f"{API_BASE_URL}?token={WEBHOOK_TOKEN}"
        try:
            r = session.post(url_webhook, json={"urls": nouveaux_liens}, timeout=15)
            print(f"Réponse serveur : {r.text}")
        except Exception as e:
            print(f"Erreur envoi Webhook : {e}")
    else:
        print("Aucun nouveau site de qualité trouvé aujourd'hui.")

if __name__ == "__main__":
    main()
