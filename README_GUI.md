# Trustoo Scraper GUI

Een eenvoudige grafische interface voor de Trustoo scraper.

## Gebruik

### GUI starten

```bash
python gui.py
```

Of vanuit de virtual environment:

```bash
source venv/bin/activate  # Op macOS/Linux
# of
venv\Scripts\activate     # Op Windows

python gui.py
```

## Functies

### 1. URL invoeren
- Voer de Trustoo URL in die je wilt scrapen
- Standaard: `https://trustoo.nl/nederland/elektricien/`

### 2. Bestandsmodus kiezen

**Nieuw bestand aanmaken:**
- Start met een lege dataset
- Nieuwe bestandsnamen kunnen worden opgegeven (optioneel)
- Als geen bestandsnamen worden opgegeven, gebruikt het script de standaard namen:
  - `trustoo_elektriciens.csv`
  - `trustoo_elektriciens.xlsx`

**Doorgaan in bestaand bestand:**
- Laadt automatisch bestaande data uit `trustoo_elektriciens.csv` of `trustoo_elektriciens.xlsx`
- Voegt nieuwe bedrijven toe aan de bestaande dataset
- Hervat vanaf het laatste checkpoint (aantal klikken)

### 3. Bestandsnamen (optioneel)
- Je kunt aangepaste bestandsnamen opgeven voor CSV en Excel
- Klik op "Bladeren..." om een bestand te kiezen of een nieuwe naam te geven
- Als je niets invult, worden de standaard namen gebruikt

### 4. Starten
- Klik op "Start Scrapen" om te beginnen
- De browser opent automatisch (niet headless)
- Je ziet de voortgang in het output venster
- Klik op "Stop" om te stoppen (let op: dit is een zachte stop)

## Output

- Alle output van het script wordt getoond in het output venster
- Status updates worden getoond in de statusbalk onderaan
- Bij voltooiing krijg je een melding met het totaal aantal verzamelde bedrijven

## Tips

- **Voor het eerst gebruiken:** Kies "Nieuw bestand aanmaken"
- **Verder gaan na stoppen:** Kies "Doorgaan in bestaand bestand" - het script hervat automatisch vanaf waar je was gebleven
- **Stop functie:** De stop knop vraagt om bevestiging. Het script stopt na de huidige actie. Voor direct stoppen, sluit je de browser handmatig.

## Troubleshooting

- **GUI start niet:** Zorg dat je Python 3 heeft geïnstalleerd en tkinter beschikbaar is
- **Geen output:** Check of de URL correct is en of je internetverbinding werkt
- **Script stopt niet:** Sluit de browser handmatig of gebruik Ctrl+C in de terminal

