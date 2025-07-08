# app.py
import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- App Config ---
st.set_page_config(layout="wide")
st.title("Deutschland: OECD-Indikatoren")

COUNTRY = "DEU"
FREQ    = "M"  # Monatsdaten

# --- Die Indikatoren, die wir abfragen wollen ---
OECD_INDICATORS = {
    "BIP Jahreswachstumsrate (y/y)": "GDP",
    "Arbeitskostenindex (LCI)":      "LCI",
    "Business Confidence Index":     "BCI_CLI",
    "Composite Leading Indicator":   "CLI",
    "Bau-PMI":                        "BCI_CONS"
}

# --- Robustes Fetch der SDMX-JSON API ---
@st.cache_data(ttl=3600)
def fetch_oecd(indicator: str, country: str, freq: str = "M") -> pd.Series:
    """
    Holt eine Zeitreihe von der OECD SDMX-JSON API.
    Gibt bei Fehlern oder fehlenden Daten eine leere Series zurück.
    """
    url = f"https://stats.oecd.org/SDMX-JSON/data/KEI/{indicator}.{country}.{freq}/all"
    try:
        r = requests.get(url, timeout=20)
        r.raise_for_status()
        j = r.json()
    except Exception:
        return pd.Series(dtype=float)

    # Struktur ermitteln
    struct = j.get("structure", {})
    dims   = struct.get("dimensions", {}).get("observation") \
          or struct.get("dimensions", {}).get("series")
    if not dims or not isinstance(dims, list):
        return pd.Series(dtype=float)
    time_values = dims[0].get("values", [])
    periods     = [v.get("id") for v in time_values if v.get("id")]

    # Erste Serie aus dataSets
    dsets     = j.get("dataSets", [])
    if not dsets:
        return pd.Series(dtype=float)
    series0   = dsets[0].get("series", {})
    if not series0:
        return pd.Series(dtype=float)
    first_ser = next(iter(series0.values()))
    obs       = first_ser.get("observations", {})

    rows = []
    for idx_str, val_list in obs.items():
        try:
            idx = int(idx_str)
            if idx < len(periods):
                dt = pd.to_datetime(periods[idx], errors="coerce")
                rows.append({"date": dt, "value": val_list[0]})
        except:
            continue

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.Series(dtype=float)
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    return df.set_index("date")["value"].sort_index()

# --- Sidebar: Auswahl der Indikatoren ---
selected = st.sidebar.multiselect(
    "OECD-Indikatoren für Deutschland",
    options=list(OECD_INDICATORS.keys()),
    default=list(OECD_INDICATORS.keys()),
)

# --- Chart ---
fig = px.line()
for name in selected:
    code = OECD_INDICATORS[name]
    s = fetch_oecd(code, COUNTRY, FREQ)
    if not s.empty:
        fig.add_scatter(x=s.index, y=s.values, mode="lines+markers", name=name)
fig.update_layout(
    title="OECD-Zeitreihen (Deutschland)",
    xaxis_title="Datum",
    yaxis_title="Indexwert",
    legend_title="Indikator"
)
st.plotly_chart(fig, use_container_width=True)

# --- Tabelle der letzten 13 Perioden ---
st.subheader("Letzte 13 Perioden")
table_data = {}
if selected:
    # Basistermine aus erster Serie
    first = fetch_oecd(OECD_INDICATORS[selected[0]], COUNTRY, FREQ)
    periods = first.sort_index(ascending=False).index[:13]
    cols = [p.strftime("%b %Y") for p in periods]

    for name in selected:
        code = OECD_INDICATORS[name]
        ser = fetch_oecd(code, COUNTRY, FREQ).sort_index(ascending=False).head(13)
        vals = [f"{v:.2f}" if pd.notna(v) else "" for v in ser.tolist()]
        # ggf. auf Länge bringen
        if len(vals) < len(cols):
            vals += [""] * (len(cols) - len(vals))
        table_data[name] = vals

    df = pd.DataFrame.from_dict(table_data, orient="index", columns=cols)
    df.index.name = "Indikator"
    st.dataframe(df)
else:
    st.write("Bitte wähle oben mindestens einen Indikator aus.")

st.markdown("---")
st.markdown("*Quelle: OECD SDMX-JSON API*")
