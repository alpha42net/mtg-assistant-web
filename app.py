import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

st.set_page_config(page_title="MTG Assistant Pro", layout="wide")

def clean_str(text):
    if not isinstance(text, str): return str(text)
    return text.replace('\u2014', '-').replace('\u2013', '-').encode('latin-1', 'replace').decode('latin-1')

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            d = res.json()
            type_line = d.get("type_line", "")
            return {"type": type_line, "is_basic": "Basic Land" in type_line}
    except: pass
    return {"type": "Unknown", "is_basic": False}

# --- FORMULAIRE SIDEBAR ---
with st.sidebar:
    st.header("📝 Official Sheet Info")
    last_n = st.text_input("LAST NAME", "BELEREN")
    first_n = st.text_input("FIRST NAME", "Jace")
    dci_v = st.text_input("DCI / ID", "000")
    event_v = st.text_input("EVENT", "Grand Prix")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION", "Montreal")
    dname_v = st.text_input("DECK NAME", "Sultai Control")
    designer_v = st.text_input("DECK DESIGNER", "")

file = st.file_uploader("📂 Import CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        
        processed = []
        for _, row in df_g.iterrows():
            name = str(row[col_name])
            sf = get_scryfall_data(name)
            qty = int(row['Quantity'])
            
            # LOGIQUE 2-1-1
            m, s, c = 0, 0, 0
            if sf["is_basic"]: m = qty
            else:
                for i in range(1, qty + 1):
                    if i <= 2: m += 1
                    elif i == 3: s += 1
                    else: c += 1
            processed.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "Total": qty, "Type": sf["type"]})
        
        st.session_state.master_df = pd.DataFrame(processed).sort_values("Card Name")

    # --- INTERFACE ---
    edited_df = st.data_editor(st.session_state.master_df, hide_index=True, use_container_width=True, key="editor")
    st.session_state.master_df = edited_df

    m_tot, s_tot = edited_df['Main'].sum(), edited_df['Side'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN", f"{m_tot} / 60")
    col2.metric("SIDE", f"{s_tot} / 15")
    col3.metric("CUT", edited_df['Cut'].sum())

    if st.button("📄 GENERATE JUDGE-READY PDF", use_container_width=True, type="primary"):
        pdf = FPDF()
        pdf.add_page()
        
        # --- HEADER OFFICIEL ---
        pdf.set_font("Arial", "B", 14)
        pdf.cell(130, 10, "DECK REGISTRATION SHEET", 0, 0)
        pdf.set_font("Arial", "B", 8)
        # Tableau Juge (Haut Droite)
        pdf.cell(60, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_x(140)
        pdf.cell(30, 5, "Deck Check Rd #:", 1); pdf.cell(30, 5, "Status:", 1, 1)
        pdf.set_x(140)
        pdf.cell(30, 5, "Judge:", 1); pdf.cell(30, 5, "Main/SB:", 1, 1)
        
        pdf.ln(2)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(95, 8, f" Date: {clean_str(date_v)}", 1); pdf.cell(95, 8, f" Event: {clean_str(event_v)}", 1, 1)
        pdf.cell(95, 8, f" Location: {clean_str(loc_v)}", 1); pdf.cell(95, 8, f" Deck Name: {clean_str(dname_v)}", 1, 1)
        pdf.cell(95, 8, f" First Name: {clean_str(first_n)}", 1); pdf.cell(95, 8, f" Last Name: {clean_str(last_n.upper())}", 1, 1)
        
        # --- MAIN DECK ---
        pdf.ln(5)
        pdf.set_fill_color(220, 220, 220)
        pdf.cell(20, 7, "QTY", 1, 0, "C", True); pdf.cell(170, 7, "CARD NAME", 1, 1, "L", True)
        
        pdf.set_font("Arial", "", 9)
        for _, r in edited_df[edited_df['Main'] > 0].iterrows():
            pdf.cell(20, 6, str(int(r['Main'])), 1, 0, "C")
            pdf.cell(170, 6, f" {clean_str(r['Card Name'])}", 1, 1)
            
        pdf.set_font("Arial", "B", 9)
        pdf.cell(20, 7, str(int(m_tot)), 1, 0, "C"); pdf.cell(170, 7, " Total Number of Cards in Main Deck", 1, 1)

        # --- SIDEBOARD ---
        pdf.ln(5)
        pdf.cell(20, 7, "QTY", 1, 0, "C", True); pdf.cell(170, 7, "SIDEBOARD", 1, 1, "L", True)
        pdf.set_font("Arial", "", 9)
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.cell(20, 6, str(int(r['Side'])), 1, 0, "C")
            pdf.cell(170, 6, f" {clean_str(r['Card Name'])}", 1, 1)
        
        pdf.set_font("Arial", "B", 9)
        pdf.cell(20, 7, str(int(s_tot)), 1, 0, "C"); pdf.cell(170, 7, " Total Number of Cards in Sideboard", 1, 1)

        # --- PAGE 2 : INVENTAIRE WINDOWS ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "FULL SYSTEM INVENTORY (M/S/C)", 0, 1, "C")
        pdf.set_font("Arial", "B", 8)
        cols = [10, 10, 10, 100, 60]
        h = ["M", "S", "C", "Card Name", "Type"]
        for i, head in enumerate(h): pdf.cell(cols[i], 7, head, 1, 0, "C", True)
        pdf.ln()
        pdf.set_font("Arial", "", 7)
        for _, r in edited_df.sort_values("Card Name").iterrows():
            pdf.cell(10, 5, str(int(r['Main'])), 1, 0, "C")
            pdf.cell(10, 5, str(int(r['Side'])), 1, 0, "C")
            pdf.cell(10, 5, str(int(r['Cut'])), 1, 0, "C")
            pdf.cell(100, 5, f" {clean_str(r['Card Name'])}", 1, 0)
            pdf.cell(60, 5, f" {clean_str(r['Type'][:40])}", 1, 1)

        pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 DOWNLOAD JUDGE SHEET", data=pdf_out, file_name=f"Official_{last_n}.pdf")
