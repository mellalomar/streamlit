# Dash Streamlit — Analyse carrière chevaux

Application Streamlit pour analyser les cumuls par cheval et par race.

Colonnes attendues dans l'Excel (`horses_2025_carriere.xlsx`):
- `ID_CHEVAL` (identifiant cheval)
- `PLACE` (nombre de places / victoires selon vos données)
- `ALLOCATION_VICTOIRE` (montant cumulé victoire)
- `ALLOCATION_PLACE` (montant cumulé place)
- `CODE_RACE_CHEVAL` (ou `RACE`/`code_race_cheval`) — utilisé pour le groupage par race
- `DATE_COURSE` (optionnel) — utilisé pour filtrer l'année 2025

Usage (PowerShell) :

```powershell
python -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run app.py
```

Fonctions principales :
- Choix de période : `Année 2025` (filtre par `DATE_COURSE`) ou `Carrière complète` (toutes les lignes)
- Agrégation par `ID_CHEVAL` et `RACE` (somme des montants et places) — reproduit la logique des requêtes SQL
- Filtres comparatifs sur `PLACE`, `ALLOCATION_VICTOIRE`, `ALLOCATION_PLACE` avec opérateurs (>, <, ≥, ≤, =)
- Résumé par race (équivalent `GROUP BY race` + `COUNT(DISTINCT id_cheval)`) et tableau détaillé
- Téléchargement CSV des chevaux filtrés

Si tu veux que j'ajoute une option pour reproduire exactement la requête SQL (par exemple limiter les races aux codes ('PSAN','PSA','A2575','AA2A5') ou une période différente), dis-moi et j'adapte l'app.
