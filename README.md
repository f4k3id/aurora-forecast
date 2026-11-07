# AurorA 🌌

Application locale de prévisions d'aurores boréales (bilingue FR/EN).

- Synchronisation automatique toutes les **5 minutes**
- Données **RNCan** (Space Weather Canada) + **indice Kp NOAA**
- **Notifications macOS** quand l'activité passe à "Stormy" (Orageuse)
- Interface **web** riche + **menubar** native macOS
- **Graphique historique 24h** de l'indice Kp

## Sources

- RNCan : https://www.spaceweather.gc.ca/forecast-prevision/short-court/zone-en.php
- NOAA Planetary K-index : https://services.swpc.noaa.gov/products/noaa-planetary-k-index.json

## Installation

```bash
git clone https://github.com/f4k3id/aurora-forecast.git
cd aurora-forecast
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Lancement rapide (dev)

```bash
source .venv/bin/activate
python menubar.py          # macOS menubar (si rumps est installé)
# ou
python start_web.py        # web seulement
```

Dashboard → http://127.0.0.1:8787

## Créer l'application .app (recommandé pour usage quotidien)

Tu veux une vraie application que tu peux mettre dans `/Applications` et qui reste dans la barre de menu même après fermeture du Terminal.

```bash
# 1. Rends le script exécutable (une seule fois)
chmod +x build_app.sh

# 2. Lance la construction (utilise un Python récent si possible)
./build_app.sh
```

Le script :
- Cherche automatiquement un bon Python (3.11+)
- Crée un environnement de build propre
- Génère une belle icône aurore
- Produit `dist/AurorA.app`

### Installation

```bash
# Copie l'app dans tes Applications
cp -R dist/AurorA.app ~/Applications/
# ou
cp -R dist/AurorA.app /Applications/
```

Puis lance **AurorA** depuis Spotlight (⌘Espace) ou double-clic.

L'icône 🌌 apparaît dans la **barre de menu en haut à droite**.

- Clic gauche → menu avec "Open Dashboard", Refresh, Quit
- Le dashboard web reste accessible à http://127.0.0.1:8787 même quand l'app est "fermée" (elle tourne en arrière-plan)

### Désinstallation

Supprime simplement `AurorA.app` du dossier Applications.

### Dépannage du menubar qui n'apparaît pas

1. Vérifie `~/Library/Logs/AurorA/aurora.log` (le .app écrit des logs très utiles).
2. Assure-toi d'avoir lancé la version **.app** et non le script Python directement.
3. Si tu as utilisé `start_web.py`, l'icône n'apparaît volontairement pas.
4. Reconstruis avec `./build_app.sh` après avoir installé un Python 3.11/3.12 propre (Homebrew recommandé).

## Fonctionnalités

- **Menubar** : icône + statut courant (Kp + niveau zone aurorale)
- **Notifications** : alerte native macOS sur passage en "Stormy"
- **Dashboard web** :
  - Conditions actuelles (3 zones RNCan + Kp)
  - Prévisions 6h / 24h
  - Courbe Kp sur ~24-48h (Chart.js)
  - Switch FR ↔ EN
  - Rafraîchissement auto + bouton manuel
- Historique local persistant (data/history.json)

## Configuration

Édite `aurora/config.py` (port, intervalle, zones qui déclenchent les alertes).

## Lancer au démarrage (macOS)

### Méthode simple (Login Items)
1. Lance `python menubar.py` (ou `start_web.py`)
2. Va dans **Réglages Système > Général > Éléments de connexion**
3. Ajoute le Terminal ou un petit script wrapper.

### Méthode propre (launchd)
Crée `~/Library/LaunchAgents/com.user.aurora.plist` :

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key>
  <string>com.user.aurora</string>
  <key>ProgramArguments</key>
  <array>
    <string>/path/to/aurora-forecast/.venv/bin/python</string>
    <string>/path/to/aurora-forecast/menubar.py</string>
  </array>
  <key>RunAtLoad</key>
  <true/>
  <key>KeepAlive</key>
  <true/>
  <key>StandardOutPath</key>
  <string>/tmp/aurora.log</string>
  <key>StandardErrorPath</key>
  <string>/tmp/aurora.err</string>
</dict>
</plist>
```

Puis :
```bash
launchctl load ~/Library/LaunchAgents/com.user.aurora.plist
```

## Structure du projet

```
AurorA/
├── menubar.py          # Point d'entrée macOS (rumps)
├── start_web.py        # Point d'entrée web pur (toutes plateformes)
├── run.sh
├── requirements.txt
├── aurora/
│   ├── config.py
│   ├── fetcher.py      # RNCan (FR/EN) + NOAA Kp
│   ├── models.py
│   ├── store.py        # Persistance JSON (~/.aurora)
│   ├── scheduler.py    # 5 min polling + logique "Stormy"
│   ├── notifier.py     # Notifications macOS (osascript)
│   └── web/
│       └── server.py   # FastAPI + magnifique dashboard mono-fichier
└── data/ (ignoré)      # Optionnel
```

Le dashboard web est **entièrement autonome** (Tailwind CDN + Chart.js) : pas de build step.

## Licence

Usage personnel. Améliorations bienvenues.


## Stack

Python 3 (Flask, requests, BeautifulSoup, rumps), packaged as a macOS `.app` with **py2app** (`./build_app.sh`). Build artifacts (`build/`, `dist/`, `.app`) and virtualenvs are not versioned.
