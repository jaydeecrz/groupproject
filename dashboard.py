import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="China CO₂ Case Study", layout="wide")

st.title("China CO₂, Temperature, Energy, and GDP — Case Study Dashboard")
st.caption(
    "Files loaded directly from this repository: CO₂ (Gapminder/World Bank style wide → long), "
    "Energy (wide → long), GDP per capita growth (wide → long), and Temperature (cleaned annual CSV)."
)

# -----------------------
# FILE NAMES (must match repo)
# -----------------------
CO2_XLSX    = "yearly_co2_emissions_1000_tonnes (1).xlsx"   # wide by year, first col = country
ENERGY_XLSX = "energy_use_per_person.xlsx"                  # wide by year, first col = country
GDP_XLSX    = "gdp_per_capita_yearly_growth.xlsx"           # wide by year, first col = country
TEMP_CSV    = "temperature_china_cleaned.csv"               # tidy: Year, Temperature (°C) or Value

# -----------------------
# Helpers
# -----------------------
def _melt_years(df, id_col, value_name):
    """Reshape wide year columns to tidy long with columns: [id_col, Year, value_name]."""
    # keep numeric year columns only
    year_cols = [c for c in df.columns if str(c).isdigit()]
    if not year_cols:
        # sometimes years are ints already
        year_cols = [c for c in df.columns if isinstance(c, (int, float))]
        year_cols = list(map(str, year_cols))
        df = df.rename(columns={int(c): str(c) for c in year_cols if isinstance(c, int)})
    out = pd.melt(df, id_vars=[id_col], value_vars=[c for c in df.columns if c.isdigit()],
                  var_name="Year", value_name=value_name)
    out["Year"] = pd.to_numeric(out["Year"], errors="coerce")
    out = out.dropna(subset=["Year"]).astype({"Year": int})
    return out.sort_values("Year")

@st.cache_data
def load_co2(path: str):
    """Load wide CO₂ (in 1000 tonnes), return (China, World) in Mt."""
    df = pd.read_excel(path)
    first = df.columns[0]
    df = df.rename(columns={first: "Country"})
    long = _melt_years(df, id_col="Country", value_name="CO2_kt")
    # convert 1000 tonnes → million tonnes
    long["CO₂ (Mt)"] = long["CO2_kt"] / 1000.0
    cn = long[long["Country"].str.strip().eq("China")][["Year", "CO₂ (Mt)"]]
    world = long.groupby("Year", as_index=False)["CO₂ (Mt)"].sum().rename(columns={"CO₂ (Mt)":"CO₂_World (Mt)"})
    return cn.reset_index(drop=True), world

@st.cache_data
def load_energy(path: str):
    """Load wide energy per person; return China tidy."""
    df = pd.read_excel(path)
    # normalize first column name
    if "country" in df.columns:
        df = df.rename(columns={"country": "Country"})
    else:
        df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="Energy (kg oil-eq./capita)")
    return long[long["Country"].str.strip().eq("China")][["Year", "Energy (kg oil-eq./capita)"]]

@st.cache_data
def load_gdp(path: str):
    """Load wide GDP per capita growth; return China tidy."""
    df = pd.read_excel(path)
    if "Country Name" in df.columns:
        df = df.rename(columns={"Country Name": "Country"})
    else:
        df = df.rename(columns={df.columns[0]: "Country"})
    long = _melt_years(df, id_col="Country", value_name="GDP Growth (%)")
    return long[long["Country"].str.strip().eq("China")][["Year", "GDP Growth (%)"]]

@st.cache_data
def load_temp(path: str):
    """Load tidy temperature CSV; normalize column names to ['Year','Temperature (°C)']."""
    df = pd.read_csv(path)
    cols = {c: str(c).strip() for c in df.columns}
    df = df.rename(columns=cols)
    if "Temp (°C)" in df.columns and "Temperature (°C)" not in df.columns:
        df = df.rename(columns={"Temp (°C)":"Temperature (°C)"})
    if "Value" in df.columns and "Temperature (°C)" not in df.columns:
        df = df.rename(columns={"Value":"Temperature (°C)"})
    if "Year" not in df.columns or "Temperature (°C)" not in df.columns:
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
# Sidebar: year range (based on intersection across series)
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
    st.caption("CO₂ converted from '1000 tonnes' to million tonnes (Mt).")

with c2:
    st.subheader("China Temperature (Annual Mean, °C)")
    fig = px.line(temp_cn_w, x="Year", y="Temperature (°C)", markers=True)
    st.plotly_chart(fig, use_container_width=True)
    st.caption("National annual mean from monthly city data → annual city means → national average.")

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
# Row 3: CO₂ vs Temperature (scatter + trendline)
# -----------------------
st.subheader("Relationship: CO₂ vs Temperature (China)")
df_ct = pd.merge(
    co2_cn_w.rename(columns={"CO₂ (Mt)":"CO2_Mt"}),
    temp_cn_w,
    on="Year",
    how="inner"
)
if not df_ct.empty:
    fig = px.scatter(df_ct, x="CO2_Mt", y="Temperature (°C)", trendline="ols",
                     hover_data=["Year"],
                     labels={"CO2_Mt":"CO₂ (Mt)", "Temperature (°C)":"Temperature (°C)"})
    st.plotly_chart(fig, use_container_width=True)
    st.caption("A positive trend suggests years with higher CO₂ tend to be warmer in China.")
else:
    st.info("No overlapping years between CO₂ and Temperature in the selected window.")

# -----------------------
# Row 4: Extra Credit — China share of world CO₂
# -----------------------
st.subheader("Extra Credit: China’s CO₂ as % of Global Total")
df_ratio = pd.merge(
    co2_cn_w.rename(columns={"CO₂ (Mt)":"CO2_Mt"}),
    co2_world_w,
    on="Year",
    how="inner"
)
if not df_ratio.empty:
    if "CO₂_World (Mt)" not in df_ratio.columns:
        # try to detect
        wcol = [c for c in df_ratio.columns if "world" in c.lower() and "co" in c.lower()]
        if wcol:
            df_ratio = df_ratio.rename(columns={wcol[0]:"CO₂_World (Mt)"})
    if {"CO2_Mt", "CO₂_World (Mt)"}.issubset(df_ratio.columns):
        df_ratio["China_%_World"] = (df_ratio["CO2_Mt"] / df_ratio["CO₂_World (Mt)"]) * 100.0
        fig = px.line(df_ratio, x="Year", y="China_%_World", markers=True,
                      labels={"China_%_World":"China’s % of World CO₂"})
        st.plotly_chart(fig, use_container_width=True)
        st.caption("This ratio controls for global totals and shows China’s changing share.")
    else:
        st.info("World CO₂ total column not found.")
else:
    st.info("No overlapping years between China CO₂ and World total in the selected window.")

st.markdown("---")
st.markdown(
    "Notes: CO₂ comes from a wide-format Excel of '1000 tonnes' by year and country. "
    "Energy and GDP per capita growth are World Bank wide-format and reshaped to tidy. "
    "Temperature is an annual national mean based on monthly city data. "
    "All charts respect the year range selected in the sidebar."
)
