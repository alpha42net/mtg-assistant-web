import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time
import re

st.set_page_config(page_title="MTG Decklist Pro", layout="wide")

class MTGPDF(FPDF):
    def draw_header_box(self, x, y, label, value, w, h=8):
        self.rect(x, y, w, h)
        self.set_xy(x, y)
        self.set_font("Arial", "B", 8)
        self.cell(20, h, f" {label}:", 0)
        self.set_font("Arial", "", 9)
        self.cell(w-20, h, str(value), 0)

def clean_text(text):
    """Nettoie les caractères spéciaux pour éviter le crash Unicode"""
    if not isinstance(text, str): return str(text)
    # Remplace les tirets longs et caractères bizarres par du texte standard
    text = text.replace('—', '-').replace('//', '/')
    return text.encode('latin-1', 'replace').decode('latin-1')

def get_scryfall(name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={name.strip()}"
        res = requests.get(url, timeout=3).json()
        tl = res.get("type_line", "")
        return {"type": tl, "land": "Land" in tl, "basic": "Basic" in tl, "cmc": res.get("cmc", 0)}
    except: return {"type": "Unknown", "land": False, "basic": False, "cmc": 0}

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("Registration")
    last_n = st.text_input("LAST NAME", "BELEREN").upper()
    first_n = st.text_input("FIRST NAME", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", "My Deck")
    if st.button("🚨 FORCER RESET (Vider 80)"):
        st.session_state.clear()
        st.rerun()

file = st.file_uploader("📂 Importez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        raw = pd.read_csv(file)
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        data = []
        for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name = str(row[n_col])
            info = get_scryfall(name)
            qty = int(row['Quantity'])
            
            # --- LOGIQUE DE FORCE ---
            m, s, c = 0, 0, 0
            if info["basic"]: m = qty
            else:
                m = min(qty, 2)
                if qty > 2: s = 1
                if qty > 3: c = qty - 3
            
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": info["land"], "Type": info["type"], "CMC": info["cmc"]})
        st.session_state.master_df = pd.DataFrame(data).sort_values("Card Name")

    # On utilise une clé unique pour l'éditeur
    edited_df = st.data_editor(st.session_state.master_df, hide_index=True, use_container_width=True, key="editor_final")
    
    tm, ts = edited_df['Main'].sum(), edited_df['Side'].sum()
    tc = edited_df['Cut'].sum()

    # Affichage des compteurs (style tes captures)
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN", f"{tm} / 60", f"{tm-60} over" if tm > 60 else None, delta_color="inverse")
    col2.metric("SIDE", f"{ts} / 15")
    col3.metric("CUT (POUBELLE)", int(tc))

    if st.button("📄 GÉNÉRER PDF (VERSION FIXÉE)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        
        # --- PAGE 1 ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 18); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.ln(2)
        
        # En-têtes (Boîtes style Windows)
        pdf.draw_header_box(35, 22, "DATE", date_v, 65)
        pdf.draw_header_box(100, 22, "LOCATION", loc_v, 85)
        pdf.draw_header_box(35, 30, "EVENT", event_v, 150)
        pdf.draw_header_box(35, 38, "DECK", dname_v, 150)

        # Barre Nom Vertical (Alternative sans rotation pour éviter crash)
        pdf.rect(10, 50, 15, 230)
        pdf.set_font("Arial", "B", 10)
        pdf.set_xy(11, 150)
        pdf.cell(13, 10, "N", 0, 1, "C") # On écrit verticalement lettre par lettre ou simplement horizontal
        pdf.cell(13, 10, "A", 0, 1, "C")
        pdf.cell(13, 10, "M", 0, 1, "C")
        pdf.cell(13, 10, "E", 0, 1, "C")

        # Listes
        y_left = 60
        pdf.set_xy(30, 55); pdf.set_font("Arial", "B", 10); pdf.cell(85, 5, "Main Deck:", 0, 1)
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y_left); pdf.set_font("Arial", "", 8)
            pdf.cell(8, 4.5, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(77, 4.5, clean_text(r['Card Name']), "B", 1); y_left += 4.5
        
        pdf.set_xy(30, 255); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")

        # Droite : Lands & Side
        rx, ry = 120, 55
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 10); pdf.cell(75, 5, "Lands:", 0, 1); ry += 5
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 8)
            pdf.cell(8, 4.5, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(67, 4.5, clean_text(r['Card Name']), "B", 1); ry += 4.5
        
        ry += 5
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 10); pdf.cell(75, 5, "Sideboard:", 0, 1); ry += 5
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 8)
            pdf.cell(8, 4.5, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(67, 4.5, clean_text(r['Card Name']), "B", 1); ry += 4.5

        # TABLEAU JUGES (Boîtes fermées)
        pdf.set_xy(120, 230); pdf.set_font("Arial", "B", 8); pdf.cell(75, 6, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(120, 236); pdf.cell(37.5, 10, "Deck Check:", 1); pdf.cell(37.5, 10, "Status:", 1)
        pdf.set_xy(120, 246); pdf.cell(37.5, 10, "Judge:", 1); pdf.cell(37.5, 10, "Main Check:", 1)

        # --- PAGE 2 ---
        pdf.add_page(); pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE GEEK", 0, 1, "C")
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        pdf.ln(5)
        cols = ["Main", "Side", "Cut", "Nom de la Carte", "Type", "CMC"]
        w = [10, 10, 10, 75, 65, 15]
        for i, h in enumerate(cols): pdf.cell(w[i], 8, h, 1, 0, "C", True)
        pdf.ln()
        pdf.set_font("Arial", "", 8)
        for i, (_, r) in enumerate(edited_df.iterrows()):
            pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(10, 7, str(int(r['Main'])), 1, 0, "C", True)
            pdf.cell(10, 7, str(int(r['Side'])), 1, 0, "C", True)
            pdf.cell(10, 7, str(int(r['Cut'])), 1, 0, "C", True)
            pdf.cell(75, 7, f" {clean_text(r['Card Name'])}", 1, 0, "L", True)
            pdf.cell(65, 7, f" {clean_text(r['Type'][:35])}", 1, 0, "L", True)
            pdf.cell(15, 7, str(int(r['CMC'])), 1, 1, "C", True)

        st.download_button("📥 TÉLÉCHARGER PDF SANS ERREUR", data=pdf.output(dest='S').encode('latin-1'), file_name="deck_final.pdf")
