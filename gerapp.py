import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Konfiguration & Secrets ---
# Füge in Streamlit-Secrets (Community Cloud) hinzu:
# DESTATIS_USER = "Felix_222@web.de"
# DESTATIS_PW   = "18Akrapovic03"
secrets = st.secrets
USER_DESTATIS = secrets["DESTATIS_USER"]
PW_DESTATIS   = secrets["DESTATIS_PW"]

# --- Indikatoren und Datenquellen ---
INDICATORS = {
    # GDP
    "GDP":                 {"source": "destatis", "series": "41111-0002"},  # Gesamtwirtschaftliches BIP in Mio. EUR
    "GDP Growth Rate":     {"source": "eurostat", "dataset": "nama_10_gdp", "filters": "unit=PC_GDP;geo=DE"},
    "GDP Annual Growth Rate": {"source": "oecd", "indicator": "GDP", "country": "DEU", "freq": "A"},

    # Arbeitsmarkt
    "Unemployment Rate":   {"source": "destatis", "series": "23121-0002"},  # Arbeitslosenquote (%), Monatswerte
    "Unemployment Change": {"source": "calc",    "base": "Unemployment Rate", "type": "diff"},
    "Labour Costs":        {"source": "oecd",     "indicator": "LCI", "country": "DEU"},
    "Wages":               {"source": "destatis", "series": "41121-0003"},  # Bruttojahresverdienst

    # Inflation
    "Inflation Rate":      {"source": "eurostat", "dataset": "prc_hicp_midx", "filters": "precision=1;unitCode=I15;geo=DE"},
    "Inflation Rate MoM":  {"source": "calc",    "base": "Inflation Rate", "type": "pct_change_m"},
    "Consumer Price Index CPI": {"source": "destatis", "series": "43121-0002"},
    "Harmonised Consumer Prices": {"source": "destatis", "series": "43190-0001"},
    "Core Consumer Prices": {"source": "destatis", "series": "43121-0004"},
    "Core Inflation Rate": {"source": "calc",    "base": "Core Consumer Prices", "type": "pct_change_y"},
    "Producer Prices":     {"source": "eurostat", "dataset": "prc_ppp_ind", "filters": "precision=1;unitCode=I15;geo=DE"},
    "Producer Prices Change": {"source": "calc",  "base": "Producer Prices", "type": "pct_change_y"},
    "Export Prices":       {"source": "destatis", "series": "43140-0002"},
    "Import Prices":       {"source": "destatis", "series": "43150-0002"},
    "Import Prices MoM":   {"source": "calc",    "base": "Import Prices", "type": "pct_change_m"},
    "Import Prices YoY":   {"source": "calc",    "base": "Import Prices", "type": "pct_change_y"},

    # Zinsen
    "Interest Rate":       {"source": "ecb",      "series": "M.M.DE.RT.0000.EUR.4F.G_N.A.1_STS.A"},
    "Interbank Rate":      {"source": "ecb",      "series": "M.M.DE.RT.0000.EUR.4F.G_N.A.1_STS.M.M"},

    # Außenwirtschaft
    "Balance of Trade":    {"source": "destatis", "series": "43120-0001"},
    "Current Account":     {"source": "bundesbank", "series": ".."},
    "Current Account to GDP": {"source": "calc",  "base1": "Current Account", "base2": "GDP", "type": "ratio"},
    "Exports":             {"source": "destatis", "series": "43100-0001"},
    "Imports":             {"source": "destatis", "series": "43110-0001"},
    "Auto Exports":        {"source": "destatis", "series": "23210-0001"},

    # Sentiment & Industrie
    "Business Confidence": {"source": "oecd",     "indicator": "BCI_CLI", "country": "DEU"},
    "Manufacturing PMI":   {"source": "destatis", "series": "..."},
    "Services PMI":        {"source": "oecd",     "indicator": "CLI_SERV", "country": "DEU"},
    "Composite PMI":       {"source": "oecd",     "indicator": "CLI_COMPO", "country": "DEU"},
    "Industrial Production": {"source": "ecb",     "series": "M.M.DE.IPG.IND.G_N.A.1_STS.M"},
    "Industrial Production MoM": {"source": "calc", "base": "Industrial Production", "type": "pct_change_m"},
    "ZEW Economic Sentiment Index": {"source": "oauth", "series": "..."},
    "Car Production":      {"source": "destatis", "series": "23230-0001"},
    "Composite Leading Indicator": {"source": "oecd",  "indicator": "CLI", "country": "DEU"},
    "Ifo Current Conditions": {"source": "destatis","series":"..."},
    "Ifo Expectations":    {"source": "destatis", "series":"..."},
    "ZEW Current Conditions": {"source": "..."},

    # Konsum & Bau
    "Consumer Confidence": {"source": "destatis", "series": "23311-0001"},
    "Retail Sales MoM":    {"source": "destatis", "series": "63211-0002"},
    "Retail Sales YoY":    {"source": "calc",    "base": "Retail Sales MoM", "type": "pct_change_y"},
    "Consumer Spending":   {"source": "destatis", "series": "63121-0001"},

    "Construction Output": {"source": "destatis", "series": "63411-0001"},
    "Housing Index":       {"source": "destatis", "series": "..."},
    "House Price Index YoY": {"source": "calc",   "base": "Housing Index", "type": "pct_change_y"},
    "Building Permits":    {"source": "destatis", "series": "..."},
    "Construction Orders": {"source": "destatis", "series": "..."},
    "Construction PMI":    {"source": "oecd",     "indicator": "BCI_CONS", "country": "DEU"}
}

# --- Fetch Functions Implementierung ---
@st.cache_data(ttl=3600)
def fetch_destatis(series_code: str) -> pd.Series:
    url = "https://api-genesis.destatis.de/SDEServer/rest/data"
    params = {"searchText": series_code, "startPeriod": "2010-01"}
    resp = requests.get(url, params=params, auth=(USER_DESTATIS, PW_DESTATIS))
    return parse_sdmx(resp.json())

@st.cache_data(ttl=3600)
def fetch_eurostat(dataset: str, filters: str) -> pd.Series:
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?format=JSON&{filters}"
    data = requests.get(url).json()
    return parse_eurostat(data)

@st.cache_data(ttl=3600)
def fetch_ecb(series: str) -> pd.Series:
    url = f"https://sdw-wsrest.ecb.europa.eu/service/data/{series}"
    data = requests.get(url, headers={"Accept":"application/json"}).json()
    return parse_sdmx(data)

@st.cache_data(ttl=3600)
def fetch_oecd(indicator: str, country: str, freq: str="M") -> pd.Series:
    url = f"https://stats.oecd.org/SDMX-JSON/data/KEI/{indicator}.{country}.{freq}/all"
    data = requests.get(url).json()
    return parse_oecd(data)

# --- Parsing-Hilfsfunktionen ---
def parse_sdmx(obj: dict) -> pd.Series:
    # universelles SDMX-JSON/REST-Parsing
    # implementiere nach DSD
    return pd.Series(dtype=float)


def parse_eurostat(obj: dict) -> pd.Series:
    # parse Eurostat JSON response
    return pd.Series(dtype=float)


def parse_oecd(obj: dict) -> pd.Series:
    # parse OECD SDMX-JSON
    return pd.Series(dtype=float)

# --- Helper: get_series ---
def get_series(name: str) -> pd.Series:
    cfg = INDICATORS[name]
    src = cfg["source"]
    if src == "destatis":
        return fetch_destatis(cfg["series"])
    if src == "eurostat":
        return fetch_eurostat(cfg["dataset"], cfg["filters"])
    if src == "ecb":
        return fetch_ecb(cfg["series"])
    if src == "oecd":
        return fetch_oecd(cfg["indicator"], cfg.get("country","DEU"), cfg.get("freq","M"))
    if src == "calc":
        base = get_series(cfg["base"])
        if cfg["type"] == "diff":
            return base.diff()
        if cfg["type"] == "pct_change_m":
            return base.pct_change(1)*100
        if cfg["type"] == "pct_change_y":
            return base.pct_change(12)*100
        if cfg["type"] == "ratio":
            num = get_series(cfg["base1"])
            den = get_series(cfg["base2"])
            return num / den
    return pd.Series(dtype=float)

# --- Streamlit UI ---
st.title("Deutschland Dashboard")
mode = st.sidebar.radio("Darstellung", ["Grafik","Tabelle"])
metrics = st.sidebar.multiselect("Indikatoren", list(INDICATORS.keys()), default=list(INDICATORS.keys()))

if mode == "Grafik":
    fig = px.line()
    for m in metrics:
        s = get_series(m)
        if not s.empty:
            fig.add_scatter(x=s.index, y=s.values, name=m)
    fig.update_layout(xaxis_title='Datum', yaxis_title='Wert')
    st.plotly_chart(fig, use_container_width=True)
else:
    # Tabellenansicht (letzte 13 Perioden)
    first = get_series(metrics[0]).sort_index(ascending=False)
    dates = first.index[:13]
    cols = [d.strftime('%b %Y') for d in dates]
    table = {}
    for m in metrics:
        vals = get_series(m).sort_index(ascending=False).head(13).tolist()
        table[m] = [f"{v:.2f}" if pd.notna(v) else "" for v in vals]
    df = pd.DataFrame.from_dict(table, orient='index', columns=cols)
    df.index.name='Indikator'
    st.dataframe(df)

st.markdown("*Datenquellen: Destatis (Basic Auth), Eurostat, ECB SDW, OECD.*")
