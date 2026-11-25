# Lead Insights – vacatures in Limburg

Wekelijks overzicht van vacatures voor interessante functies per bedrijf, als input voor Mojeo.

## Bronnen
- **Banenrijk Limburg**: via de sitemap en de gestructureerde vacaturedata (JobPosting) op elke vacaturepagina.
- Later toe te voegen: werk.nl, Google Jobs via SerpApi (inclusief Indeed en LinkedIn).

## Gebruik
```bash
pip install -r requirements.txt
python run.py            # ophalen + rapport
python run.py --report   # alleen rapport opnieuw maken (bv. na wijzigen config)
```

De eerste run haalt alle vacatures op (ongeveer 15 minuten). Daarna worden alleen nieuwe vacatures opgehaald.

## Relevantie instellen
Pas `config.yaml` aan: trefwoorden in de functietitel, branches, regio of plaatsen, en welke bemiddelaars je uitsluit.

## Output
`reports/vacatureradar_<jaar>-W<week>.html` is het weekrapport voor de board: één bestand dat in elke browser opent (ook offline), met filters, en via Ctrl/Cmd+P als liggend A4 naar PDF kan.

`reports/vacatures_<jaar>-W<week>.xlsx` bevat drie tabbladen:
- **Per bedrijf**: open vacatures, nieuw deze week, vorige week en het verschil.
- **Nieuw deze week**
- **Alle open vacatures**

## Automatisch
`.github/workflows/weekly.yml` draait elke maandagochtend en commit de database (`data/vacatures.db`) en het rapport.
