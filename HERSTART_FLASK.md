# Hoe Flask App Herstarten

## Methode 1: Terminal gebruiken (aanbevolen)

1. **Zoek het terminal venster waar Flask draait**
   - Je ziet daar waarschijnlijk iets zoals: `Running on http://127.0.0.1:5000`

2. **Stop Flask:**
   - Druk op `Ctrl + C` (of `Cmd + C` op Mac)
   - Wacht tot Flask volledig is gestopt

3. **Start Flask opnieuw:**
   ```bash
   python app.py
   ```
   of
   ```bash
   flask run
   ```

## Methode 2: Process killen (als Ctrl+C niet werkt)

1. **Zoek het Flask proces:**
   ```bash
   # Op Mac/Linux:
   ps aux | grep flask
   # of
   ps aux | grep python
   ```

2. **Kill het proces:**
   ```bash
   kill <PID>
   # Als dat niet werkt:
   kill -9 <PID>
   ```

3. **Start opnieuw:**
   ```bash
   python app.py
   ```

## Methode 3: Automatisch herstarten met debug mode

Als je `debug=True` gebruikt, herstart Flask automatisch bij code wijzigingen:

```python
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)  # debug=True
```

**LET OP:** Debug mode is alleen voor ontwikkeling, niet voor productie!

## Belangrijk na code wijzigingen:

- **ALTIJD Flask herstarten** na code wijzigingen
- **Sluit alle browser windows** die door de scraper zijn geopend
- **Check of oude processen nog draaien** met `ps aux | grep python`

