import os
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime
import io


st.set_page_config(page_title="Dashboard Gains PROPRIETAIRE", layout="wide")

st.title("Gains par PROPRIETAIRE — Extraction 2025")

# Chemin par défaut vers le fichier Excel (modifiez si besoin)
DEFAULT_EXCEL = r"Extraction_gains_2025.xlsx"

# Chemin fixé (non éditable) — la sidebar contiendra uniquement les filtres
excel_path = DEFAULT_EXCEL

if not os.path.exists(excel_path):
    st.error(f"Fichier non trouvé: {excel_path}")
    st.stop()

@st.cache_data
def load_data(path):
    df = pd.read_excel(path)
    return df

df = load_data(excel_path)

# Colonnes d'intérêt (selon la demande)
cols_needed = [
    "PROPRIETAIRE",
    "PRIME_PROPRIETAIRE",
    "ALLOCATION_VICTOIRE",
    "ALLOCATION_PLACE",
]

missing = [c for c in cols_needed if c not in df.columns]
if missing:
    st.error(f"Colonnes manquantes dans le fichier: {missing}")
    st.stop()

# Préparation des données
# On prend aussi DATE_COURSE, CODE_NATURE_COURSE, CODE_RACE_CHEVAL si disponibles (pour filtres / séries)
use_date = "DATE_COURSE" in df.columns
use_code_nature = "CODE_NATURE_COURSE" in df.columns
use_race = "CODE_RACE_CHEVAL" in df.columns

take_cols = cols_needed + ([] if not use_date else ["DATE_COURSE"]) + ([] if not use_code_nature else ["CODE_NATURE_COURSE"]) + ([] if not use_race else ["CODE_RACE_CHEVAL"])
df_clean = df[take_cols].copy()

for c in cols_needed[1:]:
    # convertir en numérique et remplacer NaN par 0
    df_clean[c] = pd.to_numeric(df_clean[c], errors="coerce").fillna(0)

if use_date:
    df_clean["DATE_COURSE"] = pd.to_datetime(df_clean["DATE_COURSE"], errors="coerce")

df_clean["TOTAL"] = df_clean[
    ["PRIME_PROPRIETAIRE", "ALLOCATION_VICTOIRE", "ALLOCATION_PLACE"]
].sum(axis=1)

# Sidebar: filtres optionnels par CODE_NATURE_COURSE et CODE_RACE_CHEVAL
st.sidebar.markdown("---")
st.sidebar.write("Filtres (optionnels)")
selected_nature = None
selected_race = None
if use_code_nature:
    code_nature_options = sorted(df_clean["CODE_NATURE_COURSE"].dropna().unique().tolist())
    selected_nature = st.sidebar.multiselect("CODE_NATURE_COURSE", options=code_nature_options, default=code_nature_options)
if use_race:
    race_options = sorted(df_clean["CODE_RACE_CHEVAL"].dropna().unique().tolist())
    selected_race = st.sidebar.multiselect("CODE_RACE_CHEVAL", options=race_options, default=race_options)

# Appliquer les filtres avant agrégation
filtered_df = df_clean.copy()
if use_code_nature and selected_nature is not None and len(selected_nature) > 0:
    filtered_df = filtered_df[filtered_df["CODE_NATURE_COURSE"].isin(selected_nature)]
if use_race and selected_race is not None and len(selected_race) > 0:
    filtered_df = filtered_df[filtered_df["CODE_RACE_CHEVAL"].isin(selected_race)]

# Agrégation par propriétaire (après filtres)
grouped = filtered_df.groupby("PROPRIETAIRE").sum(numeric_only=True).reset_index()

st.markdown("### Paramètres")
top_n = st.slider("Afficher top N propriétaires", min_value=5, max_value=100, value=20)
metric = st.selectbox(
    "Choisir la métrique", ["PRIME_PROPRIETAIRE", "ALLOCATION_VICTOIRE", "ALLOCATION_PLACE", "TOTAL"]
)

search = st.text_input("Filtrer par nom de propriétaire (partie de nom)")

extra_charts = st.multiselect(
    "Charts supplémentaires",
    options=[
        "Stacked Components",
        "Pie distribution",
        "Time series (monthly)",
        "Treemap",
        "Histogram des totaux",
    ],
    default=["Stacked Components", "Pie distribution"],
)

g = grouped.copy()
if search:
    g = g[g["PROPRIETAIRE"].str.contains(search, case=False, na=False)]

g_sorted = g.sort_values(by=metric, ascending=False).head(top_n)

st.markdown(f"### Top {top_n} propriétaires par {metric}")

fig = px.bar(
    g_sorted,
    x=metric,
    y="PROPRIETAIRE",
    orientation="h",
    title=f"Top {top_n} — {metric}",
    labels={"PROPRIETAIRE": "Propriétaire", metric: "Montant"},
)
fig.update_layout(yaxis={"categoryorder": "total ascending"}, height=600)
st.plotly_chart(fig, use_container_width=True)

st.markdown("### Charts supplémentaires")

# 1) Stacked components: montre la composition (PRIME_PROPRIETAIRE, ALLOCATION_VICTOIRE, ALLOCATION_PLACE)
if "Stacked Components" in extra_charts:
    comp = g_sorted[["PROPRIETAIRE", "PRIME_PROPRIETAIRE", "ALLOCATION_VICTOIRE", "ALLOCATION_PLACE"]].set_index("PROPRIETAIRE")
    fig_stack = go.Figure()
    fig_stack.add_trace(go.Bar(name="Prime Propriétaire", y=comp.index, x=comp["PRIME_PROPRIETAIRE"], orientation="h"))
    fig_stack.add_trace(go.Bar(name="Allocation Victoire", y=comp.index, x=comp["ALLOCATION_VICTOIRE"], orientation="h"))
    fig_stack.add_trace(go.Bar(name="Allocation Place", y=comp.index, x=comp["ALLOCATION_PLACE"], orientation="h"))
    fig_stack.update_layout(barmode="stack", height=600, title="Composition des gains par propriétaire (stacked)")
    st.plotly_chart(fig_stack, use_container_width=True)

# 2) Pie chart distribution (pour le metric sélectionné)
if "Pie distribution" in extra_charts:
    pie = g_sorted[["PROPRIETAIRE", metric]]
    fig_pie = px.pie(pie, names="PROPRIETAIRE", values=metric, title=f"Répartition de {metric} (top {top_n})")
    st.plotly_chart(fig_pie, use_container_width=True)

# 3) Time series monthly (si DATE_COURSE présent)
if "Time series (monthly)" in extra_charts:
    if not use_date:
        st.warning("La colonne DATE_COURSE n'est pas présente — impossible d'afficher la série temporelle.")
    else:
        # Choisir un ou plusieurs propriétaires à suivre
        owners_for_ts = st.multiselect("Sélectionner propriétaires pour la série temporelle (ou vide = top N)", options=g_sorted["PROPRIETAIRE"].tolist(), default=[]) or g_sorted["PROPRIETAIRE"].tolist()
        ts_df = df_clean[df_clean["PROPRIETAIRE"].isin(owners_for_ts)].copy()
        ts_df = ts_df.dropna(subset=["DATE_COURSE"])  
        if ts_df.empty:
            st.info("Aucune donnée de date pour les propriétaires sélectionnés.")
        else:
            ts_df["MONTH"] = ts_df["DATE_COURSE"].dt.to_period("M").dt.to_timestamp()
            ts_agg = ts_df.groupby(["MONTH", "PROPRIETAIRE"]).sum(numeric_only=True).reset_index()
            fig_ts = px.line(ts_agg, x="MONTH", y=metric, color="PROPRIETAIRE", title=f"Évolution mensuelle de {metric}")
            fig_ts.update_layout(height=500)
            st.plotly_chart(fig_ts, use_container_width=True)

# 4) Treemap
if "Treemap" in extra_charts:
    treemap_df = g_sorted[["PROPRIETAIRE", metric]]
    fig_tree = px.treemap(treemap_df, path=["PROPRIETAIRE"], values=metric, title=f"Treemap — {metric} (top {top_n})")
    st.plotly_chart(fig_tree, use_container_width=True)

# 5) Histogram des totaux
if "Histogram des totaux" in extra_charts:
    hist_df = g.sort_values(by="TOTAL", ascending=False)
    fig_hist = px.histogram(hist_df, x="TOTAL", nbins=50, title="Distribution des totaux par propriétaire")
    st.plotly_chart(fig_hist, use_container_width=True)

st.markdown("### Tableau détaillé")
st.dataframe(g_sorted.reset_index(drop=True))

# Préparer un fichier Excel en mémoire et proposer le téléchargement (XLSX)
to_xlsx = io.BytesIO()
with pd.ExcelWriter(to_xlsx, engine="openpyxl") as writer:
    g_sorted.to_excel(writer, index=False, sheet_name="Gains")
to_xlsx.seek(0)
st.download_button(
    "Télécharger les données affichées (XLSX)",
    data=to_xlsx.getvalue(),
    file_name="gains_proprietaire.xlsx",
    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
)

# Notes supprimées de la sidebar — la barre gauche contient uniquement les filtres

