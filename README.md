
# Crazed-Trading (Demo, no API)

Mobilfreundliche Streamlit-Demo zum Testen eines anpassbaren Futures/Grid-Bots – **ohne Börsen-API**.
- Grid-Level frei einstellbar & während des Laufens verschiebbar
- Range live anpassbar
- Fake-Live-Kurs (Random Walk) oder manuelles Tick-Advance
- Order-/Trade-Tabellen & PnL (vereinfacht)

## Lokal starten
```bash
pip install -r requirements.txt
streamlit run app.py
```
Dann im Browser öffnen.

## Deployment (Streamlit Cloud, kostenlos)
1. Repo auf GitHub pushen.
2. https://share.streamlit.io → "New app", Repo & Branch wählen, `app.py` als Entry setzen.
3. **Secrets/API** werden hier **nicht** benötigt (Demo).

## Ordner
```
/assets   → Logo & Styles
/data     → Demo-Daten (CSV)
/pages    → Unterseiten (Dashboard, Analyse, Bot-Demo, Orders, Logs, Settings)
app.py    → Landing mit "Bot erstellen"
```

**Hinweis:** Dies ist eine vereinfachte Simulation. Keine Finanzberatung.
