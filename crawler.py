import os
import json
import time
import requests
import re
from urllib.parse import urlparse
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import cloudscraper # Importation du module anti-bot

# --- CONFIGURATION SÉCURISÉE (Via GitHub Secrets) ---
API_BASE_URL = os.environ.get('API_BASE_URL')
WEBHOOK_TOKEN = os.environ.get('WEBHOOK_TOKEN')

MAX_SITES_ENVOYES = 20
SCORE_MINIMUM = 6  # Score exigeant (Garantit Vrai Stream + Qualité)

# Tout en minuscules impérativement pour le filtrage
MOTS_INTERDITS = ['facebook','twitter','instagram','youtube','wikipedia','t.me','google','login','signup','amazon','netflix','x.com','fsound','cloudflarestatus','cdn1.telesco','brave.com', 'captcha', 'bot', 'verify']
MOTS_STREAM = ['stream','film','serie','anime','episode','watch','movie','streaming', 'saison']
# Ajout des nouveaux lecteurs renforcés (jwplayer, m3u8, video...)
LECTEURS_VIDEO = ['iframe', 'vidoza', 'uqload', 'doodstream', 'mystream', 'uptobox', 'gounlimited', 'uptostream', 'embed', 'player', '.m3u8', 'jwplayer', '<video']
EXTENSIONS_AUTORISEES = ['.com', '.net', '.org', '.lol', '.xyz', '.site', '.tv', '.me', '.plus', '.best', '.to', '.is', '.cc', '.sx', '.pe', '.ch', '.ws', '.ru', '.io', '.sh', '.ag', '.vip', '.pro']

# --- CONFIGURATION RÉSEAU ROBUSTE (Cloudscraper remplace requests standard) ---
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
    try:
        r = scraper.get(API_BASE_URL, timeout=10)
        data = r.json()
        if data.get("succes"): return {site["url"].strip() for site in data["donnees"]}
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
    try:
        # On utilise scraper.get au lieu de requests.get pour passer Cloudflare
        r = scraper.get(url, headers=HEADERS, timeout=10)
        if r.status_code != 200: return 0, ""
        
        html = r.text.lower()
        if "cloudflare" in html or "checking your browser" in html: return 0, ""
        
        score = 0
        tags_trouves = []
        
        # Le Test d'Authenticité Ultime (Doit contenir du texte ET un lecteur vidéo)
        a_du_streaming = any(mot in html for mot in MOTS_STREAM)
        a_des_lecteurs = any(lecteur in html for lecteur in LECTEURS_VIDEO)

        if not a_du_streaming or not a_des_lecteurs:
            return 0, ""
            
        score += 3 # Le site est officiellement certifié comme plateforme de streaming

        # Évaluation de la Qualité (Langue / Résolution)
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
    liens_valides = set()
    try:
        r = scraper.get(url_source, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.find_all("a", href=True):
            lien = a["href"].strip()
            if url_valide(lien): liens_valides.add(lien)
            
        motif_url = r'https?://[^\s<>"]+|www\.[^\s<>"]+'
        liens_texte = re.findall(motif_url, r.text)
        for l in liens_texte:
            if url_valide(l): liens_valides.add(l)
    except Exception as e:
        pass
    return liens_valides

def main():
    print("--- Démarrage du Crawler Élite (Anti-Cloudflare + Filtre Strict) ---")
    existants = recuperer_sites_existants()
    domaines_vus = set()
    noms_vus = set() # Mémoire pour éviter les doublons de noms (ex: voiranime.to et voiranime.com)
    nouveaux_sites_data = []

    try:
        with open("sources.txt", "r") as f:
            sources = [s.strip() for s in f if s.strip() and s.startswith('http')]
    except FileNotFoundError:
        print("Erreur : Fichier sources.txt introuvable.")
        return

    for source in sources:
        print(f"\nAnalyse de la source : {source}")
        liens_trouves = extraire_liens_source(source)
        
        for lien in liens_trouves:
            dom = obtenir_domaine(lien)
            nom_propre = dom.replace('www.', '').capitalize()
            
            # On vérifie qu'on n'a pas déjà ajouté ce nom avec une autre extension
            if dom in domaines_vus or lien in existants or nom_propre.lower() in noms_vus: 
                continue
                
            domaines_vus.add(dom)
            
            score, tags = evaluer_et_tagger_site(lien)
            if score >= SCORE_MINIMUM:
                noms_vus.add(nom_propre.lower()) # On bloque ce nom pour la suite
                print(f"  [Qualité Validée] {nom_propre} | Tags: {tags} | Score: {score}")
                
                nouveaux_sites_data.append({
                    "nom": nom_propre,
                    "categorie": "Films & Séries",
                    "url": lien,
                    "tags": tags
                })
            
            if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES: break
        
        if len(nouveaux_sites_data) >= MAX_SITES_ENVOYES: break
        time.sleep(1)

    if nouveaux_sites_data:
        print(f"\nEnvoi de {len(nouveaux_sites_data)} pépites au Sheet...")
        url_webhook = f"{API_BASE_URL}?token={WEBHOOK_TOKEN}"
        try:
            r = scraper.post(url_webhook, json={"nouveaux_sites": nouveaux_sites_data}, timeout=15)
            print(f"Réponse serveur : {r.text}")
        except Exception as e:
            print(f"Erreur d'envoi : {e}")
    else:
        print("\nAucun nouveau site de qualité trouvé aujourd'hui.")

if __name__ == "__main__":
    main()
