import streamlit as st
import yfinance as yf
import pandas as pd
import numpy as np

# --- SIDINSTÄLLNINGAR ---
st.set_page_config(page_title="VD:ns Algofond 3.0", page_icon="🏢", layout="wide")
st.title("🏢 VD:ns Algofond - Terminal (Paper Trading)")

# --- VD:ns AKTIE-UNIVERSUM ---
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

@st.cache_data(ttl=3600)
def ladda_aktie_data():
    data = []
    hist_all = yf.download(OMXS_TICKERS, period='1y', progress=False)
    
    if isinstance(hist_all.columns, pd.MultiIndex): hist_close = hist_all['Close']
    else: hist_close = hist_all
        
    for ticker in OMXS_TICKERS:
        try:
            if ticker not in hist_close.columns: continue
            hist = hist_close[ticker].dropna()
            if len(hist) < 100: continue
            
            info = yf.Ticker(ticker).info
            div_yield = info.get('dividendYield', 0)
            if div_yield is None: div_yield = info.get('trailingAnnualDividendYield', 0)
            if div_yield is None: div_yield = 0
            
            pris = float(hist.iloc[-1])
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
            })
        except Exception: continue
    return pd.DataFrame(data)

st.write("⏳ Synkar med Stockholmsbörsen & Skannar Storbolagen...")
df_index = ladda_index_data()
df_aktier = ladda_aktie_data()

# --- FLIK-SYSTEMET ---
tab1, tab2, tab3, tab4 = st.tabs(["🎯 Krypskytt", "🏄‍♂️ Swing", "💰 Utdelning", "📓 Paper Trade"])

with tab1:
    st.header("🎯 Krypskytten: Letar Panik i Index")
    if not df_index.empty:
        dagens_pris = df_index['OMXS30'].iloc[-1]
        dagens_vix = df_index['VIX'].iloc[-1]
        dagens_rsi = df_index['RSI_2'].iloc[-1]
        rod_vaxel = df_index['Rod_Vaxel'].iloc[-1]
        salj_signal = (dagens_pris > df_index['SMA_5'].iloc[-1]) or rod_vaxel
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Sverige (OMXS30)", f"{dagens_pris:.2f}")
        col2.metric("Skräckindex (VIX)", f"{dagens_vix:.2f}", "Fara!" if dagens_vix > 35 else "Lugnt", delta_color="inverse")
        col3.metric("Panik-mätaren (RSI-2)", f"{dagens_rsi:.1f}", "KÖP!" if dagens_rsi < 25 and not rod_vaxel else "Avvakta", delta_color="inverse")

        st.markdown("---")
        if rod_vaxel: st.error("🧠 HJÄRNAN: RÖD VÄXEL. Marknaden är i krasch-läge.")
        elif dagens_rsi < 25: st.success("🔥 KÖP-SIGNAL! RSI är i botten. Gå till Flik 4 och köp Krypskytten fiktivt!")
        elif salj_signal: st.warning("💰 SÄLJ-SIGNAL! Priset har studsat. Sälj certifikatet och slussa vinsten!")
        else: st.info("☕ Avvakta. Inget extremt läge på index just nu.")

with tab2:
    st.header("🏄‍♂️ Mellanportföljen (Swing Trading)")
    if not df_aktier.empty:
        vinnare = df_aktier[df_aktier['Köpbar Swing (Mellan)'] == True].sort_values(by='Momentum 3M (%)', ascending=False)
        st.write("🚀 **Topp 5 Hetaste Aktierna just nu**")
        if not vinnare.empty: st.dataframe(vinnare[['Aktie', 'Pris (kr)', 'Momentum 3M (%)', 'Trend']].head(5), hide_index=True, use_container_width=True)

with tab3:
    st.header("💰 Kärnportföljen (Utdelnings-Skannern)")
    if not df_aktier.empty:
        utdelnings_kungar = df_aktier[df_aktier['Trend'] == "🟢 Upptrend"].sort_values(by='Utdelning (%)', ascending=False)
        st.dataframe(utdelnings_kungar[['Aktie', 'Pris (kr)', 'Utdelning (%)', 'Trend']].head(8), hide_index=True, use_container_width=True)

# ==========================================
# FLIK 4: PAPER TRADING (KASSABOKEN)
# ==========================================
with tab4:
    st.header("📓 Bankvalvet: Paper Trading")
    st.write("Här testkör du dina strategier live med fiktiva pengar!")
    
    # 1. Skapa portföljen i minnet om den inte finns
    if 'portfolj' not in st.session_state:
        st.session_state.portfolj = pd.DataFrame(columns=['Datum', 'Tillgång', 'Köpkurs', 'Antal', 'Investerat'])

    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🛒 Ny Fiktiv Affär")
        alla_val = ["🎯 BULL OMXS30 X3 (Krypskytten)"] + df_aktier['Aktie'].tolist() if not df_aktier.empty else ["🎯 BULL OMXS30 X3 (Krypskytten)"]
        
        vald_tillgang = st.selectbox("Välj Tillgång:", alla_val)
        antal = st.number_input("Antal andelar/aktier:", min_value=1, value=100)
        
        # Hämta live-pris
        if vald_tillgang == "🎯 BULL OMXS30 X3 (Krypskytten)":
            aktuellt_pris = float(df_index['OMXS30'].iloc[-1]) if not df_index.empty else 0.0
        else:
            rad = df_aktier[df_aktier['Aktie'] == vald_tillgang]
            aktuellt_pris = float(rad['Pris (kr)'].iloc[0]) if not rad.empty else 0.0
            
        st.info(f"Dagens kurs just nu: **{aktuellt_pris:.2f} kr**")
        
        if st.button("✅ Logga Köp"):
            ny_rad = pd.DataFrame({
                'Datum': [pd.Timestamp.now().strftime("%Y-%m-%d %H:%M")],
                'Tillgång': [vald_tillgang],
                'Köpkurs': [aktuellt_pris],
                'Antal': [antal],
                'Investerat': [aktuellt_pris * antal]
            })
            st.session_state.portfolj = pd.concat([st.session_state.portfolj, ny_rad], ignore_index=True)
            st.success("Köpt! (Glöm inte att spara filen till höger 👉)")

    with col2:
        st.subheader("💾 Moln-Säkerhet (Viktigt!)")
        st.caption("Appen glömmer dina affärer när du stänger den. **Ladda ner** kassaboken när du är klar, och **Ladda upp** den imorgon igen för att väcka minnet!")
        
        # Ladda ner
        csv = st.session_state.portfolj.to_csv(index=False).encode('utf-8')
        st.download_button("⬇️ Ladda ner Kassabok (Spara)", data=csv, file_name="min_paper_trading.csv", mime="text/csv")
        
        st.write("---")
        # Ladda upp
        uppladdad_fil = st.file_uploader("⬆️ Ladda upp Kassabok (Väck minnet)", type=["csv"])
        if uppladdad_fil is not None:
            st.session_state.portfolj = pd.read_csv(uppladdad_fil)
            st.success("Portföljen är inläst och uppdaterad med dagsfärska priser!")

    st.markdown("---")
    st.subheader("📊 Dina Öppna Positioner (Live-Värdering)")
    
    if not st.session_state.portfolj.empty:
        df_visning = st.session_state.portfolj.copy()
        nu_priser = []
        vinster_kr = []
        vinster_pct = []
        
        for index, row in df_visning.iterrows():
            t = row['Tillgång']
            kop_pris = float(row['Köpkurs'])
            inv = float(row['Investerat'])
            
            if t == "🎯 BULL OMXS30 X3 (Krypskytten)":
                live_pris = float(df_index['OMXS30'].iloc[-1]) if not df_index.empty else kop_pris
                # HÄVSTÅNGSMAGIN: Indexrörelsen multipliceras med 3!
                utv = ((live_pris / kop_pris) - 1) * 3
            else:
                rad = df_aktier[df_aktier['Aktie'] == t]
                live_pris = float(rad['Pris (kr)'].iloc[0]) if not rad.empty else kop_pris
                utv = (live_pris / kop_pris) - 1
                
            vinst = inv * utv
            nu_priser.append(round(live_pris, 2))
            vinster_kr.append(vinst)
            vinster_pct.append(utv * 100)
            
        df_visning['Live-kurs'] = nu_priser
        df_visning['Utveckling (%)'] = [f"{p:+.2f} %" for p in vinster_pct]
        df_visning['Vinst/Förlust (kr)'] = [f"{v:+.0f} kr" for v in vinster_kr]
        
        # Rensa bort onödiga kolumner för snyggare visning
        st.dataframe(df_visning[['Datum', 'Tillgång', 'Investerat', 'Utveckling (%)', 'Vinst/Förlust (kr)']], hide_index=True, use_container_width=True)
        
        tot_vinst = sum(vinster_kr)
        st.metric("💰 Total Fiktiv Vinst/Förlust", f"{tot_vinst:+,.0f} kr")
        
        if st.button("🗑️ Sälj allt och nollställ kassaboken"):
            st.session_state.portfolj = pd.DataFrame(columns=['Datum', 'Tillgång', 'Köpkurs', 'Antal', 'Investerat'])
            st.rerun()
    else:
        st.info("Valvet är tomt. Gör ett låtsasköp ovan!")
