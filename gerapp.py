import streamlit as st
import requests
import pandas as pd
import plotly.express as px

# --- Konfiguration & Secrets ---
# Lege in Streamlit-Secrets an:
# DESTATIS_USER = "Felix_222@web.de"
# DESTATIS_PW   = "18Akrapovic03"
USER_DE = st.secrets["DESTATIS_USER"]
PW_DE   = st.secrets["DESTATIS_PW"]

# --- Indikatoren und Quellen ---
INDICATORS = {
    # BIP
    "GDP":                 {"src":"destatis","code":"41111-0002"},  # BIP in Mio. EUR
    "GDP Growth Rate":     {"src":"eurostat","dataset":"nama_10_gdp","filters":"unit=PC_GDP;geo=DE"},
    "GDP Annual Growth Rate": {"src":"oecd","indicator":"GDP","country":"DEU","freq":"A"},

    # Arbeitsmarkt
    "Unemployment Rate":   {"src":"destatis","code":"23121-0002"},  # %
    "Unemployment Change": {"src":"calc","base":"Unemployment Rate","type":"diff"},
    "Labour Costs":        {"src":"oecd","indicator":"LCI","country":"DEU"},
    "Wages":               {"src":"destatis","code":"41121-0003"},  # Bruttojahresverdienst, EUR

    # Inflation
    "Inflation Rate":      {"src":"eurostat","dataset":"prc_hicp_midx","filters":"precision=1;unitCode=I15;geo=DE"},
    "Inflation Rate MoM":  {"src":"calc","base":"Inflation Rate","type":"pct_change_m"},
    "CPI":                 {"src":"destatis","code":"43121-0002"},
    "Harmonised CPI":      {"src":"destatis","code":"43190-0001"},
    "Core CPI":            {"src":"destatis","code":"43121-0004"},
    "Core Inflation Rate": {"src":"calc","base":"Core CPI","type":"pct_change_y"},
    "Producer Prices":     {"src":"eurostat","dataset":"prc_ppp_ind","filters":"precision=1;unitCode=I15;geo=DE"},
    "Producer Prices Change": {"src":"calc","base":"Producer Prices","type":"pct_change_y"},
    "Export Prices":       {"src":"destatis","code":"43140-0002"},
    "Import Prices":       {"src":"destatis","code":"43150-0002"},
    "Import Prices MoM":   {"src":"calc","base":"Import Prices","type":"pct_change_m"},
    "Import Prices YoY":   {"src":"calc","base":"Import Prices","type":"pct_change_y"},

    # Zinsen
    "Interest Rate":       {"src":"ecb","code":"M.M.DE.RT.0000.EUR.4F.G_N.A.1_STS.A"},
    "Interbank Rate":      {"src":"ecb","code":"M.M.DE.RT.0000.EUR.4F.G_N.A.1_STS.M.M"},

    # Außenwirtschaft
    "Exports":             {"src":"destatis","code":"43100-0001"},
    "Imports":             {"src":"destatis","code":"43110-0001"},
    "Balance of Trade":    {"src":"destatis","code":"43120-0001"},
    "Current Account":     {"src":"bundesbank","code":"BBK01_WT5514"},  # Beispiel Bundesbank
    "Current Account to GDP": {"src":"calc","base1":"Current Account","base2":"GDP","type":"ratio"},
    "Auto Exports":        {"src":"destatis","code":"23210-0001"},

    # Industrie & Sentiment
    "Industrial Production":      {"src":"ecb","code":"M.M.DE.IPG.IND.G_N.A.1_STS.M"},
    "Industrial Production MoM":  {"src":"calc","base":"Industrial Production","type":"pct_change_m"},
    "Car Production":            {"src":"destatis","code":"23230-0001"},
    "Business Confidence":       {"src":"oecd","indicator":"BCI_CLI","country":"DEU"},

    # Konsum & Bau
    "Consumer Confidence":    {"src":"destatis","code":"23311-0001"},
    "Retail Sales MoM":       {"src":"destatis","code":"63211-0002"},
    "Retail Sales YoY":       {"src":"calc","base":"Retail Sales MoM","type":"pct_change_y"},
    "Consumer Spending":      {"src":"destatis","code":"63121-0001"},
    "Construction Output":    {"src":"destatis","code":"63411-0001"},
    "Building Permits":        {"src":"destatis","code":"63421-0001"},
    "House Price Index":      {"src":"destatis","code":"..."},  # Code fehlt
    "House Price YoY":         {"src":"calc","base":"House Price Index","type":"pct_change_y"},

    # PMI (OECD)
    "Manufacturing PMI":  {"src":"oecd","indicator":"CLI_MANU","country":"DEU"},
    "Services PMI":       {"src":"oecd","indicator":"CLI_SERV","country":"DEU"},
    "Composite PMI":      {"src":"oecd","indicator":"CLI_COMPO","country":"DEU"},
}

# --- Fetch-Funktionen ---
@st.cache_data(ttl=3600)
def fetch_destatis(code: str) -> pd.Series:
    url = "https://api-genesis.destatis.de/SDEServer/rest/data"
    params = {"searchText": code, "startPeriod": "2010-01"}
    try:
        r = requests.get(url, params=params, auth=(USER_DE, PW_DE), timeout=10)
        r.raise_for_status()
        data = r.json()
    except:
        return pd.Series(dtype=float)
    # implementiere JSON->Series-Parsing
    return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def fetch_eurostat(dataset: str, filters: str) -> pd.Series:
    url = f"https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset}?format=JSON&{filters}"
    try:
        d = requests.get(url, timeout=10).json()
    except:
        return pd.Series(dtype=float)
    tl = d.get('dimension',{}).get('time',{}).get('category',{}).get('label',{})
    vals = d.get('value',{})
    rows=[]
    for k,v in vals.items():
        per=tl.get(str(k))
        try: dt=pd.to_datetime(per)
        except: continue
        rows.append({'date':dt,'value':v})
    df=pd.DataFrame(rows)
    df['value']=pd.to_numeric(df['value'],errors='coerce')
    return df.set_index('date')['value'].sort_index()

@st.cache_data(ttl=3600)
def fetch_ecb(code: str) -> pd.Series:
    url=f"https://sdw-wsrest.ecb.europa.eu/service/data/{code}"
    try:
        j=requests.get(url,headers={'Accept':'application/json'}, timeout=10).json()
    except:
        return pd.Series(dtype=float)
    return pd.Series(dtype=float)

@st.cache_data(ttl=3600)
def fetch_oecd(ind: str, country: str, freq: str='M') -> pd.Series:
    url=f"https://stats.oecd.org/SDMX-JSON/data/KEI/{ind}.{country}.{freq}/all"
    try:
        j=requests.get(url,timeout=10).json()
    except:
        return pd.Series(dtype=float)
    # einfacher Parser
    return pd.Series(dtype=float)

# Verzögerte Berechnung (Differenz/MoM/YoY/Ratio)
def get_series(name: str) -> pd.Series:
    cfg=INDICATORS[name]
    src=cfg['src']
    if src=='destatis': return fetch_destatis(cfg['code'])
    if src=='eurostat':return fetch_eurostat(cfg['dataset'],cfg['filters'])
    if src=='ecb':      return fetch_ecb(cfg['code'])
    if src=='oecd':     return fetch_oecd(cfg['indicator'],cfg['country'],cfg.get('freq','M'))
    if src=='calc':
        base=get_series(cfg['base'])
        if cfg['type']=='diff': return base.diff()
        if cfg['type']=='pct_change_m': return base.pct_change(1)*100
        if cfg['type']=='pct_change_y': return base.pct_change(12)*100
        if cfg['type']=='ratio':return get_series(cfg['base1']).div(get_series(cfg['base2']))
    return pd.Series(dtype=float)

# --- UI ---
st.title('Deutschland Dashboard')
mode=st.sidebar.radio('Darstellung',['Grafik','Tabelle'])
metrics=st.sidebar.multiselect('Indikatoren',list(INDICATORS.keys()),default=list(INDICATORS.keys()))

if mode=='Grafik':
    fig=px.line()
    for m in metrics:
        s=get_series(m)
        if not s.empty:
            fig.add_scatter(x=s.index,y=s.values,mode='lines',name=m)
    fig.update_layout(xaxis_title='Datum',yaxis_title='Wert')
    st.plotly_chart(fig,use_container_width=True)
else:
    first=get_series(metrics[0]).sort_index(ascending=False)
    dates=first.index[:13]
    cols=[d.strftime('%b %Y') for d in dates]
    table={}
    for m in metrics:
        vals=get_series(m).sort_index(ascending=False).head(13).tolist()
        table[m]=[f"{v:.2f}" if pd.notna(v) else "" for v in vals]
    df=pd.DataFrame.from_dict(table,orient='index',columns=cols)
    df.index.name='Indikator'
    st.dataframe(df)

st.markdown('*Datenquellen: Destatis (Basic Auth), Eurostat, ECB, OECD.*')
