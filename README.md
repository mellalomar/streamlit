# Dashboard des gains par PROPRIETAIRE (Streamlit)

Petit dashboard Streamlit pour visualiser les gains par `PROPRIETAIRE` à partir du fichier `Extraction_gains_2025.xlsx`.

Fichiers ajoutés:
- `streamlit_app.py` : l'application Streamlit.
- `requirements.txt` : dépendances Python.

Colonnes utilisées : `PROPRIETAIRE`, `PRIME_NAISSEUR_CHEVAL`, `ALLOCATION_VICTOIRE`, `ALLOCATION_PLACE`. L'app calcule aussi une colonne `TOTAL` = somme des trois.

Comment lancer (PowerShell / Windows):

```powershell
# créer un environnement virtuel (optionnel)
python -m venv .venv; .\.venv\Scripts\Activate.ps1

# installer les dépendances
pip install -r requirements.txt

# lancer l'app (depuis le dossier du projet)
streamlit run streamlit_app.py
```

Notes:
- Le chemin par défaut du fichier Excel est défini dans la barre latérale de l'app; modifiez-le si votre fichier est ailleurs.
- L'app propose un filtre par nom de propriétaire, un choix de métrique (chaque colonne séparément ou total), et le téléchargement CSV des résultats affichés.

Améliorations possibles : filtres par date/course, graphiques temporels, export Excel, pagination, et gestion des propriétaires avec accents.
