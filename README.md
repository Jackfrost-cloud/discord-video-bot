# Discord Video Bot

Bot Discord permettant d'envoyer un lien vidéo (YouTube, TikTok, Instagram, Twitter/X et
toute autre plateforme compatible `yt-dlp`), de choisir une qualité via des boutons, puis
de recevoir le fichier — directement en DM si sa taille le permet, ou via un lien
temporaire sinon.

## 1. Architecture

```text
discord-video-bot/
├── bot/
│   ├── main.py               # point d'entrée, démarrage bot + serveur fallback + nettoyage
│   ├── config.py             # configuration centralisée (.env)
│   ├── cogs/
│   │   ├── download.py       # commande /download, boutons de qualité, orchestration
│   │   └── events.py         # détection des URLs envoyées en DM
│   ├── services/
│   │   ├── extractor.py      # métadonnées + qualités disponibles (yt-dlp, sans téléchargement)
│   │   ├── downloader.py     # téléchargement effectif (yt-dlp + fusion FFmpeg)
│   │   ├── media_processor.py# vérification et finalisation du fichier
│   │   ├── storage.py        # abstraction StorageProvider (LocalStorage fournie)
│   │   ├── fileserver.py     # serveur HTTP interne pour les liens temporaires
│   │   ├── queue.py          # file d'attente, limites par utilisateur, cooldown
│   │   └── cleanup.py        # nettoyage des fichiers temporaires et liens expirés
│   ├── models/download_job.py
│   └── utils/                # urls.py, formatting.py, logging.py
├── tests/
├── .env.example
├── Dockerfile / docker-compose.yml
└── requirements.txt
```

## 2. Technologies

- **Python 3.12+**, `discord.py` 2.x (slash commands + composants UI)
- **yt-dlp** comme moteur d'extraction et de téléchargement
- **FFmpeg**, appelé automatiquement par yt-dlp pour fusionner les flux vidéo/audio séparés
- **aiohttp**, pour le petit serveur HTTP interne qui sert les liens de téléchargement
  temporaires (fallback fichiers trop volumineux)
- **pytest** + **pytest-asyncio** pour les tests

## 3. Décisions techniques principales

- **Asynchrone de bout en bout** : les appels `yt-dlp` (bloquants) tournent dans
  `asyncio.to_thread`, jamais dans la boucle événementielle du bot.
- **Sélecteurs de format dynamiques** (`bestvideo[height<=X]+bestaudio/best[height<=X]`) :
  le bot ne propose jamais une qualité qui n'existe pas réellement pour la vidéo demandée.
- **Queue + sémaphore** pour limiter la concurrence globale et par utilisateur, avec cooldown
  configurable — un flot de téléchargements ne bloque jamais les autres utilisateurs.
- **Stockage abstrait (`StorageProvider`)** : `LocalStorage` est fournie et fonctionnelle,
  mais le code n'est pas couplé à un fournisseur — un `S3Storage` peut être ajouté en
  implémentant la même interface.
- **Sécurité du fallback** : chaque fichier temporaire est accessible via un token aléatoire
  (`secrets.token_urlsafe`), jamais via son chemin système ; les liens expirent et sont
  nettoyés automatiquement.
- **Aucune fausse promesse** : si une qualité, une plateforme ou une authentification n'est
  pas disponible, le bot le dit clairement plutôt que de simuler un résultat.

## 4. Installation

```bash
git clone [<url-de-ton-repo>](https://github.com/Jackfrost-cloud/discord-video-bot.git)
cd discord-video-bot
python -m venv .venv
source .venv/bin/activate   # Windows : .venv\Scripts\activate
pip install -r requirements.txt
```

### Installation de FFmpeg

- **Windows** : télécharge une build sur https://www.gyan.dev/ffmpeg/builds/, extrais
  l'archive et ajoute le dossier `bin` au `PATH` (ou renseigne `FFMPEG_LOCATION` dans `.env`).
- **Linux (Debian/Ubuntu)** :
  ```bash
  sudo apt update && sudo apt install ffmpeg
  ```
- **Docker** : rien à faire, FFmpeg est installé dans l'image (voir `Dockerfile`).

## 5. Configuration

Copie `.env.example` vers `.env` et renseigne au minimum `DISCORD_TOKEN` :

```bash
cp .env.example .env
```

Chaque variable est documentée dans `.env.example` (concurrence, timeouts, taille max
Discord, rétention des liens temporaires, etc.).

## 6. Création du bot Discord

1. Va sur https://discord.com/developers/applications et crée une **New Application**.
2. Dans l'onglet **Bot**, clique sur **Reset Token** et copie le token dans `DISCORD_TOKEN`
   (ne le publie jamais, ne le commit jamais).
3. Toujours dans **Bot**, active l'intent **Message Content Intent** (nécessaire pour
   détecter les URLs envoyées en DM).
4. Dans **OAuth2 > URL Generator**, coche le scope `bot` et `applications.commands`, puis
   les permissions `Send Messages`, `Attach Files`, `Embed Links`, `Use Slash Commands`.
5. Ouvre l'URL générée pour inviter le bot sur ton serveur.

## 7. Lancement

```bash
python -m bot.main
```

Au premier démarrage, le bot synchronise automatiquement la commande slash `/download`
(cela peut prendre jusqu'à une heure pour apparaître globalement, instantané sur un
serveur de test si tu limites la synchronisation à une guilde).

## 8. Tests

```bash
pip install -r requirements.txt
pytest
```

Les tests couvrent la validation d'URL, le formatage, la génération de noms de fichiers
sûrs, le modèle de job et le comportement de la file d'attente (limites par utilisateur).
Ils ne téléchargent aucune vidéo réelle — `yt-dlp` n'est pas appelé pendant les tests.

## 9. Déploiement Docker

```bash
cp .env.example .env   # puis renseigne DISCORD_TOKEN et le reste
docker compose up -d
```

Le conteneur inclut Python, toutes les dépendances et FFmpeg. Les répertoires
`./downloads` et `./tmp` sont montés en volumes pour persister les fichiers en cours de
traitement entre redémarrages.

## 10. Problèmes connus / limites

- Le lien de fallback est servi par un serveur HTTP **sans HTTPS natif** : en production,
  place-le derrière un reverse proxy (nginx, Caddy, Traefik) qui termine le TLS avant de
  transmettre `PUBLIC_BASE_URL`.
- `DISCORD_MAX_FILE_SIZE` doit être ajusté au niveau de boost réel de ton serveur (25 Mo par
  défaut, 50 Mo ou 100 Mo selon les boosts, ou la limite spécifique si le bot tourne sur un
  compte avec Nitro).
- Le contenu protégé par DRM, une authentification ou un paywall n'est volontairement pas
  géré : le bot échoue proprement plutôt que de contourner une protection.
- `STORAGE_PROVIDER` ne fournit que `local` par défaut ; un fournisseur distant (S3, etc.)
  nécessite d'implémenter `StorageProvider` dans `bot/services/storage.py`.
