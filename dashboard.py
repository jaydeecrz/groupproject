import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="China CO₂ Case Study", layout="wide")

st.title("China CO₂, Temperature, Energy, and GDP — Case Study Dashboard")
st.caption(
    "Reads files directly from this repository. CO₂, Energy, and GDP are wide Excel files reshaped to tidy; "
    "Temperature is a cleaned annual CSV. Includes extra-credit plot (China share of world CO₂) and a quick correlation."
)

# -----------------------
# Filenames (must match your repo)
# -----------------------
CO2_XLSX    = "yearly_co2_emissions_1000_tonnes (1).xlsx"   # wide by year, first col = country
ENERGY_XLSX = "energy_use_per_person.xlsx"                  # wide by year, first col = country
GDP_XLSX    = "gdp_per_capita_yearly_growth.xlsx"           # wide by year, first col = country
TEMP_CSV    = "temperature_china_cleaned.csv"               # tidy: Year + Temperature column

# -----------------------
# Helpers
# -----------------------
def _melt_years(df: pd.DataFrame, id_col: str, value_name: str) -> pd.DataFrame:
    """
    Robust wide→long reshape:
    - normalizes headers to strings
    - finds 4-digit year columns (1700–2100), tolerant to '1960.0'
    - returns [id_col, Year, value_name]
    """
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]

    # ensure ID column exists; fallbacks if needed
    if id_col not in df.columns:
        candidates = [c for c in df.columns if c.lower() in ("country", "country name", "nation")]
        id_col = candidates[0] if candidates else df.columns[0]

    # detect year columns
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
    return df[df[country_col].str.strip().str.lower().eq(country_name.lower())].copy()

@st.cache_data
def load_co2(path: str):
    """
    Load wide CO₂ (in 1000 tonnes) Excel → tidy:
    returns:
      co2_cn:  Year, CO₂ (Mt)
      co2_world: Year, CO₂_World (Mt)
    """
    df = pd.read_excel(path)
    # rename first col to Country
    df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="CO2_kt")
    long["CO₂ (Mt)"] = long["CO2_kt"] / 1000.0  # 1000 tonnes → Mt
    co2_cn = _country_filter(long, "Country", "China")[["Year", "CO₂ (Mt)"]]
    co2_world = long.groupby("Year", as_index=False)["CO₂ (Mt)"].sum().rename(columns={"CO₂ (Mt)":"CO₂_World (Mt)"})
    return co2_cn.reset_index(drop=True), co2_world

@st.cache_data
def load_energy(path: str):
    """Energy wide Excel → tidy China series: Year, Energy (kg oil-eq./capita)"""
    df = pd.read_excel(path)
    if "country" in df.columns:
        df = df.rename(columns={"country": "Country"})
    else:
        df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="Energy (kg oil-eq./capita)")
    return _country_filter(long, "Country", "China")[["Year", "Energy (kg oil-eq./capita)"]]

@st.cache_data
def load_gdp(path: str):
    """GDP per capita growth wide Excel → tidy China series: Year, GDP Growth (%)"""
    df = pd.read_excel(path)
    if "Country Name" in df.columns:
        df = df.rename(columns={"Country Name": "Country"})
    else:
        df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="GDP Growth (%)")
    return _country_filter(long, "Country", "China")[["Year", "GDP Growth (%)"]]

@st.cache_data
def load_temp(path: str):
    """Temperature CSV → normalize to Year, Temperature (°C)"""
    df = pd.read_csv(path)
    df.columns = [c.strip() for c in df.columns]
    # normalize common names
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

# -----------------------
# Load data
# -----------------------
co2_cn, co2_world = load_co2(CO2_XLSX)
energy_cn         = load_energy(ENERGY_XLSX)
gdp_cn            = load_gdp(GDP_XLSX)
temp_cn           = load_temp(TEMP_CSV)

# -----------------------
# Year range slider based on intersection
# -----------------------
year_min = max(s["Year"].min() for s in [co2_cn, co2_world, energy_cn, gdp_cn, temp_cn])
year_max = min(s["Year"].max() for s in [co2_cn, co2_world, energy_cn, gdp_cn, temp_cn])

st.sidebar.header("Controls")
yr0, yr1 = st.sidebar.slider(
    "Year range",
    min_value=int(year_min),
    max_value=int(year_max),
    value=(max(int(year_min), 1980), int(year_max)),
    step=1
)

def window(df): 
    return df[(df["Year"] >= yr0) & (df["Year"] <= yr1)].copy()

co2_cn_w    = window(co2_cn)
co2_world_w = window(co2_world)
energy_cn_w = window(energy_cn)
gdp_cn_w    = window(gdp_cn)
temp_cn_w   = window(temp_cn)

# -----------------------
# Row 1: CO₂ & Temperature
# -----------------------
c1, c2 = st.columns(2)
with c1:
    st.subheader("China CO₂ Emissions (Mt)")
    fig = px.line(co2_cn_w, x="Year", y="CO₂ (Mt)", markers=True)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("Converted from '1000 tonnes' to million tonnes (Mt).")

with c2:
    st.subheader("China Temperature (Annual Mean, °C)")
    fig = px.line(temp_cn_w, x="Year", y="Temperature (°C)", markers=True)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("National annual mean created from monthly city data → annual city means → national average.")

# -----------------------
# Row 2: Energy & GDP
# -----------------------
c3, c4 = st.columns(2)
with c3:
    st.subheader("Energy Use per Person (kg oil-eq./capita)")
    fig = px.line(energy_cn_w, x="Year", y="Energy (kg oil-eq./capita)", markers=True)
    st.plotly_chart(fig, use_container_width=True)

with c4:
    st.subheader("GDP per Capita Growth (%)")
    fig = px.line(gdp_cn_w, x="Year", y="GDP Growth (%)", markers=True)
    st.plotly_chart(fig, use_container_width=True)

# -----------------------
# Row 3: CO₂ vs Temperature (scatter + trendline) + correlation
# -----------------------
st.subheader("Relationship: CO₂ vs Temperature (China)")
df_ct = pd.merge(
    co2_cn_w.rename(columns={"CO₂ (Mt)":"CO2_Mt"}),
    temp_cn_w, on="Year", how="inner"
)
if not df_ct.empty:
    fig = px.scatter(df_ct, x="CO2_Mt", y="Temperature (°C)", trendline="ols",
                     hover_data=["Year"],
                     labels={"CO2_Mt":"CO₂ (Mt)", "Temperature (°C)":"Temperature (°C)"})
    st.plotly_chart(fig, use_container_width=True)

    # quick correlation
    try:
        from scipy.stats import pearsonr
        co, pv = pearsonr(df_ct["CO2_Mt"], df_ct["Temperature (°C)"])
        st.caption(f"Pearson r = {co:.3f}, p = {pv:.3g} (computed on overlapping years).")
    except Exception:
        st.caption("Correlation unavailable (scipy not installed).")
else:
    st.info("No overlapping years between CO₂ and Temperature in the selected window.")

# -----------------------
# Row 4: Extra Credit — China share of world CO₂
# -----------------------
st.subheader("Extra Credit: China’s CO₂ as % of Global Total")
df_ratio = pd.merge(
    co2_cn_w.rename(columns={"CO₂ (Mt)":"CO2_Mt"}),
    co2_world_w, on="Year", how="inner"
)
if not df_ratio.empty:
    world_col = "CO₂_World (Mt)"
    if world_col not in df_ratio.columns:
        # try to detect if name is slightly different
        wcol = [c for c in df_ratio.columns if "world" in c.lower() and "co" in c.lower()]
        if wcol:
            df_ratio = df_ratio.rename(columns={wcol[0]: world_col})
    if {"CO2_Mt", world_col}.issubset(df_ratio.columns):
        df_ratio["China_%_World"] = (df_ratio["CO2_Mt"] / df_ratio[world_col]) * 100.0
        fig = px.line(df_ratio, x="Year", y="China_%_World", markers=True,
                      labels={"China_%_World":"China’s % of World CO₂"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption("This ratio controls for global totals and shows China’s changing share.")
    else:
        st.info("World CO₂ total column not found in merged data.")
else:
    st.info("No overlapping years between China CO₂ and World total in the selected window.")

st.markdown("---")
st.markdown(
    "Notes: CO₂ (Gapminder/World Bank style) is stored as '1000 tonnes' and converted to Mt. "
    "Energy and GDP are World Bank wide-format series reshaped to tidy. "
    "Temperature is a pre-cleaned annual national mean (from monthly city data). "
    "All plots respect the year range selected in the sidebar."
)
