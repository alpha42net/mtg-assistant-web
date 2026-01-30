import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION INITIALE ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Web Edition (Full)")

# --- FONCTION API SCRYFALL ---
def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            d = res.json()
            type_line = d.get("type_line", "")
            return {
                "type": type_line, 
                "cmc": d.get("cmc", 0),
                "is_basic": "Basic Land" in type_line or "Basic Snow Land" in type_line
            }
    except: pass
    return {"type": "Unknown", "cmc": 0, "is_basic": False}

# --- SIDEBAR (Tous les champs Windows) ---
with st.sidebar:
    st.header("👤 Player Info")
    last_n = st.text_input("LAST NAME", value="BELEREN")
    first_n = st.text_input("FIRST NAME", value="Jace")
    dci_v = st.text_input("DCI / ID", value="000")
    
    st.header("🏆 Tournament Info")
    event_v = st.text_input("EVENT", placeholder="ex: Regional")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION", value="")
    table_v = st.text_input("TABLE #", value="")
    dname_v = st.text_input("DECK NAME", value="My Deck")

# --- LOGIQUE DE CHARGEMENT ET RÉPARTITION ---
file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    # On initialise le DataFrame seulement s'il n'existe pas encore
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Running Windows Logic Distribution...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                total_qty = int(row['Quantity'])
                
                # LOGIQUE WINDOWS :
                # 1. Si Terrain de base -> 100% dans le MAIN
                if sf["is_basic"]:
                    m, s, c = total_qty, 0, 0
                else:
                    # 2. Si Sort -> Max 4 dans le MAIN
                    m = min(total_qty, 4)
                    reste = total_qty - m
                    # 3. Le reste dans le SIDE (max 4 par défaut ou tout le reste)
                    s = min(reste, 4) 
                    # 4. Le surplus final dans le CUT
                    c = reste - s
                
                processed.append({
                    "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                    "Total": total_qty, "Type": sf["type"], "CMC": sf["cmc"]
                })
                time.sleep(0.01)
            
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Distribution Complete!", state="complete")

    # --- ÉDITEUR ET CALCULS EN TEMPS RÉEL ---
    # On récupère les données de la session
    working_df = st.session_state.master_df

    # L'éditeur interactif (Trier en cliquant sur les colonnes)
    edited_df = st.data_editor(
        working_df,
        hide_index=True,
        use_container_width=True,
        key="main_editor",
        column_config={
            "Total": st.column_config.NumberColumn("Total", disabled=True),
            "Type": st.column_config.TextColumn("Type", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True)
        }
    )

    # RECALCUL IMMÉDIAT DES COMPTEURS
    # On met à jour le Total par ligne si l'utilisateur change Main/Side/Cut
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']
    st.session_state.master_df = edited_df # Sauvegarde

    m_total = edited_df['Main'].sum()
    s_total = edited_df['Side'].sum()
    c_total = edited_df['Cut'].sum()
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{m_total} / 60", delta=int(m_total-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_total} / 15", delta=int(s_total-15), delta_color="inverse")
    col3.metric("TOTAL CUT", c_total)

    # --- GÉNÉRATION DU PDF (FORMAT WINDOWS) ---
    if st.button("📄 GENERATE PROFESSIONAL PDF", use_container_width=True, type="primary"):
        pdf = FPDF()
        
        # PAGE 1 : DECKLIST OFFICIELLE
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        
        pdf.set_font("Arial", "", 8)
        pdf.cell(95, 7, f"LAST NAME: {last_n.upper()}", 1)
        pdf.cell(95, 7, f"FIRST NAME: {first_n}", 1, 1)
        pdf.cell(63, 7, f"DCI #: {dci_v}", 1); pdf.cell(64, 7, f"DATE: {date_v}", 1); pdf.cell(63, 7, f"TABLE #: {table_v}", 1, 1)
        pdf.cell(190, 7, f"EVENT: {event_v} @ {loc_v}", 1, 1)
        pdf.cell(190, 7, f"DECK NAME: {dname_v}", 1, 1)
        
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(20, 8, "QTY", 1, 0, "C"); pdf.cell(170, 8, "CARD NAME (MAIN DECK)", 1, 1, "C")
        pdf.set_font("Arial", "", 9)
        for _, r in edited_df[edited_df['Main'] > 0].iterrows():
            pdf.cell(20, 6, str(r['Main']), 1, 0, "C")
            pdf.cell(170, 6, f" {r['Card Name']}", 1, 1)
            
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(20, 8, "QTY", 1, 0, "C"); pdf.cell(170, 8, "SIDEBOARD", 1, 1, "C")
        pdf.set_font("Arial", "", 9)
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.cell(20, 6, str(r['Side']), 1, 0, "C")
            pdf.cell(170, 6, f" {r['Card Name']}", 1, 1)

        # PAGE 2 : FULL INVENTORY TABLE (Le tableau Windows)
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "FULL INVENTORY & ANALYSIS", 0, 1, "C")
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        cols = [10, 10, 10, 10, 75, 63, 12]
        h = ["M", "S", "C", "Tot", "Card Name", "Type", "CMC"]
        for i, text in enumerate(h):
            pdf.cell(cols[i], 7, text, 1, 0, "C", True)
        pdf.ln()
        
        pdf.set_font("Arial", "", 7)
        for _, r in edited_df.iterrows():
            pdf.cell(10, 5, str(r['Main']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Side']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Cut']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Total']), 1, 0, "C")
            pdf.cell(75, 5, f" {r['Card Name']}", 1, 0, "L")
            pdf.cell(63, 5, f" {r['Type'][:38]}", 1, 0, "L")
            pdf.cell(12, 5, str(r['CMC']), 1, 1, "C")

        pdf_output = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 DOWNLOAD FINAL PDF", data=pdf_output, file_name=f"{last_n}_Decklist.pdf", use_container_width=True)
