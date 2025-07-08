import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- App Configuration ---
st.set_page_config(layout="wide")
st.title("Deutschland: OECD-Indikatoren")

# --- Constants ---
COUNTRY = "DEU"
FREQ = "M"  # Monthly frequency

OECD_INDICATORS = {
    "BIP Jahreswachstumsrate (y/y)": "GDP",
    "Arbeitskostenindex (LCI)": "LCI",
    "Business Confidence Index": "BCI_CLI",
    "Composite Leading Indicator": "CLI",
    "Bau-PMI": "BCI_CONS"
}

@st.cache_data(ttl=3600)
def fetch_oecd(indicator: str, country: str, freq: str = "M") -> pd.Series:
    """
    Holt eine Zeitreihe von der OECD SDMX-JSON API.
    Liefert eine leere Series, falls etwas nicht stimmt.
    """
    url = f"https://stats.oecd.org/SDMX-JSON/data/KEI/{indicator}.{country}.{freq}/all"
    try:
        resp = requests.get(url, timeout=20)
        resp.raise_for_status()
        j = resp.json()
    except Exception:
        return pd.Series(dtype=float)

    # Find observation dimensions
    struct = j.get("structure", {})
    dims = struct.get("dimensions", {}).get("observation") or struct.get("dimensions", {}).get("series")
    if not dims or not isinstance(dims, list):
        return pd.Series(dtype=float)
    time_values = dims[0].get("values", [])
    periods = [v.get("id") for v in time_values if "id" in v]

    # Get the first series in the dataset
    data_sets = j.get("dataSets", [])
    if not data_sets:
        return pd.Series(dtype=float)
    series_dict = data_sets[0].get("series", {})
    if not series_dict:
        return pd.Series(dtype=float)
    first_series = next(iter(series_dict.values()))
    observations = first_series.get("observations", {})

    # Build DataFrame
    rows = []
    for idx_str, obs in observations.items():
        try:
            idx = int(idx_str)
            if idx < len(periods):
                date = pd.to_datetime(periods[idx], errors="coerce")
                value = obs[0]
                rows.append({"date": date, "value": value})
        except:
            continue
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series(dtype=float)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

# --- Sidebar: Indicator Selection ---
selected = st.sidebar.multiselect(
    "OECD-Indikatoren",
    list(OECD_INDICATORS.keys()),
    default=list(OECD_INDICATORS.keys())
)

# --- Plot View ---
fig = px.line()
for name in selected:
    code = OECD_INDICATORS[name]
    series = fetch_oecd(code, COUNTRY, FREQ)
    if not series.empty:
        fig.add_scatter(x=series.index, y=series.values, mode="lines+markers", name=name)
fig.update_layout(
    title="OECD-Zeitreihen (Deutschland)",
    xaxis_title="Datum",
    yaxis_title="Indexwert"
)
st.plotly_chart(fig, use_container_width=True)

# --- Table View ---
st.subheader("Tabelle: Letzte 13 Perioden")

# Determine table columns
dates = None
if selected:
    first_code = OECD_INDICATORS[selected[0]]
    first_ser = fetch_oecd(first_code, COUNTRY, FREQ)
    dates = first_ser.sort_index(ascending=False).index[:13]
cols = [d.strftime('%b %Y') for d in dates] if dates is not None else []

# Build table data
data = {}
for name in selected:
    code = OECD_INDICATORS[name]
    ser = fetch_oecd(code, COUNTRY, FREQ).sort_index(ascending=False).head(13)
    vals = [f"{v:.2f}" if pd.notna(v) else "" for v in ser.tolist()]
    if len(vals) < len(cols):
        vals += [""] * (len(cols) - len(vals))
    data[name] = vals

df = pd.DataFrame.from_dict(data, orient='index', columns=cols)
df.index.name = 'Indikator'
st.dataframe(df)

# Footer
st.markdown("*Quelle: OECD SDMX-JSON API*")
