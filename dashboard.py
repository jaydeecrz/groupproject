import streamlit as st
import pandas as pd
import plotly.express as px
from scipy.stats import pearsonr

st.set_page_config(page_title="China Climate Case Study", layout="wide")

# =========================
# Title & Intro
# =========================
st.title("China Case Study — CO₂, Temperature, Energy, GDP, and Natural Disasters")
st.markdown(
    "This dashboard summarizes our case study of **China** using the same indicators as the assignment: "
    "**CO₂ emissions**, **temperature**, **energy use per person**, **GDP per capita growth**, and **natural disasters**. "
    "All visuals are interactive and use files stored in this repository for reproducibility."
)
st.caption(
    "Sources: Gapminder/World Bank (CO₂, Energy, GDP); temperature from cleaned annual national series; "
    "disasters from group Excel (yearly counts or raw EM-DAT grouped)."
)

# =========================
# Filenames (must match your repo)
# =========================
CO2_XLSX    = "yearly_co2_emissions_1000_tonnes (1).xlsx"   # wide by year, first col = country
ENERGY_XLSX = "energy_use_per_person.xlsx"                  # wide by year, first col = country
GDP_XLSX    = "gdp_per_capita_yearly_growth.xlsx"           # wide by year, first col = country
TEMP_CSV    = "temperature_china_cleaned.csv"               # tidy: Year + Temperature column
DISASTER_XL = "natural_disasters.xlsx"                      # either tidy [Year, Disasters] or raw EM-DAT-like

COUNTRY = "China"  # fixed per your project

# =========================
# Helpers
# =========================
def _melt_years(df: pd.DataFrame, id_col: str, value_name: str) -> pd.DataFrame:
    """
    Robust wide→long reshape:
    - normalizes headers to strings
    - detects year columns (1700–2100), tolerant to '1960.0'
    - returns [id_col, Year, value_name]
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # ensure ID column exists; fallbacks if needed
    if id_col not in df.columns:
        candidates = [c for c in df.columns if c.lower() in ("country", "country name", "nation")]
        id_col = candidates[0] if candidates else df.columns[0]

    def _is_year(c):
        try:
            y = int(float(str(c)))
            return 1700 <= y <= 2100
        except:
            return False

    year_cols = [c for c in df.columns if _is_year(c)]
    if not year_cols:
        st.error("Could not detect year columns in the file below. Inspect headers:")
        st.write(df.head())
        st.stop()

    out = pd.melt(df, id_vars=[id_col], value_vars=year_cols,
                  var_name="Year", value_name=value_name)
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out = out.dropna(subset=["Year"]).astype({"Year": int}).sort_values("Year")
    return out

def _country_filter(df: pd.DataFrame, country_col: str, country_name: str) -> pd.DataFrame:
    return df[df[country_col].astype(str).str.strip().str.lower().eq(country_name.lower())].copy()

@st.cache_data
def load_co2(path: str):
    """
    Load wide CO₂ (in 1000 tonnes) Excel → tidy:
      co2_cn:  [Year, CO₂ (Mt)]
      co2_world: [Year, CO₂_World (Mt)]
    """
    df = pd.read_excel(path)
    df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="CO2_kt")
    long["CO₂ (Mt)"] = long["CO2_kt"] / 1000.0  # 1000 tonnes → Mt
    co2_cn = _country_filter(long, "Country", COUNTRY)[["Year", "CO₂ (Mt)"]]
    co2_world = long.groupby("Year", as_index=False)["CO₂ (Mt)"].sum().rename(columns={"CO₂ (Mt)":"CO₂_World (Mt)"})
    return co2_cn.reset_index(drop=True), co2_world

@st.cache_data
def load_energy(path: str):
    """Energy wide Excel → tidy China series: [Year, Energy (kg oil-eq./capita)]"""
    df = pd.read_excel(path)
    if "country" in df.columns:
        df = df.rename(columns={"country": "Country"})
    else:
        df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="Energy (kg oil-eq./capita)")
    return _country_filter(long, "Country", COUNTRY)[["Year", "Energy (kg oil-eq./capita)"]]

@st.cache_data
def load_gdp(path: str):
    """GDP per capita growth wide Excel → tidy China series: [Year, GDP Growth (%)]"""
    df = pd.read_excel(path)
    if "Country Name" in df.columns:
        df = df.rename(columns={"Country Name": "Country"})
    else:
        df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="GDP Growth (%)")
    return _country_filter(long, "Country", COUNTRY)[["Year", "GDP Growth (%)"]]

@st.cache_data
def load_temp(path: str):
    """Temperature CSV → normalize to [Year, Temperature (°C)]"""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    if "Temp (°C)" in df.columns and "Temperature (°C)" not in df.columns:
        df = df.rename(columns={"Temp (°C)":"Temperature (°C)"})
    if "Value" in df.columns and "Temperature (°C)" not in df.columns:
        df = df.rename(columns={"Value":"Temperature (°C)"})
    if "Year" not in df.columns or "Temperature (°C)" not in df.columns:
        st.error("Temperature CSV must have 'Year' and 'Temperature (°C)' (or 'Value').")
        st.write("Detected columns:", df.columns.tolist())
        st.stop()
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    df = df.dropna(subset=["Year"]).astype({"Year": int}).sort_values("Year")
    return df[["Year", "Temperature (°C)"]]

@st.cache_data
def load_disasters(path: str):
    """
    Natural disasters loader (robust):
    - If tidy: expects [Year, Disasters]
    - If raw EM-DAT-like: expects ['Start Year','Country', 'Disaster Type', ...] and groups to yearly counts
    Returns China series: [Year, Disasters]
    """
    df = pd.read_excel(path)
    df.columns = [str(c).strip() for c in df.columns]

    # Tidy case
    if "Year" in df.columns and ("Disasters" in df.columns or "Disaster Count" in df.columns):
        if "Disaster Count" in df.columns and "Disasters" not in df.columns:
            df = df.rename(columns={"Disaster Count": "Disasters"})
        out = df[["Year", "Disasters"]].copy()
        out["Year"] = pd.to_numeric(out["Year"], errors="coerce").astype("Int64")
        return out.dropna(subset=["Year"]).astype({"Year": int}).sort_values("Year")

    # Raw EM-DAT-like case
    # Expect 'Start Year' and 'Country'
    year_col = None
    for c in df.columns:
        if c.lower().replace("_", " ") in ("start year", "year"):
            year_col = c
            break

    if year_col is None:
        st.error("Could not find a 'Year' or 'Start Year' column in natural_disasters.xlsx.")
        st.write("Detected columns:", df.columns.tolist())
        st.stop()

    # Filter China, count rows per year
    df = df.rename(columns={year_col: "Year"})
    df["Year"] = pd.to_numeric(df["Year"], errors="coerce")
    if "Country" in df.columns:
        df = _country_filter(df.dropna(subset=["Year"]), "Country", COUNTRY)
    else:
        df = df.dropna(subset=["Year"])

    out = df.groupby("Year", as_index=False).size().rename(columns={"size": "Disasters"})
    return out.astype({"Year": int}).sort_values("Year")

# =========================
# Load data
# =========================
co2_cn, co2_world = load_co2(CO2_XLSX)
energy_cn         = load_energy(ENERGY_XLSX)
gdp_cn            = load_gdp(GDP_XLSX)
temp_cn           = load_temp(TEMP_CSV)
disasters_cn      = load_disasters(DISASTER_XL)

# =========================
# Year range slider based on intersection across series
# =========================
year_min = max(s["Year"].min() for s in [co2_cn, co2_world, energy_cn, gdp_cn, temp_cn, disasters_cn])
year_max = min(s["Year"].max() for s in [co2_cn, co2_world, energy_cn, gdp_cn, temp_cn, disasters_cn])

st.sidebar.header("Controls")
default_start = max(int(year_min), 1980)  # modern default if possible
yr0, yr1 = st.sidebar.slider("Year range", int(year_min), int(year_max), (default_start, int(year_max)), step=1)

def window(df):
    return df[(df["Year"] >= yr0) & (df["Year"] <= yr1)].copy()

co2_cn_w    = window(co2_cn)
co2_world_w = window(co2_world)
energy_cn_w = window(energy_cn)
gdp_cn_w    = window(gdp_cn)
temp_cn_w   = window(temp_cn)
dis_cn_w    = window(disasters_cn)

# Small helper to format y-axis & margins
def fmt(fig, yfmt=None):
    if yfmt:
        fig.update_layout(yaxis=dict(tickformat=yfmt))
    fig.update_layout(margin=dict(l=8, r=8, t=60, b=8))
    return fig

# =========================
# Row 1: CO₂ & Temperature
# =========================
c1, c2 = st.columns(2)
with c1:
    st.subheader("China CO₂ Emissions (Mt)")
    fig = px.line(co2_cn_w, x="Year", y="CO₂ (Mt)", markers=True,
                  labels={"CO₂ (Mt)":"CO₂ (million tonnes)"},
                  title="Annual CO₂ Emissions — China")
    st.plotly_chart(fmt(fig, yfmt="~s"), use_container_width=True)
    st.caption("CO₂ converted from '1000 tonnes' to **million tonnes (Mt)**. Rapid growth is visible in recent decades.")

with c2:
    st.subheader("China Temperature (Annual Mean, °C)")
    fig = px.line(temp_cn_w, x="Year", y="Temperature (°C)", markers=True,
                  title="Annual Mean Temperature — China")
    st.plotly_chart(fmt(fig, yfmt=".2f"), use_container_width=True)
    st.caption("Annual national mean created from monthly city data → annual city means → national average.")

# =========================
# Row 2: Energy & GDP
# =========================
c3, c4 = st.columns(2)
with c3:
    st.subheader("Energy Use per Person (kg oil-eq./capita)")
    fig = px.line(energy_cn_w, x="Year", y="Energy (kg oil-eq./capita)", markers=True,
                  title="Energy Use per Person — China")
    st.plotly_chart(fmt(fig), use_container_width=True)
    st.caption("Higher energy use per person generally aligns with industrialization and rising emissions.")

with c4:
    st.subheader("GDP per Capita Growth (%)")
    fig = px.line(gdp_cn_w, x="Year", y="GDP Growth (%)", markers=True,
                  title="GDP per Capita Growth — China")
    st.plotly_chart(fmt(fig, yfmt=".1f"), use_container_width=True)
    st.caption("GDP per capita growth (%) provides economic context for changes in energy use and emissions.")

# =========================
# Row 3: Natural Disasters (China)
# =========================
st.subheader("Natural Disasters — China (Yearly Counts)")
if not dis_cn_w.empty:
    fig = px.line(dis_cn_w, x="Year", y="Disasters", markers=True,
                  title="Natural Disasters — China")
    st.plotly_chart(fmt(fig), use_container_width=True)
    st.caption(
        "Yearly count of recorded natural disasters. This is **descriptive**; it does not prove causation, "
        "but it helps contextualize climate-related impacts over time."
    )
else:
    st.info("No disaster records in the selected year window. Try widening the slider.")

# =========================
# Row 4: CO₂ vs Temperature (scatter + trendline) + correlation
# =========================
st.subheader("Relationship: CO₂ vs Temperature (China)")
df_ct = pd.merge(
    co2_cn_w.rename(columns={"CO₂ (Mt)":"CO2_Mt"}),
    temp_cn_w, on="Year", how="inner"
)
if not df_ct.empty and df_ct["CO2_Mt"].notna().sum() > 1:
    fig = px.scatter(
        df_ct, x="CO2_Mt", y="Temperature (°C)",
        trendline="ols", hover_data=["Year"],
        labels={"CO2_Mt":"CO₂ (Mt)", "Temperature (°C)":"Temperature (°C)"},
        title="CO₂ vs Temperature — China (Overlapping Years)"
    )
    st.plotly_chart(fmt(fig), use_container_width=True)
    try:
        r, p = pearsonr(df_ct["CO2_Mt"], df_ct["Temperature (°C)"])
        st.caption(f"Pearson **r = {r:.3f}**, **p = {p:.3g}** over **{len(df_ct)}** overlapping years (descriptive association).")
    except Exception:
        st.caption("Correlation unavailable (scipy/statsmodels issue).")
else:
    st.info("No overlapping years between CO₂ and Temperature in this selection. Widen the year range.")

# =========================
# Row 5: Extra Credit — China’s CO₂ as % of Global Total
# =========================
st.subheader("Extra Credit: China’s CO₂ as % of Global Total")
df_ratio = pd.merge(
    co2_cn_w.rename(columns={"CO₂ (Mt)":"CO2_Mt"}),
    co2_world_w, on="Year", how="inner"
)
world_col = "CO₂_World (Mt)"
if not df_ratio.empty and world_col in df_ratio.columns:
    df_ratio["China_%_World"] = (df_ratio["CO2_Mt"] / df_ratio[world_col]) * 100.0
    fig = px.line(df_ratio, x="Year", y="China_%_World", markers=True,
                  labels={"China_%_World":"China’s % of World CO₂"},
                  title="China’s Share of Global CO₂")
    st.plotly_chart(fmt(fig), use_container_width=True)
    st.caption("This ratio controls for global totals and shows how China’s **share** of world emissions changes over time.")
else:
    st.info("World CO₂ total not available for overlap. Check CO₂ files or widen the year range.")

# =========================
# Footer notes
# =========================
st.markdown("---")
st.markdown(
    "Notes: CO₂ (Gapminder/World Bank style) is stored as '1000 tonnes' and converted to **Mt**. "
    "Energy and GDP are wide-format Excel reshaped to tidy. "
    "Temperature is a cleaned annual national mean based on city data. "
    "Disaster counts are either pre-aggregated by year or grouped from raw EM-DAT-like input. "
    "All plots honor the sidebar year range to keep comparisons consistent."
)
