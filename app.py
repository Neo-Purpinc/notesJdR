"""
app.py — Interface web Streamlit pour visualiser les notes Real Madrid.

Lancer avec : streamlit run app.py
"""

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Configuration de la page
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Notes Real Madrid 2025-2026",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

OUTPUT_DIR = Path("output")
DATA_FILE = OUTPUT_DIR / "data.json"
STATS_FILE = OUTPUT_DIR / "stats.json"

COMPETITION_ICONS = {
    "Liga": "🇪🇸",
    "Ligue des Champions": "⭐",
    "Coupe du Roi": "🏆",
    "Supercoupe d'Espagne": "🥇",
    "Coupe Intercontinentale": "🌍",
    "Amical": "🎯",
    "Inconnue": "❓",
}

COLOR_SCALE = {
    "high": "#22c55e",   # vert  ≥ 7
    "mid":  "#f97316",   # orange 5-6
    "low":  "#ef4444",   # rouge ≤ 4
}


# ---------------------------------------------------------------------------
# Chargement des données
# ---------------------------------------------------------------------------

@st.cache_data(ttl=300)
def load_data() -> tuple[list[dict], list[dict]]:
    """Charge articles + stats depuis les fichiers JSON."""
    articles = []
    stats = []

    if DATA_FILE.exists():
        articles = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    if STATS_FILE.exists():
        stats = json.loads(STATS_FILE.read_text(encoding="utf-8"))

    return articles, stats


def flatten_to_df(articles: list[dict]) -> pd.DataFrame:
    """Transforme la liste d'articles en DataFrame à plat (1 ligne par joueur×match)."""
    rows = []
    for a in articles:
        for p in a.get("players", []):
            rows.append({
                "date": pd.to_datetime(a["date"]),
                "adversaire": a.get("opponent", "?"),
                "competition": a.get("competition", "Inconnue"),
                "joueur": p["name"],
                "note": p["note"],
                "url": a.get("url", ""),
                "titre": a.get("title", ""),
            })
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("date")
        # note peut être None (Non noté) → NaN pour pandas
        df["note"] = pd.to_numeric(df["note"], errors="coerce")
    return df


def stats_to_df(stats: list[dict]) -> pd.DataFrame:
    """Transforme les stats en DataFrame pour le tableau général."""
    # Collecte toutes les compétitions
    all_comps: set[str] = set()
    for s in stats:
        all_comps.update(s.get("par_competition", {}).keys())
    all_comps_sorted = sorted(all_comps)

    rows = []
    for s in stats:
        row = {
            "Joueur": s["player_name"],
            "Moy. globale": s["moyenne_globale"],
            "Matchs notés": s["nb_matchs"],
            "Non notés": s.get("nb_matchs_non_notes", 0),
            "Total": s.get("nb_matchs_total", s["nb_matchs"]),
            "Note min": s.get("note_min", "-"),
            "Note max": s.get("note_max", "-"),
            "Écart-type": s.get("ecart_type", 0.0),
        }
        for comp in all_comps_sorted:
            if comp in s.get("par_competition", {}):
                cd = s["par_competition"][comp]
                row[f"{COMPETITION_ICONS.get(comp, '')} {comp}"] = cd["moyenne"]
                row[f"  {comp} (notés)"] = cd["nb_matchs"]
                row[f"  {comp} (non notés)"] = cd.get("nb_non_notes", 0)
            else:
                row[f"{COMPETITION_ICONS.get(comp, '')} {comp}"] = None
                row[f"  {comp} (notés)"] = 0
                row[f"  {comp} (non notés)"] = 0
        rows.append(row)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Coloration conditionnelle
# ---------------------------------------------------------------------------

def color_note(val) -> str:
    if pd.isna(val) or val is None:
        return ""
    try:
        v = float(val)
    except (TypeError, ValueError):
        return ""
    if v >= 7:
        return f"background-color: {COLOR_SCALE['high']}33; color: {COLOR_SCALE['high']}"
    elif v >= 5:
        return f"background-color: {COLOR_SCALE['mid']}33; color: {COLOR_SCALE['mid']}"
    elif v > 0:
        return f"background-color: {COLOR_SCALE['low']}33; color: {COLOR_SCALE['low']}"
    return ""


# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

def render_sidebar(df: pd.DataFrame) -> tuple[list[str], list[str]]:
    st.sidebar.header("⚽ Real Madrid 2025-26")
    st.sidebar.markdown("---")

    all_comps = sorted(df["competition"].unique()) if not df.empty else []
    all_players = sorted(df["joueur"].unique()) if not df.empty else []

    selected_comps = st.sidebar.multiselect(
        "Compétition",
        options=all_comps,
        default=all_comps,
        format_func=lambda c: f"{COMPETITION_ICONS.get(c, '')} {c}",
    )

    selected_players = st.sidebar.multiselect(
        "Joueurs",
        options=all_players,
        default=[],
        placeholder="Tous les joueurs",
    )

    st.sidebar.markdown("---")

    if st.sidebar.button("🔄 Rafraîchir les données", use_container_width=True):
        with st.spinner("Scraping en cours..."):
            try:
                result = subprocess.run(
                    [sys.executable, "main.py", "--refresh"],
                    capture_output=True,
                    text=True,
                    timeout=300,
                )
                if result.returncode == 0:
                    st.cache_data.clear()
                    st.sidebar.success("Données mises à jour !")
                    st.rerun()
                else:
                    st.sidebar.error(f"Erreur scraping:\n{result.stderr[:500]}")
            except subprocess.TimeoutExpired:
                st.sidebar.error("Timeout (>5 min). Relancez manuellement.")
            except Exception as e:
                st.sidebar.error(f"Erreur: {e}")

    return selected_comps, selected_players


# ---------------------------------------------------------------------------
# Onglet 1 — Tableau général
# ---------------------------------------------------------------------------

def tab_tableau(stats: list[dict], selected_comps: list[str], selected_players: list[str]) -> None:
    st.header("📊 Tableau général")

    if not stats:
        st.info("Aucune donnée disponible. Cliquez sur 'Rafraîchir les données'.")
        return

    # Filtre par compétition dans les stats
    filtered_stats = stats
    if selected_players:
        filtered_stats = [s for s in filtered_stats if s["player_name"] in selected_players]

    df = stats_to_df(filtered_stats)

    if df.empty:
        st.warning("Aucun joueur trouvé avec les filtres sélectionnés.")
        return

    # Colonnes de notes à colorer (moyennes uniquement, pas les colonnes de comptage)
    note_cols = [c for c in df.columns if "Moy." in c or (
        any(comp in c for comp in ["Liga", "Champions", "Coupe", "Super", "Intercontinental", "Amical"])
        and "(notés)" not in c and "(non notés)" not in c
    )]

    min_matchs = st.slider("Minimum de matchs notés", 1, 20, 1, key="min_matchs_tab")
    df_filtered = df[df["Matchs notés"] >= min_matchs]

    st.caption(f"{len(df_filtered)} joueurs affichés")

    styled = df_filtered.style.applymap(color_note, subset=note_cols).format(
        {c: "{:.2f}" for c in note_cols if c in df_filtered.columns},
        na_rep="—",
    )

    st.dataframe(styled, use_container_width=True, height=600)

    # Export CSV
    csv = df_filtered.to_csv(index=False).encode("utf-8")
    st.download_button("📥 Exporter CSV", csv, "notes_real_madrid.csv", "text/csv")


# ---------------------------------------------------------------------------
# Onglet 2 — Évolution temporelle
# ---------------------------------------------------------------------------

def tab_evolution(df: pd.DataFrame, selected_players: list[str], selected_comps: list[str]) -> None:
    st.header("📈 Évolution temporelle")

    if df.empty:
        st.info("Aucune donnée disponible.")
        return

    # Filtre
    mask = df["competition"].isin(selected_comps)
    if selected_players:
        mask &= df["joueur"].isin(selected_players)
    df_f = df[mask].copy()

    if df_f.empty:
        st.warning("Aucune donnée pour les filtres sélectionnés.")
        return

    players_available = sorted(df_f["joueur"].unique())
    if not selected_players:
        default_players = players_available[:5]
    else:
        default_players = [p for p in selected_players if p in players_available]

    players_choice = st.multiselect(
        "Joueurs à afficher",
        options=players_available,
        default=default_players,
        key="evo_players",
    )

    show_rolling = st.checkbox("Afficher la moyenne glissante (5 matchs)", value=True)

    if not players_choice:
        st.info("Sélectionnez au moins un joueur.")
        return

    df_plot = df_f[df_f["joueur"].isin(players_choice)].copy()

    fig = go.Figure()

    for player in players_choice:
        pdata = df_plot[df_plot["joueur"] == player].sort_values("date")
        if pdata.empty:
            continue

        # Ligne principale
        fig.add_trace(go.Scatter(
            x=pdata["date"],
            y=pdata["note"],
            mode="lines+markers",
            name=player,
            hovertemplate=(
                f"<b>{player}</b><br>"
                "Date: %{x|%d/%m/%Y}<br>"
                "Note: %{y}/10<br>"
                "Adversaire: %{customdata[0]}<br>"
                "Compétition: %{customdata[1]}"
                "<extra></extra>"
            ),
            customdata=pdata[["adversaire", "competition"]].values,
        ))

        # Moyenne glissante
        if show_rolling and len(pdata) >= 3:
            rolling = pdata["note"].rolling(window=5, min_periods=2).mean()
            fig.add_trace(go.Scatter(
                x=pdata["date"],
                y=rolling,
                mode="lines",
                name=f"{player} (moy. 5)",
                line=dict(dash="dot", width=1.5),
                showlegend=True,
                opacity=0.7,
                hoverinfo="skip",
            ))

    fig.update_layout(
        title="Évolution des notes par match",
        xaxis_title="Date",
        yaxis_title="Note (/10)",
        yaxis=dict(range=[0, 10.5], dtick=1),
        hovermode="x unified",
        height=500,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )

    st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------------------------
# Onglet 3 — Comparaison joueurs
# ---------------------------------------------------------------------------

def tab_comparaison(stats: list[dict], selected_players: list[str], selected_comps: list[str]) -> None:
    st.header("🆚 Comparaison joueurs")

    if not stats:
        st.info("Aucune donnée disponible.")
        return

    all_players = sorted(s["player_name"] for s in stats)
    players_choice = st.multiselect(
        "Joueurs à comparer",
        options=all_players,
        default=selected_players[:4] if selected_players else all_players[:4],
        key="comp_players",
    )

    if not players_choice:
        st.info("Sélectionnez au moins un joueur.")
        return

    # Collecte des compétitions filtrées
    comps_in_filter = set(selected_comps)
    all_comps_data: set[str] = set()
    for s in stats:
        if s["player_name"] in players_choice:
            for comp in s.get("par_competition", {}):
                if comp in comps_in_filter:
                    all_comps_data.add(comp)
    comps_sorted = sorted(all_comps_data)

    if not comps_sorted:
        st.warning("Aucune compétition trouvée pour ces joueurs.")
        return

    col1, col2 = st.columns(2)

    # --- Bar chart groupé ---
    with col1:
        st.subheader("Moyenne par compétition")
        bar_data = []
        for s in stats:
            if s["player_name"] not in players_choice:
                continue
            for comp in comps_sorted:
                cd = s.get("par_competition", {}).get(comp)
                if cd:
                    bar_data.append({
                        "Joueur": s["player_name"],
                        "Compétition": comp,
                        "Moyenne": cd["moyenne"],
                        "Matchs": cd["nb_matchs"],
                    })

        if bar_data:
            df_bar = pd.DataFrame(bar_data)
            fig_bar = px.bar(
                df_bar,
                x="Compétition",
                y="Moyenne",
                color="Joueur",
                barmode="group",
                range_y=[0, 10],
                hover_data=["Matchs"],
                title="Moyennes par compétition",
                height=400,
            )
            fig_bar.update_layout(legend=dict(orientation="h", yanchor="bottom", y=1.02))
            st.plotly_chart(fig_bar, use_container_width=True)
        else:
            st.info("Pas de données pour le graphique en barres.")

    # --- Radar chart ---
    with col2:
        st.subheader("Profil (radar)")

        # Axes du radar : compétitions + régularité (inversé de l'écart-type)
        radar_cats = comps_sorted + ["Régularité"]
        fig_radar = go.Figure()

        for s in stats:
            if s["player_name"] not in players_choice:
                continue

            values = []
            for comp in comps_sorted:
                cd = s.get("par_competition", {}).get(comp)
                values.append(cd["moyenne"] if cd else 0)

            # Régularité : 10 - écart-type (capped à 0)
            regularite = max(0, 10 - s.get("ecart_type", 0) * 2)
            values.append(regularite)

            # Fermer le polygone
            values_closed = values + [values[0]]
            cats_closed = radar_cats + [radar_cats[0]]

            fig_radar.add_trace(go.Scatterpolar(
                r=values_closed,
                theta=cats_closed,
                fill="toself",
                name=s["player_name"],
                opacity=0.6,
            ))

        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 10])),
            showlegend=True,
            title="Profil multi-compétition",
            height=400,
        )
        st.plotly_chart(fig_radar, use_container_width=True)


# ---------------------------------------------------------------------------
# Onglet 4 — Détail par match
# ---------------------------------------------------------------------------

def tab_detail(df: pd.DataFrame, selected_players: list[str], selected_comps: list[str]) -> None:
    st.header("📋 Détail par match")

    if df.empty:
        st.info("Aucune donnée disponible.")
        return

    col1, col2, col3 = st.columns(3)

    with col1:
        all_players = sorted(df["joueur"].unique())
        player_filter = st.selectbox(
            "Joueur",
            options=["Tous"] + all_players,
            index=0,
            key="detail_player",
        )

    with col2:
        comp_filter = st.selectbox(
            "Compétition",
            options=["Toutes"] + sorted(df["competition"].unique()),
            index=0,
            key="detail_comp",
        )

    with col3:
        note_min = st.slider("Note minimale", 0, 10, 0, key="detail_note_min")

    # Filtrage
    mask = df["competition"].isin(selected_comps)
    if player_filter != "Tous":
        mask &= df["joueur"] == player_filter
    if comp_filter != "Toutes":
        mask &= df["competition"] == comp_filter
    mask &= (df["note"] >= note_min) | df["note"].isna()

    df_f = df[mask].copy()

    if df_f.empty:
        st.warning("Aucun résultat pour ces filtres.")
        return

    # Icône compétition
    df_f["🏆"] = df_f["competition"].map(lambda c: COMPETITION_ICONS.get(c, ""))
    df_f["Date"] = df_f["date"].dt.strftime("%d/%m/%Y")

    display_cols = ["Date", "joueur", "adversaire", "🏆", "competition", "note"]
    rename_map = {
        "joueur": "Joueur",
        "adversaire": "Adversaire",
        "competition": "Compétition",
        "note": "Note",
    }

    df_display = df_f[display_cols].rename(columns=rename_map).sort_values(
        "Date", ascending=False
    ).reset_index(drop=True)

    st.caption(f"{len(df_display)} lignes")

    styled = df_display.style.applymap(color_note, subset=["Note"]).format(
        {"Note": lambda x: "—" if pd.isna(x) else f"{x:.0f}"}
    )
    st.dataframe(styled, use_container_width=True, height=600)

    # Stats rapides
    if player_filter != "Tous" and not df_f.empty:
        st.markdown("---")
        st.subheader(f"Résumé — {player_filter}")
        rated_f = df_f[df_f["note"].notna()]
        non_noted_count = int(df_f["note"].isna().sum())
        mc1, mc2, mc3, mc4, mc5 = st.columns(5)
        mc1.metric("Matchs notés", len(rated_f))
        mc2.metric("Non notés", non_noted_count)
        mc3.metric("Total apparitions", len(df_f))
        mc4.metric("Moyenne", f"{rated_f['note'].mean():.2f}/10" if not rated_f.empty else "—")
        mc5.metric(
            "Max / Min",
            f"{int(rated_f['note'].max())} / {int(rated_f['note'].min())}" if not rated_f.empty else "—",
        )


# ---------------------------------------------------------------------------
# Point d'entrée principal
# ---------------------------------------------------------------------------

def main() -> None:
    st.title("⚽ Notes Real Madrid — Saison 2025-2026")

    # Chargement des données
    articles, stats = load_data()

    if not articles:
        st.warning(
            "Aucune donnée trouvée. Cliquez sur **🔄 Rafraîchir les données** "
            "dans la barre latérale pour lancer le scraping."
        )
        # Afficher la sidebar quand même
        df_empty = pd.DataFrame(columns=["competition", "joueur", "date", "note", "adversaire", "url", "titre"])
        selected_comps, selected_players = render_sidebar(df_empty)
        return

    df = flatten_to_df(articles)

    # Sidebar
    selected_comps, selected_players = render_sidebar(df)

    # Métriques globales
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Articles scrapés", len(articles))
    col2.metric("Joueurs uniques", df["joueur"].nunique() if not df.empty else 0)
    col3.metric(
        "Note moyenne globale",
        f"{df['note'].mean():.2f}/10" if not df.empty else "—",
    )
    col4.metric("Compétitions", df["competition"].nunique() if not df.empty else 0)

    st.markdown("---")

    # Onglets
    tab1, tab2, tab3, tab4 = st.tabs([
        "📊 Tableau général",
        "📈 Évolution temporelle",
        "🆚 Comparaison joueurs",
        "📋 Détail par match",
    ])

    # Filtre global compétitions sur df
    df_filtered = df[df["competition"].isin(selected_comps)] if selected_comps else df

    with tab1:
        tab_tableau(stats, selected_comps, selected_players)

    with tab2:
        tab_evolution(df_filtered, selected_players, selected_comps)

    with tab3:
        tab_comparaison(stats, selected_players, selected_comps)

    with tab4:
        tab_detail(df_filtered, selected_players, selected_comps)

    # Footer
    st.markdown("---")
    st.caption("Données scrapées depuis [lejournaldureal.fr](https://lejournaldureal.fr)")


if __name__ == "__main__":
    main()
