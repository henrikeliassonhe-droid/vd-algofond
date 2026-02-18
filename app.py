import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- SIDINSTÄLLNINGAR ---
st.set_page_config(page_title="VD:ns Algofond 2.0", page_icon="🏢", layout="wide")
st.title("🏢 VD:ns Algofond - Multi-Strategi Terminal")

# --- VD:ns AKTIE-UNIVERSUM (Svenska Storbolag) ---
OMXS_TICKERS = [
    "ABB.ST", "ALFA.ST", "ASSA-B.ST", "ATCO-A.ST", "AZN.ST", 
    "BOL.ST", "ERIC-B.ST", "EVO.ST", "HM-B.ST", "INVE-B.ST", 
    "NIBE-B.ST", "SAND.ST", "SEB-A.ST", "SWED-A.ST", "VOLV-B.ST",
    "TELIA.ST", "HEXA-B.ST", "SAAB-B.ST", "SCA-B.ST", "SHB-A.ST"
]

# --- DATA MOTORER ---
@st.cache_data(ttl=900)
def ladda_index_data():
    omx = yf.download('^OMX', period='2y', progress=False)
    vix = yf.download('^VIX', period='2y', progress=False)
    
    if isinstance(omx.columns, pd.MultiIndex): omx_close = omx['Close'].iloc[:, 0]
    else: omx_close = omx['Close']
        
    if isinstance(vix.columns, pd.MultiIndex): vix_close = vix['Close'].iloc[:, 0]
    else: vix_close = vix['Close']
    
    df = pd.DataFrame({'OMXS30': omx_close, 'VIX': vix_close}).dropna()
    df.index = df.index.tz_localize(None)
    
    df['SMA_40'] = df['OMXS30'].rolling(window=40).mean()
    df['SMA_150'] = df['OMXS30'].rolling(window=150).mean()
    df['SMA_5'] = df['OMXS30'].rolling(window=5).mean()
    
    delta = df['OMXS30'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    ema_up = up.ewm(com=1, adjust=False).mean()
    ema_down = down.ewm(com=1, adjust=False).mean()
    rs = ema_up / ema_down
    df['RSI_2'] = 100 - (100 / (1 + rs))
    
    df['Rod_Vaxel'] = ((df['OMXS30'] < df['SMA_40']) & (df['OMXS30'] < df['SMA_150'])) | (df['VIX'] > 35)
    return df.dropna()

@st.cache_data(ttl=3600) # Uppdaterar aktierna max 1 gång i timmen för prestanda
def ladda_aktie_data():
    data = []
    
    # Ladda ner alla priser i ett svep (för att appen ska starta fort)
    hist_all = yf.download(OMXS_TICKERS, period='1y', progress=False)
    
    if isinstance(hist_all.columns, pd.MultiIndex):
        hist_close = hist_all['Close']
    else:
        hist_close = hist_all
        
    for ticker in OMXS_TICKERS:
        try:
            if ticker not in hist_close.columns:
                continue
            
            hist = hist_close[ticker].dropna()
            if len(hist) < 100: continue
            
            # Hämta utdelningen direkt från Yahoo
            info = yf.Ticker(ticker).info
            div_yield = info.get('dividendYield', 0)
            if div_yield is None: div_yield = info.get('trailingAnnualDividendYield', 0)
            if div_yield is None: div_yield = 0
            
            pris = float(hist.iloc[-1])
            
            # Momentum: Hur mycket har aktien stigit de senaste 3 månaderna? (Ca 63 handelsdagar)
            pris_3m = float(hist.iloc[-63]) if len(hist) >= 63 else float(hist.iloc[0])
            momentum = ((pris / pris_3m) - 1) * 100
            
            sma_50 = float(hist.rolling(50).mean().iloc[-1])
            sma_150 = float(hist.rolling(150).mean().iloc[-1])
            
            trend = "🟢 Upptrend" if pris > sma_150 else "🔴 Nedtrend"
            kopsignal_swing = (pris > sma_50) and (pris > sma_150)
            
            data.append({
                'Aktie': ticker.replace('.ST', ''),
                'Pris (kr)': round(pris, 2),
                'Momentum 3M (%)': round(momentum, 2),
                'Utdelning (%)': round(div_yield * 100, 2),
                'Trend': trend,
                'Köpbar Swing (Mellan)': kopsignal_swing,
                'SMA_150': sma_150
            })
        except Exception as e:
            continue
    return pd.DataFrame(data)

st.write("⏳ Synkar med Stockholmsbörsen & Skannar Storbolagen...")
df_index = ladda_index_data()
df_aktier = ladda_aktie_data()

# --- FLIK-SYSTEMET ---
tab1, tab2, tab3 = st.tabs(["🎯 Krypskytten (Index)", "🏄‍♂️ Mellanportföljen (Swing)", "💰 Kärnan (Utdelningar)"])

# ==========================================
# FLIK 1: KRYPSKYTTEN
# ==========================================
with tab1:
    st.header("🎯 Krypskytten: Letar Panik i Index")
    st.write("Din dagliga rutin kl 17:20. Ligger i kontanter, anfaller vid panik med x3 hävstång.")
    
    if not df_index.empty:
        dagens_pris = df_index['OMXS30'].iloc[-1]
        dagens_vix = df_index['VIX'].iloc[-1]
        dagens_rsi = df_index['RSI_2'].iloc[-1]
        rod_vaxel = df_index['Rod_Vaxel'].iloc[-1]
        salj_signal = (dagens_pris > df_index['SMA_5'].iloc[-1]) or rod_vaxel
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Sverige (OMXS30)", f"{dagens_pris:.2f}")
        col2.metric("Skräckindex (VIX)", f"{dagens_vix:.2f}", "Fara!" if dagens_vix > 35 else "Lugnt", delta_color="inverse")
        col3.metric("Panik-mätaren (RSI-2)", f"{dagens_rsi:.1f}", "KÖP-LÄGE!" if dagens_rsi < 25 and not rod_vaxel else "Avvakta", delta_color="inverse")

        st.markdown("---")
        if rod_vaxel:
            st.error("🧠 HJÄRNAN: RÖD VÄXEL. Marknaden är i krasch-läge. Krypskytten har utegångsförbud.")
        elif dagens_rsi < 25:
            st.success("🔥 KÖP-SIGNAL! RSI är i botten. Köp BULL OMX X3 på Montrose!")
        elif salj_signal:
            st.warning("💰 SÄLJ-SIGNAL! Priset har studsat. Sälj certifikatet och slussa vinsten!")
        else:
            st.info("☕ Avvakta. Inget extremt läge på index just nu.")

# ==========================================
# FLIK 2: MELLANPORTFÖLJEN
# ==========================================
with tab2:
    st.header("🏄‍♂️ Mellanportföljen (Swing Trading)")
    st.write("Här hittar vi aktierna som rör sig snabbast just nu. Vi hyr in oss i några månader och rider vågen. Sälj när trenden dör!")
    
    if not df_aktier.empty:
        # Sortera ut de som är köpbara (över SMA50 och SMA150) och ranka efter Momentum
        vinnare = df_aktier[df_aktier['Köpbar Swing (Mellan)'] == True].sort_values(by='Momentum 3M (%)', ascending=False)
        forlorare = df_aktier[df_aktier['Köpbar Swing (Mellan)'] == False].sort_values(by='Momentum 3M (%)', ascending=True)

        st.markdown("### 🚀 Topp 5 Hetaste Aktierna (Köp-lista)")
        st.write("Dessa bolag har starkast underliggande dragkraft på hela börsen just nu. Köp 2-3 av dessa till din Mellanportfölj!")
        
        if not vinnare.empty:
            st.dataframe(vinnare[['Aktie', 'Pris (kr)', 'Momentum 3M (%)', 'Trend']].head(5), hide_index=True, use_container_width=True)
        else:
            st.warning("Inga aktier har en stark positiv trend just nu. Håll kassan!")

        st.markdown("### 🗑️ Sälj-Varning (Fallande momentum)")
        st.write("Äger du någon av dessa i Mellanportföljen? Sälj dem direkt. Deras trend har brutits.")
        if not forlorare.empty:
            st.dataframe(forlorare[['Aktie', 'Pris (kr)', 'Momentum 3M (%)', 'Trend']].head(5), hide_index=True, use_container_width=True)

# ==========================================
# FLIK 3: KÄRNAN
# ==========================================
with tab3:
    st.header("💰 Kärnportföljen (Utdelnings-Skannern)")
    st.write("Här placerar du vinsten från Krypskytten. Vi letar efter storbolag med hög direktavkastning, men **Hjärnan blockerar bolag i krasch**.")
    
    if not df_aktier.empty:
        # Sortera på utdelning, men BARA bolag i Upptrend
        utdelnings_kungar = df_aktier[df_aktier['Trend'] == "🟢 Upptrend"].sort_values(by='Utdelning (%)', ascending=False)
        
        st.success("🏦 Godkända Utdelningsaktier (I positiv trend)")
        st.dataframe(utdelnings_kungar[['Aktie', 'Pris (kr)', 'Utdelning (%)', 'Trend']].head(8), hide_index=True, use_container_width=True)
        
        # Visa value traps
        value_traps = df_aktier[df_aktier['Trend'] == "🔴 Nedtrend"].sort_values(by='Utdelning (%)', ascending=False)
        st.error("🚨 Varningslistan: Hög utdelning men aktien KRASCHAR (Värdefälla/Swedbank-fällan)")
        st.dataframe(value_traps[['Aktie', 'Pris (kr)', 'Utdelning (%)', 'Trend']].head(5), hide_index=True, use_container_width=True)
