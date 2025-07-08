import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Config ---
st.set_page_config(layout="wide")
st.title("Deutschland: OECD-indikatoren")

COUNTRY = "DEU"
FREQ = "M"  # monatliche Daten

OECD_INDICATORS = {
    "BIP Jahreswachstumsrate (y/y)": "GDP",
    "Arbeitskostenindex (LCI)": "LCI",
    "Business Confidence Index": "BCI_CLI",
    "Composite Leading Indicator": "CLI",
    "Bau-PMI": "BCI_CONS"
}

@st.cache_data(ttl=3600)
def fetch_oecd(indicator: str, country: str, freq: str = "M") -> pd.Series:
    """Holt eine Zeitreihe von der OECD SDMX-JSON API."""
    url = f"https://stats.oecd.org/SDMX-JSON/data/KEI/{indicator}.{country}.{freq}/all"
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    data = resp.json()
    
    # Dimensionen extrahieren
    obs_dim = data["structure"]["dimensions"]["observation"][0]["values"]
    time_periods = [v["id"] for v in obs_dim]
    
    # Series-Daten (es gibt nur eine Serie pro Aufruf)
    series_dict = list(data["dataSets"][0]["series"].values())[0]
    observations = series_dict.get("observations", {})
    
    # Daten in DataFrame umwandeln
    rows = []
    for idx_str, obs in observations.items():
        idx = int(idx_str)
        if idx < len(time_periods):
            date = pd.to_datetime(time_periods[idx])
            value = obs[0]
            rows.append({"date": date, "value": value})
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series(dtype=float)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

# Sidebar: Auswahl der Indikatoren
selected = st.sidebar.multiselect("OECD-Indikatoren", list(OECD_INDICATORS.keys()), default=list(OECD_INDICATORS.keys()))

# Plot
fig = px.line()
for name in selected:
    code = OECD_INDICATORS[name]
    series = fetch_oecd(code, COUNTRY, FREQ)
    if not series.empty:
        fig.add_scatter(x=series.index, y=series.values, mode="lines+markers", name=name)
fig.update_layout(
    title="OECD-Zeitreihen (Deutschland)",
    xaxis_title="Datum", yaxis_title="Indexwert"
)
st.plotly_chart(fig, use_container_width=True)

# Table
st.subheader("Tabelle: Letzte 13 Perioden")
data = {}
# Bestimme Zeitpunkte aus erster Serie
dates = None
if selected:
    first_code = OECD_INDICATORS[selected[0]]
    first_ser = fetch_oecd(first_code, COUNTRY, FREQ)
    dates = first_ser.sort_index(ascending=False).index[:13]
cols = [d.strftime('%b %Y') for d in dates] if dates is not None else []
for name in selected:
    code = OECD_INDICATORS[name]
    ser = fetch_oecd(code, COUNTRY, FREQ).sort_index(ascending=False).head(13)
    vals = [f"{v:.2f}" for v in ser.tolist()]
    if len(vals) < len(cols):
        vals += [""] * (len(cols) - len(vals))
    data[name] = vals

df = pd.DataFrame.from_dict(data, orient='index', columns=cols)
df.index.name = 'Indikator'
st.dataframe(df)

st.markdown("*Quelle: OECD SDMX-JSON API*")
