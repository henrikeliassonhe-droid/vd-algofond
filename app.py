import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# --- SIDINSTÄLLNINGAR ---
st.set_page_config(page_title="VD:ns Algofond", page_icon="📈", layout="wide")
st.title("📈 VD:ns Algofond - Kontrollpanel (OMXS30)")

# --- SIDOMENY (PARAMETRAR) ---
st.sidebar.header("⚙️ VD:ns Reglage")
SMA_KORT = st.sidebar.number_input("Hjärnan: Kort Trend (SMA)", value=40)
SMA_LANG = st.sidebar.number_input("Hjärnan: Lång Trend (SMA)", value=150)
VIX_PANIK = st.sidebar.number_input("Hjärnan: VIX Paniknivå", value=35.0)
RSI_KOP = st.sidebar.number_input("Krypskytten: RSI Köpgräns", value=25.0)
SMA_EXIT = st.sidebar.number_input("Krypskytten: Exit-snitt (SMA)", value=5)

@st.cache_data(ttl=900) # Sparar datan i 15 min (900 sek) så appen laddar blixtsnabbt
def ladda_data():
    # Hämta OMXS30 (^OMX) och VIX (^VIX)
    omx = yf.download('^OMX', period='3y', progress=False)
    vix = yf.download('^VIX', period='3y', progress=False)
    
    # Säkerställ kompatibilitet med nyare yfinance-uppdateringar
    if isinstance(omx.columns, pd.MultiIndex):
        omx_close = omx['Close'].iloc[:, 0]
    else:
        omx_close = omx['Close']
        
    if isinstance(vix.columns, pd.MultiIndex):
        vix_close = vix['Close'].iloc[:, 0]
    else:
        vix_close = vix['Close']
    
    df = pd.DataFrame({'OMXS30': omx_close, 'VIX': vix_close}).dropna()
    df.index = df.index.tz_localize(None)
    
    # --- BERÄKNINGAR ---
    df['SMA_Kort'] = df['OMXS30'].rolling(window=SMA_KORT).mean()
    df['SMA_Lang'] = df['OMXS30'].rolling(window=SMA_LANG).mean()
    df['SMA_Exit'] = df['OMXS30'].rolling(window=SMA_EXIT).mean()
    
    # Krypskyttens panikmätare (RSI-2)
    delta = df['OMXS30'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=1, adjust=False).mean()
    ema_down = down.ewm(com=1, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI_2'] = 100 - (100 / (1 + rs))
    
    # Beräkna historiska signaler för grafen
    # Röd växel = under båda SMA ELLER VIX > Panik
    df['Rod_Vaxel'] = ((df['OMXS30'] < df['SMA_Kort']) & (df['OMXS30'] < df['SMA_Lang'])) | (df['VIX'] > VIX_PANIK)
    # Köp = Inte röd växel OCH RSI < Köpgräns
    df['Kop_Signal'] = (~df['Rod_Vaxel']) & (df['RSI_2'] < RSI_KOP)
    
    return df.dropna()

st.write("⏳ Synkar med Stockholmsbörsen och Wall Street...")
df = ladda_data()

if not df.empty:
    # --- ANALYSERA DAGENS LÄGE ---
    dagens_pris = df['OMXS30'].iloc[-1]
    dagens_sma_kort = df['SMA_Kort'].iloc[-1]
    dagens_sma_lang = df['SMA_Lang'].iloc[-1]
    dagens_vix = df['VIX'].iloc[-1]
    dagens_rsi = df['RSI_2'].iloc[-1]
    dagens_exit = df['SMA_Exit'].iloc[-1]

    rod_vaxel = df['Rod_Vaxel'].iloc[-1]
    kop_signal = df['Kop_Signal'].iloc[-1]
    salj_signal = (dagens_pris > dagens_exit) or rod_vaxel

    # --- DASHBOARD UI (TOPPEN) ---
    st.markdown("---")
    st.markdown("### 🚦 Systemstatus: Idag kl 17:20")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("Sverige (OMXS30)", f"{dagens_pris:.2f}")
        
    with col2:
        st.metric("Skräckindex (VIX)", f"{dagens_vix:.2f}", "Krasch-varning!" if dagens_vix > VIX_PANIK else "Lugnt", delta_color="inverse")

    with col3:
        if rod_vaxel:
            st.error("🧠 HJÄRNAN: RÖD VÄXEL\n\nKraschrisk! Krypskytten vilar.")
        else:
            st.success("🧠 HJÄRNAN: GRÖN VÄXEL\n\nMarknaden är frisk.")
            
    with col4:
        st.metric(label="Krypskytten (RSI-2)", value=f"{dagens_rsi:.1f}", delta=f"{dagens_rsi - RSI_KOP:.1f} (Mål: < {RSI_KOP})", delta_color="inverse")
        
    st.markdown("---")
    
    st.subheader("🚨 Dagens Action (kl 17:20)")
    if kop_signal:
        st.error("🔥 **SKARPT LÄGE! KÖP x3!** Öppna Montrose och köp BULL OMX X3 NU!")
    elif salj_signal:
        st.warning("💰 **SÄLJ-SIGNAL!** Om du ligger inne: Sälj certifikatet och slussa vinsten till Kärnan!")
    else:
        st.info("☕ **AVVAKTA.** Inga larm idag. Låt Kärnportföljen jobba i fred.")

    st.markdown("---")

    # --- INTERAKTIV GRAF (PLOTLY) ---
    st.subheader("📊 Interaktiv Marknadsradar")

    fig = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.05)

    # Pris och Glidande Medelvärden
    fig.add_trace(go.Scatter(x=df.index, y=df['OMXS30'], mode='lines', name='OMXS30', line=dict(color='white')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Lang'], mode='lines', name='Trend (SMA 150)', line=dict(color='dodgerblue', dash='dot')), row=1, col=1)
    fig.add_trace(go.Scatter(x=df.index, y=df['SMA_Exit'], mode='lines', name='Exit (SMA 5)', line=dict(color='orange')), row=1, col=1)

    # Leta upp historiska köp-signaler för att måla ut dem i grafen
    buy_dates = df[df['Kop_Signal']].index
    buy_prices = df.loc[buy_dates, 'OMXS30']
    fig.add_trace(go.Scatter(x=buy_dates, y=buy_prices, mode='markers', name='Historiska Köp', marker=dict(color='lime', size=12, symbol='triangle-up')), row=1, col=1)

    # RSI-Mätaren i botten
    fig.add_trace(go.Scatter(x=df.index, y=df['RSI_2'], mode='lines', name='RSI-2', line=dict(color='purple')), row=2, col=1)
    fig.add_hline(y=RSI_KOP, line_dash="dash", line_color="lime", row=2, col=1, annotation_text="KÖP-ZON")

    fig.update_layout(height=600, template="plotly_dark", hovermode="x unified", margin=dict(l=0, r=0, t=30, b=0))
    st.plotly_chart(fig, use_container_width=True)

    st.caption("Uppdateras automatiskt. Din VD-rutin: Kolla appen kl 17:20 varje vardag.")
else:
    st.error("Kunde inte hämta data från Yahoo Finance just nu.")