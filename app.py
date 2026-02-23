import streamlit as st
import pandas as pd
import plotly.express as px
import numpy as np
from pathlib import Path

st.set_page_config(page_title="Dash Carrière Chevaux", layout="wide")

# Helper for query-param / session navigation compatibility
def _get_page_param():
    # Prefer the modern read-only API
    if hasattr(st, "query_params"):
        params = st.query_params
        return params.get("page", [st.session_state.get("page", "main")])[0]
    # Fall back to experimental getter
    if hasattr(st, "experimental_get_query_params"):
        params = st.experimental_get_query_params()
        return params.get("page", [st.session_state.get("page", "main")])[0]
    # Last resort: session_state
    return st.session_state.get("page", "main")


def _set_page_param(value: str) -> bool:
    """Set the page param in a compatible way.

    Returns True if a programmatic rerun is expected, False if caller
    may need to prompt the user to reload.
    """
    # Preferred setter
    if hasattr(st, "set_query_params"):
        try:
            st.set_query_params(page=value)
            return True
        except Exception:
            pass
    # experimental setter
    if hasattr(st, "experimental_set_query_params"):
        try:
            st.experimental_set_query_params(page=value)
            return True
        except Exception:
            pass
    # fallback: set in session_state and attempt to rerun
    st.session_state["page"] = value
    if hasattr(st, "experimental_rerun"):
        try:
            st.experimental_rerun()
            return True
        except Exception:
            pass
    # nothing we can do programmatically on very old streamlit — caller will handle
    return False

st.title("📊 Dash — Analyse carrière des chevaux")
st.markdown("👋 Bonjour ! Bienvenue dans le tableau de bord d'analyse de carrière des chevaux.")
st.markdown(
    "Analyse des colonnes: `ID_CHEVAL`, `PLACE`, `ALLOCATION_VICTOIRE`, `ALLOCATION_PLACE`, `CODE_RACE_CHEVAL`, `DATE_COURSE`."
)

# --- Page navigation: session_state-based (immediate, compatible)
# Determine current page from session_state first; default to 'main'
page = st.session_state.get("page", _get_page_param())
st.session_state["page"] = page

with st.sidebar:
    # Only show the "open gains" button when we're not already on the gains page.
    # This avoids having two navigation buttons in the sidebar which can require
    # multiple clicks due to preserved widget state across reruns.
    if st.session_state.get("page") != "gain":
        if st.button("→ Ouvrir : Gains propriétaires", key="open_page_gain"):
            # Use session_state navigation so Streamlit reruns immediately on button click
            st.session_state["page"] = "gain"

if st.session_state.get("page") == "gain":
    # importer et afficher la page externe (page_gain.py)
    try:
        import page_gain
        page_gain.show_page()
    except Exception as e:
        st.error(f"Impossible d'afficher la page de gains: {e}")
    st.stop()

# --- Charger le fichier (upload ou local) ---
uploaded_file = st.sidebar.file_uploader("Téléversez le fichier Excel (horses_2025_carriere.xlsx)", type=["xlsx"]) 
local_path = Path("DATA/horses_2025_carriere.xlsx")

@st.cache_data
def load_excel(file) -> pd.DataFrame:
    try:
        return pd.read_excel(file, engine="openpyxl")
    except Exception:
        return pd.read_excel(file)

if uploaded_file is not None:
    df = load_excel(uploaded_file)
elif local_path.exists():
    st.sidebar.success(f"Fichier local détecté: {local_path.name}")
    df = load_excel(local_path)
else:
    st.warning("Aucun fichier fourni. Déposez `horses_2025_carriere.xlsx` via l'uploader ou placez-le dans le dossier de l'app.")
    st.stop()

# --- Vérifications et standardisation des colonnes ---
expected_cols = ["ID_CHEVAL", "PLACE", "ALLOCATION_VICTOIRE", "ALLOCATION_PLACE"]
optional_race_cols = ["CODE_RACE_CHEVAL", "code_race_cheval", "RACE", "race"]
optional_age_cols = ["CODE_AGE_CHEVAL", "code_age_cheval", "AGE", "age"]
date_col = "DATE_COURSE"

missing = [c for c in expected_cols if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes dans l'Excel: {missing}. Noms attendus: {expected_cols}")
    st.write("Colonnes trouvées:", list(df.columns))
    st.stop()

# Copy and normalize
df = df.copy()
df["ID_CHEVAL"] = df["ID_CHEVAL"].astype(str)

# Detect race column and standardize to RACE
race_col = None
for col in optional_race_cols:
    if col in df.columns:
        race_col = col
        df["RACE"] = df[col].astype(str)
        break

if race_col is None:
    st.warning("Colonne de race non trouvée. Les analyses par race seront désactivées.")
    has_race = False
else:
    has_race = True

# Detect age column and standardize to AGE
age_col = None
for col in optional_age_cols:
    if col in df.columns:
        age_col = col
        df["AGE"] = df[col].astype(str)
        break

if age_col is None:
    st.warning("Colonne d'âge non trouvée. Les analyses par âge seront désactivées.")
    has_age = False
else:
    has_age = True

# Handle date column
has_date = date_col in df.columns
if has_date:
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    if df[date_col].isna().all():
        has_date = False
        st.warning("La colonne DATE_COURSE existe mais n'a pas pu être convertie correctement en dates. Le filtre période sera désactivé.")

# numeric conversion
for c in ["PLACE", "ALLOCATION_VICTOIRE", "ALLOCATION_PLACE"]:
    df[c] = pd.to_numeric(df[c], errors="coerce").fillna(0)

# --- Période : Année 2025 vs Carrière complète ---
st.sidebar.markdown("---")
st.sidebar.subheader("📅 Période d'analyse")
if has_date:
    period_choice = st.sidebar.radio("Sélectionnez la période", ("📅 Année 2025", "🏆 Carrière complète"))
    if period_choice == "📅 Année 2025":
        # filter rows to 2025
        df = df[df[date_col].dt.year == 2025]
        st.sidebar.success(f"Filtre appliqué: Année 2025 — {len(df)} lignes restantes")
    else:
        st.sidebar.info(f"Carrière complète — {len(df)} lignes")
else:
    st.sidebar.warning("DATE_COURSE absent — affichage sur toute la carrière disponible")

# --- Agrégation par cheval + race (comme dans les requêtes SQL)
# Ajouter un indicateur WIN pour compter les victoires (PLACE == 1)
df = df.copy()
df["WIN"] = (df["PLACE"] == 1).astype(int)

# Agrégation par cheval uniquement (ID_CHEVAL) — utilisée pour les 3 filtres
# On conserve RACE et AGE comme attributs du cheval en prenant la première valeur
agg_dict = {
    "PLACE": "sum",
    "WIN": "sum",
    "ALLOCATION_VICTOIRE": "sum",
    "ALLOCATION_PLACE": "sum",
}

# Si RACE/AGE existent, les agréger en prenant la première valeur rencontrée par ID_CHEVAL
if has_race:
    agg_dict["RACE"] = lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else "N/A"
else:
    # placeholder column for downstream code
    df["RACE"] = "N/A"
    agg_dict["RACE"] = lambda x: "N/A"

if has_age:
    agg_dict["AGE"] = lambda x: x.dropna().iloc[0] if len(x.dropna()) > 0 else "N/A"
else:
    df["AGE"] = "N/A"
    agg_dict["AGE"] = lambda x: "N/A"

# df_grouped : agrégat par cheval unique — utilisé pour appliquer les filtres (NB_VICTOIRES, ALLOC...)
df_grouped = df.groupby("ID_CHEVAL", as_index=False).agg(agg_dict)
df_grouped = df_grouped.rename(columns={"WIN": "NB_VICTOIRES"})

# Si la colonne CODE_CATEGORISATION_COURSE existe au niveau row, joindre la première valeur par cheval
if "CODE_CATEGORISATION_COURSE" in df.columns:
    cat_map = df.groupby("ID_CHEVAL")["CODE_CATEGORISATION_COURSE"].first().to_dict()
    df_grouped["CODE_CATEGORISATION_COURSE"] = df_grouped["ID_CHEVAL"].map(cat_map).fillna("N/A")

# Si la colonne CODE_RACE_CHEVAL existe (code race distinct de RACE), joindre la première valeur par cheval
if "CODE_RACE_CHEVAL" in df.columns:
    code_race_map = df.groupby("ID_CHEVAL")["CODE_RACE_CHEVAL"].first().to_dict()
    df_grouped["CODE_RACE_CHEVAL"] = df_grouped["ID_CHEVAL"].map(code_race_map).fillna("N/A")

# --- Filtres comparatifs (comme en SQL) ---
st.sidebar.markdown("---")
st.sidebar.subheader("🎯 Filtres")

# Filtre optionnel par âge (EN PREMIER, avant les autres filtres)
if has_age:
    st.sidebar.subheader("🎂 Filtre par Âge")
    ages_available = sorted(df_grouped["AGE"].unique().tolist())
    age_filter = st.sidebar.multiselect("Sélectionnez les âges", ages_available, default=ages_available)
    mask_age = df_grouped["AGE"].isin(age_filter) if age_filter else pd.Series(True, index=df_grouped.index)
else:
    mask_age = pd.Series(True, index=df_grouped.index)

# Filtres additionnels basés sur les colonnes (CODE_CATEGORISATION_COURSE, CODE_RACE_CHEVAL)
if "CODE_CATEGORISATION_COURSE" in df_grouped.columns:
    cats_available = sorted(df_grouped["CODE_CATEGORISATION_COURSE"].dropna().unique().tolist())
    cat_filter = st.sidebar.multiselect("CODE_CATEGORISATION_COURSE", options=cats_available, default=cats_available)
    mask_cat = df_grouped["CODE_CATEGORISATION_COURSE"].isin(cat_filter) if cat_filter else pd.Series(True, index=df_grouped.index)
else:
    mask_cat = pd.Series(True, index=df_grouped.index)

# Filtre par code race si disponible, sinon par RACE
if "CODE_RACE_CHEVAL" in df_grouped.columns:
    race_codes = sorted(df_grouped["CODE_RACE_CHEVAL"].dropna().unique().tolist())
    race_code_filter = st.sidebar.multiselect("CODE_RACE_CHEVAL", options=race_codes, default=race_codes)
    mask_code_race = df_grouped["CODE_RACE_CHEVAL"].isin(race_code_filter) if race_code_filter else pd.Series(True, index=df_grouped.index)
elif has_race:
    race_codes = sorted(df_grouped["RACE"].dropna().unique().tolist())
    race_code_filter = st.sidebar.multiselect("RACE", options=race_codes, default=race_codes)
    mask_code_race = df_grouped["RACE"].isin(race_code_filter) if race_code_filter else pd.Series(True, index=df_grouped.index)
else:
    mask_code_race = pd.Series(True, index=df_grouped.index)

st.sidebar.markdown("---")
st.sidebar.subheader("📊 Filtres comparatifs")

def comp_select(label, series_max, default=0, step=1):
    col_cond, col_val = st.sidebar.columns([1, 2])
    with col_cond:
        cond = st.selectbox(label, ["≥", ">", "≤", "<", "="], key=f"cond_{label}")
    with col_val:
        val = st.number_input("NB_VICTOIRES", min_value=0, max_value=int(series_max) if series_max>0 else 0, value=default, step=step, key=f"val_{label}")
    return cond, val

# Appliquer les filtres (âge + catégorie + code race) à df_grouped AVANT de calculer les max values pour les selectbox
df_grouped_filtered_by_age = df_grouped[mask_age & mask_cat & mask_code_race].copy()

place_cond, place_val = comp_select("PLACE 1", df_grouped_filtered_by_age["PLACE"].max(), default=0, step=1)
alloc_v_cond, alloc_v_val = comp_select("ALLOCATION_VICTOIRE", df_grouped_filtered_by_age["ALLOCATION_VICTOIRE"].max(), default=0, step=1000)
alloc_p_cond, alloc_p_val = comp_select("ALLOCATION_PLACE", df_grouped_filtered_by_age["ALLOCATION_PLACE"].max(), default=0, step=1000)

def apply_condition(series, condition, value):
    if condition == "≥":
        return series >= value
    if condition == ">":
        return series > value
    if condition == "≤":
        return series <= value
    if condition == "<":
        return series < value
    if condition == "=":
        return series == value
    return pd.Series(True, index=series.index)

# Séparer les masques par critère pour affichage indépendant (sur les données filtrées par âge)
mask_victoires = apply_condition(df_grouped_filtered_by_age["NB_VICTOIRES"], place_cond, place_val)
mask_alloc_v = apply_condition(df_grouped_filtered_by_age["ALLOCATION_VICTOIRE"], alloc_v_cond, alloc_v_val)
mask_alloc_p = apply_condition(df_grouped_filtered_by_age["ALLOCATION_PLACE"], alloc_p_cond, alloc_p_val)

# Masque combiné (tous les critères, sur les données pré-filtrées par âge)
mask_combined = mask_victoires & mask_alloc_v & mask_alloc_p
filtered = df_grouped_filtered_by_age[mask_combined].copy()

# --- Résultats / Metrics ---
col0,col1, col2, col3 = st.columns(4)
# total distinct horses in the (possibly period-filtered and age-filtered) raw data
total_chevaux = df_grouped_filtered_by_age["ID_CHEVAL"].nunique()

# Comptes indépendants par critère (COUNT DISTINCT id_cheval qui satisfont chaque critère séparément, SUR LES DONNÉES FILTRÉES PAR ÂGE)
count_victoires = df_grouped_filtered_by_age[mask_victoires]["ID_CHEVAL"].nunique()
count_alloc_v = df_grouped_filtered_by_age[mask_alloc_v]["ID_CHEVAL"].nunique()
count_alloc_p = df_grouped_filtered_by_age[mask_alloc_p]["ID_CHEVAL"].nunique()

with col0:
    st.metric("Nbr Totale chevaux", total_chevaux)
with col1:
    st.metric("N'ayant pas gagné place", count_victoires)
with col2:
    st.metric("N'ayant pas gagné montant", count_alloc_v)
with col3:
    st.metric("N'ayant pas réçu", count_alloc_p)

# Afficher aussi le résultat combiné (tous critères) sous les metrics

st.markdown("---")

# --- Graphiques Pie : Distribution des races pour chaque filtre + sans filtre ---
st.subheader("🥧 Distribution des races par critère")

if has_race and len(df_grouped_filtered_by_age) > 0:
    pie_col1, pie_col2, pie_col3, pie_col4 = st.columns(4)
    
    # Sans filtre (all data filtrées par âge)
    race_dist_all = df_grouped_filtered_by_age["RACE"].value_counts()
    with pie_col1:
        st.write("*Toutes les races (sans filtre)*")
        if not race_dist_all.empty:
            fig_all = px.pie(names=race_dist_all.index, values=race_dist_all.values)
            st.plotly_chart(fig_all, use_container_width=True, key="pie_all")
        else:
            st.write("Aucune donnée")
    
    # Filtre NB_VICTOIRES
    race_dist_vic = df_grouped_filtered_by_age[mask_victoires]["RACE"].value_counts()
    with pie_col2:
        st.write("*Races (critère NB_VICTOIRES)*")
        if not race_dist_vic.empty:
            fig_vic = px.pie(names=race_dist_vic.index, values=race_dist_vic.values)
            st.plotly_chart(fig_vic, use_container_width=True, key="pie_vic")
        else:
            st.write("Aucune donnée")
    
    # Filtre ALLOCATION_VICTOIRE
    race_dist_alloc_v = df_grouped_filtered_by_age[mask_alloc_v]["RACE"].value_counts()
    with pie_col3:
        st.write("*Races (critère ALLOCATION_VICTOIRE)*")
        if not race_dist_alloc_v.empty:
            fig_alloc_v = px.pie(names=race_dist_alloc_v.index, values=race_dist_alloc_v.values)
            st.plotly_chart(fig_alloc_v, use_container_width=True, key="pie_alloc_v")
        else:
            st.write("Aucune donnée")
    
    # Filtre ALLOCATION_PLACE
    race_dist_alloc_p = df_grouped_filtered_by_age[mask_alloc_p]["RACE"].value_counts()
    with pie_col4:
        st.write("*Races (critère ALLOCATION_PLACE)*")
        if not race_dist_alloc_p.empty:
            fig_alloc_p = px.pie(names=race_dist_alloc_p.index, values=race_dist_alloc_p.values)
            st.plotly_chart(fig_alloc_p, use_container_width=True, key="pie_alloc_p")
        else:
            st.write("Aucune donnée")
    
    st.markdown("---")
else:
    st.info(f"ℹ️ Les graphiques pie ne peuvent pas s'afficher : has_race={has_race}, len(df_grouped_filtered_by_age)={len(df_grouped_filtered_by_age)}")
    st.markdown("---")

# --- Résumé par RACE (équivalent SQL GROUP BY race, COUNT(cheval) ) ---

if has_race:
    st.subheader("📈 Résumé par RACE")
    summary = filtered.groupby("RACE").agg(
        NB_CHEVAUX=("ID_CHEVAL", "nunique"),
        # PLACE_SUM should count wins (PLACE == 1) -> use NB_VICTOIRES which aggregates WIN per cheval
        PLACE_SUM=("NB_VICTOIRES", "sum"),
       # PLACE_AVG=("PLACE", "mean"),
        ALLOC_VICTOIRE_SUM=("ALLOCATION_VICTOIRE", "sum"),
        ALLOC_VICTOIRE_AVG=("ALLOCATION_VICTOIRE", "mean"),
        ALLOC_PLACE_SUM=("ALLOCATION_PLACE", "sum"),
        ALLOC_PLACE_AVG=("ALLOCATION_PLACE", "mean")
    ).reset_index()
    summary = summary.sort_values(by="NB_CHEVAUX", ascending=False).round(2)
    st.dataframe(summary, use_container_width=True)
else:
    st.info("Aucune colonne de race détectée. Le résumé par race est désactivé.")

st.markdown("---")

# --- Résumé par AGE (équivalent SQL GROUP BY age, COUNT(cheval) ) ---
if has_age:
    st.subheader("🎂 Résumé par ÂGE")
    summary_age = filtered.groupby("AGE").agg(
        NB_CHEVAUX=("ID_CHEVAL", "nunique"),
        # Use NB_VICTOIRES to count wins per age group
        PLACE_SUM=("NB_VICTOIRES", "sum"),
        #PLACE_AVG=("PLACE", "mean"),
        ALLOC_VICTOIRE_SUM=("ALLOCATION_VICTOIRE", "sum"),
        ALLOC_VICTOIRE_AVG=("ALLOCATION_VICTOIRE", "mean"),
        ALLOC_PLACE_SUM=("ALLOCATION_PLACE", "sum"),
        ALLOC_PLACE_AVG=("ALLOCATION_PLACE", "mean")
    ).reset_index()
    summary_age = summary_age.sort_values(by="NB_CHEVAUX", ascending=False).round(2)
    st.dataframe(summary_age, use_container_width=True)
else:
    st.info("Aucune colonne d'âge détectée. Le résumé par âge est désactivé.")

st.markdown("---")

# --- Détail chevaux filtrés ---
# (tableau détaillé des chevaux filtrés supprimé)

# --- Visualisations ---
st.markdown("---")
st.subheader("📊 Distributions")
chart_col1, chart_col2 = st.columns(2)

# For distributions we want counts of distinct horses by place and allocations.
# Start from row-level `df` (already period-filtered); then apply age filter if present.
df_rows = df.copy()
if has_age:
    df_rows = df_rows[df_rows["AGE"].isin(age_filter)]

# Distribution: distinct horses grouped by PLACE (count of unique ID_CHEVAL per PLACE)
with chart_col1:
    st.write("Distribution — nombre de chevaux par PLACE (un cheval peut apparaître dans plusieurs places s'il a eu plusieurs résultats)")
    place_horse_counts = df_rows.groupby("PLACE")["ID_CHEVAL"].nunique().sort_index()
    # Optionally ignore PLACE == 0 if not meaningful
    if 0 in place_horse_counts.index:
        place_horse_counts = place_horse_counts.drop(0)
    st.bar_chart(place_horse_counts)

# Allocation distributions: compute total allocation per horse and bin
alloc_horse_v = df_rows.groupby("ID_CHEVAL", as_index=False)["ALLOCATION_VICTOIRE"].sum()
alloc_horse_p = df_rows.groupby("ID_CHEVAL", as_index=False)["ALLOCATION_PLACE"].sum()

with chart_col2:
    st.write("Distribution — Allocation victoire (somme par cheval, bins)")
    if len(alloc_horse_v) == 0:
        st.write("Aucune donnée")
    else:
        vals = alloc_horse_v["ALLOCATION_VICTOIRE"].astype(float)
        # Reduce extreme ranges by using the 95th percentile as upper bin edge
        p95 = float(vals.quantile(0.95))
        vmin = float(vals.min())
        vmax = float(vals.max())
        if p95 <= vmin or vmin == vmax:
            bins = np.array([vmin, vmax])
        else:
            # create 9 bins between min and p95, and one final bin from p95 to max
            middle = np.linspace(vmin, p95, 9)
            bins = np.unique(np.concatenate((middle, [vmax])))
        alloc_v_bins = pd.cut(vals, bins=bins, include_lowest=True)
        alloc_v_counts = alloc_v_bins.value_counts().sort_index()
    alloc_v_chart = pd.DataFrame({"Intervalle": alloc_v_counts.index.astype(str), "Nb_chevaux": alloc_v_counts.values})
    # Trier les bins par nombre de chevaux décroissant
    alloc_v_chart = alloc_v_chart.sort_values(by="Nb_chevaux", ascending=False)
    st.bar_chart(alloc_v_chart.set_index("Intervalle"))

# Also show allocation_place distribution below
st.markdown("---")
st.write("Distribution — Allocation place (somme par cheval, bins)")
if len(alloc_horse_p) == 0:
    st.write("Aucune donnée")
else:
    vals_p = alloc_horse_p["ALLOCATION_PLACE"].astype(float)
    p95_p = float(vals_p.quantile(0.95))
    vmin_p = float(vals_p.min())
    vmax_p = float(vals_p.max())
    if p95_p <= vmin_p or vmin_p == vmax_p:
        bins_p = np.array([vmin_p, vmax_p])
    else:
        middle_p = np.linspace(vmin_p, p95_p, 9)
        bins_p = np.unique(np.concatenate((middle_p, [vmax_p])))
    alloc_p_bins = pd.cut(vals_p, bins=bins_p, include_lowest=True)
    alloc_p_counts = alloc_p_bins.value_counts().sort_index()
    alloc_p_chart = pd.DataFrame({"Intervalle": alloc_p_counts.index.astype(str), "Nb_chevaux": alloc_p_counts.values})
    # Trier les bins par nombre de chevaux décroissant
    alloc_p_chart = alloc_p_chart.sort_values(by="Nb_chevaux", ascending=False)
    st.bar_chart(alloc_p_chart.set_index("Intervalle"))

# Distribution par âge si disponible
if has_age and len(filtered) > 0:
    st.markdown("---")
    st.subheader("🎂 Distribution par ÂGE")
    age_dist = filtered["AGE"].value_counts().sort_index()
    st.bar_chart(age_dist)

# --- Carte: répartition par L_HIPPODROME (villes marocaines) ---
hippo_col = "L_HIPPODROME"
if hippo_col in df.columns:
    st.markdown("---")
    st.subheader("📍 Carte — Répartition des chevaux par hippodrome (ville)")



    # Table de coordonnées à compléter/adapter
    city_coords = {
        "casablanca": (33.5731, -7.5898),
        "rabat": (34.020882, -6.841650),
        "marrakech": (31.6295, -7.9811),
        "meknes": (33.8938, -5.5477),
        "oujda": (34.6824, -1.9076),
        "sale": (34.0170, -6.8296),
        "settat": (33.0016, -7.6194),
        "el jadida": (33.2566, -8.5042),
        "eljadida": (33.2566, -8.5042),
        "anfa": (33.5731, -7.5898),
        "lalla malika": (33.2566, -8.5042),
        "souissi": (34.020882, -6.841650),
        "khénifra": (32.939444, -5.6675),
        "khemisset": (33.8245, -6.0705)
    }

    # On prend les chevaux correspondant aux filtres (si aucun, on prend toutes les lignes)
    chev_ids = filtered["ID_CHEVAL"].unique().tolist()
    if len(chev_ids) > 0:
        hip_df = df[df["ID_CHEVAL"].isin(chev_ids)].copy()
    else:
        hip_df = df.copy()

    # Compter chevaux distincts par hippodrome
    hip_counts = hip_df.groupby(hippo_col).agg(NB_CHEVAUX=("ID_CHEVAL", "nunique")).reset_index()

    # Pour chaque hippodrome, chercher coordonnées si possible
    def match_city(name: str):
        if pd.isna(name):
            return (None, None)
        s = str(name).lower().strip()
        # matching exact ou inclusif
        for key, (lat, lon) in city_coords.items():
            if key in s or s in key:
                return lat, lon
        # matching par mot
        for word in s.replace('-', ' ').replace('_', ' ').split():
            if word in city_coords:
                return city_coords[word]
        return (None, None)

    hip_counts[["lat", "lon"]] = hip_counts[hippo_col].apply(lambda x: pd.Series(match_city(x)))

    # Séparer ceux qui ont une coordonnée et ceux qui n'en ont pas
    with_coord = hip_counts.dropna(subset=["lat", "lon"]).copy()
    without_coord = hip_counts[hip_counts["lat"].isna()].copy()


    if not with_coord.empty:
        import pydeck as pdk
        st.write("**Carte claire des hippodromes (pydeck)**")
        midpoint = [with_coord["lat"].mean(), with_coord["lon"].mean()]
        layer = pdk.Layer(
            "ScatterplotLayer",
            data=with_coord,
            get_position='[lon, lat]',
            get_radius=10000,
            get_fill_color=[0, 100, 255, 180],
            pickable=True,
            auto_highlight=True,
        )
        view_state = pdk.ViewState(latitude=midpoint[0], longitude=midpoint[1], zoom=5)
        st.pydeck_chart(pdk.Deck(
            layers=[layer],
            initial_view_state=view_state,
            map_style=None  # fond blanc sans routes
        ))
        st.write("**Distribution du nombre de chevaux par hippodrome (avec coordonnées):**")
        hip_sorted = with_coord.sort_values(by="NB_CHEVAUX", ascending=False)
        st.bar_chart(hip_sorted.set_index(hippo_col)["NB_CHEVAUX"])
        st.write("Détail par hippodrome (avec coordonnées):")
        st.dataframe(hip_sorted, use_container_width=True)
    else:
        st.info("❌ Aucun hippodrome avec coordonnées trouvées dans city_coords. Complétez la table pour activer la carte.")

    if not without_coord.empty:
        st.warning(f"⚠️ Hippodromes sans coordonnées : {without_coord[hippo_col].tolist()}")
else:
    st.warning(f"⚠️ Colonne '{hippo_col}' non trouvée dans le fichier Excel. Colonnes disponibles: {list(df.columns)}")

# --- Téléchargement ---
st.markdown("---")
csv = filtered.to_csv(index=False).encode("utf-8")
st.download_button("Télécharger les chevaux filtrés (CSV)", data=csv, file_name="chevaux_filtres.csv", mime="text/csv")

st.info("Les données sont agrégées par `ID_CHEVAL` et `RACE` avant application des filtres — reproduit la logique des requêtes SQL fournies.")
