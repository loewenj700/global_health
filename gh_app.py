"""
app.py — Global Diabetes Dashboard
Runs with: streamlit run app.py
Requires: pip install streamlit pandas plotly

Data files (put in the same folder as app.py):
  diabetes-prev.csv    — World Bank SH.STA.DIAB.ZS (diabetes prevalence, 2024)
  health-spend.csv     — World Bank SH.XPD.CHEX.GD.ZS (health spending % GDP)
  uhc-index.csv        — WHO GHO UHC_INDEX_REPORTED (service coverage index, 2023)

Download from the GitHub repo linked in the article.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import requests

st.set_page_config(
    page_title="Global Diabetes Dashboard",
    page_icon="🩺",
    layout="wide",
)

# ── Data loading ─────────────────────────────────────────────────

@st.cache_data(show_spinner="Loading data…")
def load_data():
    # Load pre-downloaded CSV files
    diabetes = pd.read_csv("data/diabetes-prev.csv")
    health_spend = pd.read_csv("data/health-spend.csv")
    uhc = pd.read_csv("data/uhc-index.csv")

    # Diabetes: latest year per country
    diab = (
        diabetes[diabetes["year"] == 2024]
        .rename(columns={"value": "diabetes_pct"})
    )

    # Health spend: latest year per country
    spend = (
        health_spend
        .sort_values("year", ascending=False)
        .drop_duplicates("iso3")
        .rename(columns={"value": "health_spend_pct", "year": "spend_year",
                         "country": "country_spend"})
    )

    # UHC: latest year per country (all 2023)
    uhc_clean = uhc[["iso3", "uhc_index"]].copy()

    # Merge all three on iso3
    df = (
        diab[["iso3", "country", "year", "diabetes_pct"]]
        .merge(spend[["iso3", "health_spend_pct", "spend_year"]], on="iso3")
        .merge(uhc_clean[["iso3", "uhc_index"]], on="iso3")
    )

    # Add World Bank region
    try:
        meta = requests.get(
            "https://api.worldbank.org/v2/country?format=json&per_page=500",
            timeout=15
        ).json()[1]
        region_map = {
            c["id"]: c["region"]["value"]
            for c in meta if c.get("id") and c.get("region")
        }
    except Exception:
        region_map = {}

    def simplify(r):
        if "Middle East" in r or "Afghanistan" in r:
            return "Middle East & N. Africa"
        if "Sub-Saharan" in r:
            return "Sub-Saharan Africa"
        if "Latin America" in r:
            return "Latin America & Caribbean"
        if "East Asia" in r:
            return "East Asia & Pacific"
        if "South Asia" in r:
            return "South Asia"
        if "Europe" in r:
            return "Europe & Central Asia"
        if "North America" in r:
            return "North America"
        return "Other"

    if region_map:
        df["region"] = df["iso3"].map(region_map).fillna("Other").apply(simplify)
        df = df[df["iso3"].isin(region_map)].copy()
    else:
        df["region"] = "Other"

    return df.reset_index(drop=True)


df = load_data()

# Region color palette (Okabe-Ito)
region_colors = {
    "Middle East & N. Africa":   "#E69F00",
    "Sub-Saharan Africa":        "#56B4E9",
    "Latin America & Caribbean": "#009E73",
    "East Asia & Pacific":       "#F0E442",
    "South Asia":                "#0072B2",
    "Europe & Central Asia":     "#CC79A7",
    "North America":             "#D55E00",
    "Other":                     "#999999",
}

# ── Header ───────────────────────────────────────────────────────

st.title("Global Diabetes Dashboard")
st.caption(
    "World Bank SH.STA.DIAB.ZS (diabetes, 2024) · "
    "SH.XPD.CHEX.GD.ZS (health spending, latest year) · "
    "WHO GHO UHC_INDEX_REPORTED (service coverage index, 2023)"
)

col1, col2, col3, col4 = st.columns(4)
col1.metric("Countries in dataset", f"{len(df)}")
col2.metric("Global avg. diabetes", f"{df['diabetes_pct'].mean():.1f}%")
top_country = df.sort_values("diabetes_pct", ascending=False).iloc[0]
col3.metric(
    f"Highest diabetes ({top_country['country']})",
    f"{top_country['diabetes_pct']:.1f}%"
)
top_spend = df.sort_values("health_spend_pct", ascending=False).iloc[0]
col4.metric(
    f"Highest health spend ({top_spend['country']})",
    f"{top_spend['health_spend_pct']:.1f}% GDP"
)

st.divider()

tab1, tab2, tab3 = st.tabs([
    "Scatter: The Paradox",
    "Top Countries",
    "UHC Coverage Gap",
])

# ── Tab 1: Scatter ───────────────────────────────────────────────

with tab1:
    st.subheader("Diabetes prevalence vs healthcare spending")
    st.markdown(
        "**Bubble size** = UHC Service Coverage Index. "
        "Larger bubble = better health service access."
    )

    highlight = st.multiselect(
        "Highlight countries",
        options=sorted(df["country"].unique()),
        default=[c for c in ["Pakistan", "United States", "Thailand", "Germany", "Kuwait"]
                 if c in df["country"].values],
    )

    region_filter = st.multiselect(
        "Filter by region",
        options=sorted(df["region"].unique()),
        default=sorted(df["region"].unique()),
    )

    df1 = df[df["region"].isin(region_filter)].copy()

    fig1 = go.Figure()
    for region, color in region_colors.items():
        sub = df1[df1["region"] == region]
        if sub.empty:
            continue
        is_hl = sub["country"].isin(highlight)

        # Non-highlighted
        s0 = sub[~is_hl]
        if not s0.empty:
            fig1.add_trace(go.Scatter(
                x=s0["health_spend_pct"],
                y=s0["diabetes_pct"],
                mode="markers",
                name=region,
                showlegend=True,
                marker=dict(
                    size=(s0["uhc_index"] / 100 * 25 + 5).tolist(),
                    color=color,
                    opacity=0.5,
                    line=dict(width=0.5, color="white"),
                ),
                customdata=s0[["country", "uhc_index"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Diabetes: %{y:.1f}%<br>"
                    "Health spend: %{x:.1f}% GDP<br>"
                    "UHC index: %{customdata[1]:.0f}"
                    "<extra></extra>"
                ),
            ))

        # Highlighted
        s1 = sub[is_hl]
        if not s1.empty:
            fig1.add_trace(go.Scatter(
                x=s1["health_spend_pct"],
                y=s1["diabetes_pct"],
                mode="markers+text",
                name="",
                showlegend=False,
                text=s1["country"],
                textposition="top center",
                marker=dict(
                    size=(s1["uhc_index"] / 100 * 25 + 5).tolist(),
                    color="#E63946",
                    opacity=1.0,
                    line=dict(width=2, color="black"),
                ),
                customdata=s1[["country", "uhc_index"]].values,
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Diabetes: %{y:.1f}%<br>"
                    "Health spend: %{x:.1f}% GDP<br>"
                    "UHC index: %{customdata[1]:.0f}"
                    "<extra></extra>"
                ),
            ))

    fig1.update_layout(
        xaxis_title="Healthcare spending (% of GDP)",
        yaxis_title="Diabetes prevalence (% of adults, 2024)",
        legend_title="Region",
        plot_bgcolor="#f8f9fa",
        height=550,
    )
    st.plotly_chart(fig1, use_container_width=True)

    if highlight:
        st.subheader("Highlighted countries")
        hl_df = df[df["country"].isin(highlight)][
            ["country", "diabetes_pct", "health_spend_pct", "uhc_index", "region"]
        ].sort_values("diabetes_pct", ascending=False).rename(columns={
            "country": "Country",
            "diabetes_pct": "Diabetes %",
            "health_spend_pct": "Health spend % GDP",
            "uhc_index": "UHC index",
            "region": "Region",
        })
        st.dataframe(hl_df, hide_index=True, use_container_width=True)

    st.download_button(
        "Download full dataset as CSV",
        df.to_csv(index=False),
        file_name="diabetes_health_spend_uhc.csv",
        mime="text/csv",
    )

# ── Tab 2: Top countries bar chart ───────────────────────────────

with tab2:
    st.subheader("Countries by diabetes prevalence (2024)")

    n = st.slider("Number of countries to show", min_value=5, max_value=30, value=15)
    top_n = df.sort_values("diabetes_pct", ascending=False).head(n).copy()

    def spend_tier(x):
        if x < 4:
            return "Low (<4% GDP)"
        if x < 8:
            return "Medium (4–8% GDP)"
        return "High (>8% GDP)"

    top_n["spend_tier"] = top_n["health_spend_pct"].apply(spend_tier)
    top_n_sorted = top_n.sort_values("diabetes_pct", ascending=True)

    tier_colors = {
        "Low (<4% GDP)":     "#D62728",
        "Medium (4–8% GDP)": "#FF7F0E",
        "High (>8% GDP)":    "#1F77B4",
    }

    fig2 = go.Figure()
    for tier, color in tier_colors.items():
        sub = top_n_sorted[top_n_sorted["spend_tier"] == tier]
        if sub.empty:
            continue
        fig2.add_trace(go.Bar(
            y=sub["country"],
            x=sub["diabetes_pct"],
            orientation="h",
            name=tier,
            marker_color=color,
            text=[f"{v:.1f}%" for v in sub["diabetes_pct"]],
            textposition="outside",
            customdata=sub[["health_spend_pct", "uhc_index"]].values,
            hovertemplate=(
                "<b>%{y}</b><br>"
                "Diabetes: %{x:.1f}%<br>"
                "Health spend: %{customdata[0]:.1f}% GDP<br>"
                "UHC index: %{customdata[1]:.0f}"
                "<extra></extra>"
            ),
        ))

    fig2.update_layout(
        xaxis_title="Diabetes prevalence (% of adults, 2024)",
        yaxis_title="",
        legend_title="Health spending",
        plot_bgcolor="#f8f9fa",
        height=max(400, n * 32),
        xaxis=dict(range=[0, top_n["diabetes_pct"].max() * 1.18]),
    )
    st.plotly_chart(fig2, use_container_width=True)

# ── Tab 3: UHC coverage gap ──────────────────────────────────────

with tab3:
    st.subheader("UHC Service Coverage Index vs diabetes prevalence")
    st.markdown(
        "The UHC index measures whether people can access essential health services "
        "(0 = no coverage, 100 = full coverage). "
        "Countries in the shaded zone have high diabetes AND low healthcare coverage."
    )

    uhc_range = st.slider(
        "Filter by UHC index range",
        min_value=int(df["uhc_index"].min()),
        max_value=int(df["uhc_index"].max()),
        value=(int(df["uhc_index"].min()), int(df["uhc_index"].max())),
    )

    df3 = df[
        (df["uhc_index"] >= uhc_range[0]) &
        (df["uhc_index"] <= uhc_range[1])
    ].copy()

    fig3 = go.Figure()
    for region, color in region_colors.items():
        sub = df3[df3["region"] == region]
        if sub.empty:
            continue
        fig3.add_trace(go.Scatter(
            x=sub["uhc_index"],
            y=sub["diabetes_pct"],
            mode="markers",
            name=region,
            marker=dict(
                size=10,
                color=color,
                opacity=0.75,
                line=dict(width=0.5, color="white"),
            ),
            customdata=sub[["country", "health_spend_pct"]].values,
            hovertemplate=(
                "<b>%{customdata[0]}</b><br>"
                "Diabetes: %{y:.1f}%<br>"
                "UHC index: %{x:.0f}<br>"
                "Health spend: %{customdata[1]:.1f}% GDP"
                "<extra></extra>"
            ),
        ))

    max_diab = df["diabetes_pct"].max()
    fig3.add_shape(
        type="rect",
        x0=20, x1=65, y0=15, y1=max_diab + 2,
        fillcolor="rgba(214, 39, 40, 0.07)",
        line=dict(width=0),
    )
    fig3.add_annotation(
        x=42, y=max_diab + 1,
        text="High burden, low coverage",
        showarrow=False,
        font=dict(color="#D62728", size=12),
    )

    fig3.update_layout(
        xaxis_title="UHC Service Coverage Index (WHO, 2023)",
        yaxis_title="Diabetes prevalence (% of adults, 2024)",
        legend_title="Region",
        plot_bgcolor="#f8f9fa",
        height=550,
        xaxis=dict(range=[20, 100]),
    )
    st.plotly_chart(fig3, use_container_width=True)

    danger = df[
        (df["diabetes_pct"] > 15) & (df["uhc_index"] < 65)
    ][["country", "diabetes_pct", "health_spend_pct", "uhc_index", "region"]].sort_values(
        "diabetes_pct", ascending=False
    ).rename(columns={
        "country": "Country",
        "diabetes_pct": "Diabetes %",
        "health_spend_pct": "Health spend % GDP",
        "uhc_index": "UHC index",
        "region": "Region",
    })

    st.subheader(
        f"High burden, low coverage: {len(danger)} countries "
        f"(diabetes > 15%, UHC index < 65)"
    )
    st.dataframe(danger, hide_index=True, use_container_width=True)
