# Hoe Flask App Starten

## Belangrijk: Je moet `app.py` gebruiken, NIET `gui.py`!

`gui.py` is een oude GUI versie. De nieuwe web interface draait via `app.py`.

## Methode 1: Met het start script (aanbevolen)

```bash
cd /Users/nickvangeffen/.cursor/worktrees/trustoo-scraper/itz
./start.sh
```

## Methode 2: Handmatig starten

1. **Open een terminal**

2. **Navigeer naar de juiste directory:**
   ```bash
   cd /Users/nickvangeffen/.cursor/worktrees/trustoo-scraper/itz
   ```

3. **Activeer het virtual environment:**
   ```bash
   source venv/bin/activate
   ```
   
   Je ziet nu `(venv)` voor je prompt.

4. **Start Flask:**
   ```bash
   python app.py
   ```

5. **Open je browser:**
   - Ga naar: `http://localhost:5000` of `http://127.0.0.1:5000`
   - Log in met:
     - Username: `admin`
     - Password: `admin123`

## Methode 3: Met Python direct (als venv al actief is)

```bash
cd /Users/nickvangeffen/.cursor/worktrees/trustoo-scraper/itz
source venv/bin/activate
python app.py
```

## Flask Herstarten

Als je code hebt aangepast:

1. **Stop Flask:**
   - Ga naar het terminal venster waar Flask draait
   - Druk op `Ctrl + C` (of `Cmd + C` op Mac)

2. **Start opnieuw:**
   ```bash
   python app.py
   ```

## Problemen oplossen

### "ModuleNotFoundError: No module named 'flask'"
- Zorg dat je het virtual environment hebt geactiveerd: `source venv/bin/activate`
- Je moet `(venv)` zien voor je prompt

### "Port already in use"
- Iemand anders gebruikt poort 5000
- Stop de andere Flask app of gebruik een andere poort:
  ```bash
  PORT=5001 python app.py
  ```

### "Permission denied" bij start.sh
- Maak het script uitvoerbaar:
  ```bash
  chmod +x start.sh
  ```

## Belangrijk

- **Gebruik altijd `app.py`, NIET `gui.py`**
- **Activeer altijd het virtual environment eerst**
- **Herstart Flask na code wijzigingen**

