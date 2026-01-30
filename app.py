import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")

def clean_pdf_text(text):
    if not isinstance(text, str): return str(text)
    return text.encode('latin-1', 'replace').decode('latin-1')

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=4).json()
        type_line = res.get("type_line", "")
        return {
            "type": type_line, 
            "cmc": res.get("cmc", 0),
            "is_land": "Land" in type_line,
            "is_basic": "Basic" in type_line
        }
    except: return {"type": "Unknown", "cmc": 0, "is_land": False, "is_basic": False}

# --- INTERFACE ---
with st.sidebar:
    st.header("Registration")
    last_n = st.text_input("LAST NAME", "BELEREN")
    first_n = st.text_input("FIRST NAME", "Jace")
    dci_v = st.text_input("DCI", "000")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", "My Deck")

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

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
            
            # --- LOGIQUE DE CALCUL WINDOWS ---
            m, s, c = 0, 0, 0
            if sf["is_basic"]:
                m = qty # Les basic lands vont tous dans le Main
            else:
                # Répartition 2-1-1 pour chaque bloc de 4
                for i in range(1, qty + 1):
                    if i <= 2: m += 1
                    elif i == 3: s += 1
                    else: c += 1
            
            processed.append({
                "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                "Total": qty, "Type": sf["type"], "IsLand": sf["is_land"]
            })
        st.session_state.master_df = pd.DataFrame(processed).sort_values("Card Name")

    edited_df = st.data_editor(st.session_state.master_df, hide_index=True, use_container_width=True)
    st.session_state.master_df = edited_df

    c1, c2, c3 = st.columns(3)
    c_m = edited_df['Main'].sum()
    c_s = edited_df['Side'].sum()
    c1.metric("MAIN DECK", f"{c_m} / 60")
    c2.metric("SIDEBOARD", f"{c_s} / 15")
    c3.metric("TOTAL CUT", edited_df['Cut'].sum())

    if st.button("📄 GÉNERER PDF WINDOWS", use_container_width=True, type="primary"):
        pdf = FPDF()
        pdf.add_page()
        
        # --- PAGE 1 (Copie conforme de ton code image_9c15df.png) ---
        pdf.set_font("Arial", "B", 16)
        pdf.text(35, 15, "MAGIC: THE GATHERING DECKLIST")
        pdf.set_font("Arial", "", 8)
        pdf.text(35, 22, f"DATE: {clean_pdf_text(date_v)}   LOCATION: {clean_pdf_text(loc_v)}")
        pdf.set_xy(35, 29); pdf.cell(165, 7, f"EVENT: {clean_pdf_text(event_v)}", 0)
        pdf.set_xy(35, 36); pdf.cell(165, 7, f"DECK: {clean_pdf_text(dname_v)}", 0)
        
        pdf.rect(10, 50, 15, 230) # Colonne verticale gauche
        with pdf.rotation(90, 17, 160):
            pdf.set_font("Arial", "B", 7)
            pdf.text(17, 160, f"NAME: {clean_pdf_text(last_n.upper())}, {clean_pdf_text(first_n)}")

        # Section Spells
        pdf.set_xy(28, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y = 56
        spells = edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)]
        for _, r in spells.iterrows():
            pdf.set_font("Arial", "", 7); pdf.set_xy(28, y)
            pdf.cell(8, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(77, 4, clean_pdf_text(r['Card Name']), "B", 1); y += 4
        
        pdf.set_xy(28, 260); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R")
        pdf.cell(20, 10, str(int(c_m)), 1, 1, "C")

        # Section Lands & Sideboard (Colonne Droite)
        rx, yr = 118, 50
        pdf.set_xy(rx, yr); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Lands:", 0, 1); yr += 6
        lands = edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)]
        for _, r in lands.iterrows():
            pdf.set_font("Arial", "", 7); pdf.set_xy(rx, yr)
            pdf.cell(8, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(74, 4, clean_pdf_text(r['Card Name']), "B", 1); yr += 4
        
        yr += 5
        pdf.set_xy(rx, yr); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Sideboard:", 0, 1); yr += 6
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_font("Arial", "", 7); pdf.set_xy(rx, yr)
            pdf.cell(8, 4, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(74, 4, clean_pdf_text(r['Card Name']), "B", 1); yr += 4
            
        pdf.set_xy(rx, 225); pdf.set_font("Arial", "B", 10)
        pdf.cell(62, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(c_s)), 1, 1, "C")

        # --- TABLEAU DES JUGES (FOR OFFICIAL USE ONLY) ---
        jy = 238
        pdf.set_xy(118, jy); pdf.set_font("Arial", "B", 7); pdf.cell(82, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(118, jy+5); pdf.cell(41, 10, "Deck Check:", 1); pdf.cell(41, 10, "Status:", 1)
        pdf.set_xy(118, jy+15); pdf.cell(41, 10, "Judge:", 1); pdf.cell(41, 10, "Main Check:", 1)

        # PAGE 2 : ARCHIVE GEEK (Inventaire complet)
        pdf.add_page(); pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "ANALYSE GEEK DU DECK (TOUTES LES CARTES)", 0, 1, "C")
        
        pdf.ln(5); pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        headers = ["Main", "Side", "Cut", "Nom de la Carte", "Type Scryfall"]
        widths = [12, 12, 12, 80, 74]
        for i, h in enumerate(headers): pdf.cell(widths[i], 6, h, 1, 0, "C", True)
        pdf.ln()
        
        pdf.set_font("Arial", "", 7)
        for _, r in edited_df.iterrows():
            pdf.cell(12, 5, str(int(r['Main'])), 1, 0, "C")
            pdf.cell(12, 5, str(int(r['Side'])), 1, 0, "C")
            pdf.cell(12, 5, str(int(r['Cut'])), 1, 0, "C")
            pdf.cell(80, 5, f" {clean_pdf_text(r['Card Name'])}", 1, 0)
            pdf.cell(74, 5, f" {clean_pdf_text(r['Type'][:45])}", 1, 1)

        pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 TÉLÉCHARGER LE PDF GEEK", data=pdf_out, file_name=f"Deck_{last_n}.pdf")
