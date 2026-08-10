<div align="center">

  <h1>🎬 FindStream - Live Dashboard</h1>
  <p><b>Plateforme d'Orchestration, d'Audit Nocturne & de Curation Automatisée de Flux Streaming</b></p>

  <p>
    <img src="https://img.shields.io/badge/Python-3.11-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python 3.11" />
    <img src="https://img.shields.io/badge/Google_Apps_Script-JavaScript-4285F4?style=for-the-badge&logo=google&logoColor=white" alt="Google Apps Script" />
    <img src="https://img.shields.io/badge/Frontend-Vanilla_CSS3-1572B6?style=for-the-badge&logo=css3&logoColor=white" alt="Vanilla CSS3" />
    <img src="https://img.shields.io/badge/GitHub_Actions-Automated_Crawler-2088FF?style=for-the-badge&logo=githubactions&logoColor=white" alt="GitHub Actions" />
    <img src="https://img.shields.io/badge/Anti_Cloudflare-Cloudscraper_&_ScraperAPI-FF6C37?style=for-the-badge&logo=cloudflare&logoColor=white" alt="Cloudscraper & Proxy" />
  </p>

  <p>
    <i>Une infrastructure autonome en 3 couches dédiée à la découverte, la vérification en temps réel et la curation intelligente de catalogues de streaming (Films, Séries, Animés). Design réactif "Zero-Framework" garantissant une compatibilité universelle anti-blocage.</i>
  </p>

</div>

---

## 📖 Sommaire

- [À propos du projet](#-à-propos-du-projet)
- [Fonctionnalités clés](#-fonctionnalités-clés)
- [Architecture & Pipeline Automatisé](#-architecture--pipeline-automatisé)
- [Structure du Projet](#-structure-du-projet)
- [Sécurité & Anti-Contournement Bot](#-sécurité--anti-contournement-bot)
- [Configuration & Déploiement](#-configuration--déploiement)
- [Design System & Ergonomie UX](#-design-system--ergonomie-ux)

---

## 💡 À propos du projet

**FindStream** résout le problème critique de l'obsolescence rapide des liens de streaming (blocages FAI, changements de domaine, fermetures de serveurs). 

Plutôt que de s'appuyer sur un annuaire statique mis à jour manuellement, **FindStream** déploie une infrastructure hybride qui :
1. **Chasse continuellement les nouvelles adresses** via un crawler nocturne Python surveillant les canaux de communication officiels (Telegram `/s/`, annuaires).
2. **Audite l'état de santé du réseau** chaque nuit et remplace automatiquement les sites morts ("🔴 Hors Ligne") par des alternatives viables extraites de classements en ligne.
3. **Filtre la donnée à la source** pour empêcher la pollution du catalogue (exclusion stricte des CDN, API, scripts Google Fonts ou réseaux sociaux).
4. **Sert un dashboard ultra-rapide** sans aucun framework lourd (100% Vanilla CSS/JS), garantissant une exécution fluide et immunisée contre les bloqueurs de scripts tiers (uBlock, protections Chrome/CORS).

---

## 🌟 Fonctionnalités clés

### 🤖 Automation Nocturne & Remplacement Autonome (Self-Healing)
* **Crawler Python Chasseur (22h00)** : Analyse automatique de `sources.txt` avec calcul déterministe d'un score de qualité (détection de lecteurs vidéo `iframe`, `jwplayer`, tags `VF`, `VOSTFR`, `HD`).
* **Audit de Santé & Redirection (Google Apps Script)** : Test systématique des codes de réponse HTTP. En cas de redirection (301/302), l'URL est mise à jour instantanément.
* **Auto-Remplacement via Leaderboard** : Si un site tombe, le script extrait un domaine de secours valide sur STMGarenix, vérifie son authenticité et met à jour la base de données sans intervention humaine.

### 🛡️ Filtre Intelligent & Anti-Pollution (Source-Level)
* **Validation de Domaine Strict** : Seules les extensions de streaming légitimes (`.to`, `.com`, `.net`, `.sx`, etc.) sont acceptées.
* **Exclusion des Paramètres & Scripts** : Rejet automatique des liens comportant des paramètres complexes (`?`, `=`) ou pointant vers des actifs système (`fonts.googleapis.com`, `gstatic`, etc.).

### 📱 Frontend Dynamic & UX Moderne
* **Bouton Switch "Double-Vue" (Google Drive Style)** : Interrupteur fluide permettant de basculer entre la vue **Grille (Bento Box)** et la vue **Liste (Cases Longues)** avec mémorisation de la préférence (`localStorage`).
* **Menu Latéral & Thème Synchrone** : Toggle Jour/Nuit intégré dans la barre latérale et responsive design optimisé pour tous les écrans (avec bascule automatique en "Cases Longues" sur smartphones $\le 404\text{px}$).
* **Tri Intelligent** : Les sites hors ligne (🔴) sont automatiquement relégués en bas de liste pour ne pas polluer l'expérience utilisateur, tandis que les sites actifs restent triés par ordre alphabétique.
* **Gestion des Favoris en Local** : Sauvegarde instantanée et anonyme des sites préférés (`localStorage`).

---

## 🏗️ Architecture & Pipeline Automatisé

Le projet s'appuie sur une séparation stricte des responsabilités entre la collecte, l'orchestration backend et le rendu frontend.

```text
  ┌──────────────────────────────────────────────────────────┐
  │                 1. COLLECTE (GitHub Actions)             │
  │  Crawler Python (22h00) -> Scrape sources.txt (Telegram)  │
  └────────────────────────────┬─────────────────────────────┘
                               │ 2. POST Webhook JSON (WEBHOOK_TOKEN)
                               ▼
  ┌──────────────────────────────────────────────────────────┐
  │              2. ORCHESTRATION & BASE DE DONNÉES           │
  │  Google Apps Script + Sheet (Garde en mémoire le Cache)  │
  │  - Audit de Santé Nocturne via Proxy ScraperAPI          │
  │  - Fallback 2-Steps : Mode Éco (1 crédit) -> Urgence JS   │
  │  - Auto-Remplacement via Leaderboard STMGarenix          │
  └────────────────────────────┬─────────────────────────────┘
                               │ 3. API REST (doGet + Cache 6h)
                               ▼
  ┌──────────────────────────────────────────────────────────┐
  │                 3. DASHBOARD CLIENT (Netlify)            │
  │  Vanilla JS & CSS3 (Zero Dependancy / Anti-Blocage Chrome)│
  │  - Tri A-Z (Actifs) + Relégation des Inactifs (Bas)      │
  │  - Switch Layout Bento / Long Cards                      │
  └──────────────────────────────────────────────────────────┘
