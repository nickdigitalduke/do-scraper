# Railway Deployment Guide

## Stappen om de scraper op Railway te deployen:

### 1. Voorbereiding

1. **GitHub Repository maken** (als je dat nog niet hebt):
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin <jouw-github-repo-url>
   git push -u origin main
   ```

### 2. Railway Setup

1. Ga naar [railway.app](https://railway.app) en maak een account
2. Klik op "New Project"
3. Kies "Deploy from GitHub repo"
4. Selecteer je repository

### 3. Environment Variables instellen

In Railway dashboard, ga naar je project → Variables tab:

- `SECRET_KEY`: Genereer een willekeurige string (bijv. gebruik `openssl rand -hex 32`)
- `ADMIN_PASSWORD`: Het wachtwoord voor login (standaard: `admin123` - **VERANDER DIT!**)
- `PORT`: Railway stelt dit automatisch in, hoef je niet te zetten

### 4. Build Settings

Railway detecteert automatisch dat het een Python project is. Zorg dat:
- `requirements.txt` aanwezig is
- `app.py` is het start script
- `nixpacks.toml` is aanwezig voor Chrome/Chromium support

### 5. Deploy

Railway start automatisch met deployen. Je kunt de logs bekijken in het dashboard.

### 6. Toegang

Na deployment krijg je een URL zoals: `https://jouw-project.railway.app`

**Login gegevens:**
- Gebruikersnaam: `admin`
- Wachtwoord: Het wachtwoord dat je hebt ingesteld in `ADMIN_PASSWORD`

## Belangrijke Notities:

1. **Chrome/Chromium**: Railway gebruikt Nixpacks om Chrome te installeren voor Selenium
2. **Headless Mode**: De scraper draait automatisch in headless mode op Railway
3. **Bestanden**: Gescrapte bestanden worden opgeslagen in de Railway filesystem (tijdelijk)
4. **Download**: Gebruikers moeten de bestanden downloaden via de web interface (nog toe te voegen)

## Troubleshooting:

- **Chrome niet gevonden**: Zorg dat `nixpacks.toml` aanwezig is
- **Port error**: Railway stelt PORT automatisch in, gebruik `os.environ.get('PORT', 5000)`
- **Memory issues**: Railway free tier heeft beperkte memory, grote scrapes kunnen problemen geven

## Veiligheid:

- **VERANDER HET ADMIN WACHTWOORD** in production!
- Gebruik een sterke `SECRET_KEY`
- Overweeg meerdere gebruikers toe te voegen (pas `USERS` dict aan in `app.py`)

