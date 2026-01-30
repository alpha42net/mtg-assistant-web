import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")

class MTGPDF(FPDF):
    # Méthode robuste pour la rotation sans utiliser 'with'
    def vertical_name(self, x, y, text):
        self.set_font("Arial", "B", 8)
        self.rotate(90, x, y)
        self.text(x, y, text)
        self.rotate(0) # Reset la rotation immédiatement

def clean_pdf_text(text):
    if not isinstance(text, str): return str(text)
    return text.encode('latin-1', 'replace').decode('latin-1')

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=3).json()
        type_line = res.get("type_line", "")
        return {"type": type_line, "is_land": "Land" in type_line, "cmc": res.get("cmc", 0)}
    except: return {"type": "Unknown", "is_land": False, "cmc": 0}

# --- SIDEBAR ---
with st.sidebar:
    st.header("Registration")
    last_n = st.text_input("LAST NAME", "BELEREN").upper()
    first_n = st.text_input("FIRST NAME", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", "My Deck")
    
    # BOUTON CRUCIAL POUR RÉINITIALISER LES 80 CARTES
    if st.button("♻️ RESET COMPLET (FORCE 60 CARTES)"):
        for key in st.session_state.keys():
            del st.session_state[key]
        st.rerun()

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'df' not in st.session_state:
        raw_df = pd.read_csv(file)
        # Nettoyage des noms de colonnes
        raw_df.columns = [c.strip() for c in raw_df.columns]
        name_col = "Card Name" if "Card Name" in raw_df.columns else raw_df.columns[0]
        
        # Groupement et Logique 2-1-1 Immédiate
        data = []
        for _, row in raw_df.groupby(name_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name, qty = str(row[name_col]), int(row['Quantity'])
            sf = get_scryfall_data(name)
            
            # Répartition forcée pour vider le 80/60
            m, s, c = 0, 0, 0
            if "Basic" in sf['type']: m = qty
            else:
                for i in range(1, qty + 1):
                    if i <= 2: m += 1
                    elif i == 3: s += 1
                    else: c += 1
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": sf["is_land"], "Type": sf["type"], "CMC": sf["cmc"]})
        st.session_state.df = pd.DataFrame(data).sort_values("Card Name")

    # ÉDITEUR
    edited = st.data_editor(st.session_state.df, hide_index=True, use_container_width=True)
    st.session_state.df = edited

    # COMPTEURS
    c_m, c_s, c_c = edited['Main'].sum(), edited['Side'].sum(), edited['Cut'].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{c_m} / 60", delta=int(c_m-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{c_s} / 15", delta=int(c_s-15), delta_color="inverse")
    col3.metric("CUT (POUBELLE)", c_c)

    if st.button("📄 GÉNERER PDF (CONFORME WINDOWS)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        pdf.add_page()
        
        # --- EN-TÊTE ---
        pdf.set_font("Arial", "B", 16)
        pdf.text(35, 15, "MAGIC: THE GATHERING DECKLIST")
        
        # Lignes horizontales exactes
        pdf.set_font("Arial", "", 8)
        pdf.set_xy(35, 19); pdf.cell(35, 6, f"DATE: {date_v}", "B")
        pdf.set_x(75); pdf.cell(50, 6, f"LOCATION: {loc_v}", "B", 1)
        pdf.set_xy(35, 26); pdf.cell(90, 6, f"EVENT: {event_v}", "B", 1)
        pdf.set_xy(35, 33); pdf.cell(90, 6, f"DECK: {dname_v}", "B", 1)
        
        # Rectangle Gauche et Nom VERTICAL (Fixé)
        pdf.rect(10, 50, 15, 230)
        pdf.vertical_name(17, 160, f"NAME: {clean_pdf_text(last_n)}, {clean_pdf_text(first_n)}")

        # Colonne Gauche (Spells)
        pdf.set_xy(28, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y = 56
        for _, r in edited[(edited['Main'] > 0) & (edited['IsLand'] == False)].iterrows():
            pdf.set_xy(28, y); pdf.set_font("Arial", "", 7)
            pdf.cell(8, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(77, 4, clean_pdf_text(r['Card Name']), "B", 1); y += 4
        
        pdf.set_xy(28, 260); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(c_m)), 1, 1, "C")

        # Colonne Droite (Lands & Side)
        rx, ry = 118, 50
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Lands:", 0, 1); ry += 6
        for _, r in edited[(edited['Main'] > 0) & (edited['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 7)
            pdf.cell(8, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(74, 4, clean_pdf_text(r['Card Name']), "B", 1); ry += 4
        
        ry += 10
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Sideboard:", 0, 1); ry += 6
        for _, r in edited[edited['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 7)
            pdf.cell(8, 4, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(74, 4, clean_pdf_text(r['Card Name']), "B", 1); ry += 4
        
        # Totaux et Juges
        pdf.set_xy(rx, 225); pdf.cell(62, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(c_s)), 1, 1, "C")
        pdf.set_xy(118, 238); pdf.set_font("Arial", "B", 7); pdf.cell(82, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(118, 243); pdf.cell(41, 10, "Deck Check:", 1); pdf.cell(41, 10, "Status:", 1)
        pdf.set_xy(118, 253); pdf.cell(41, 10, "Judge:", 1); pdf.cell(41, 10, "Main Check:", 1)

        # --- PAGE 2 : ANALYSE ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(190, 10, "ANALYSE GEEK DU DECK", 0, 1, "C")
        pdf.ln(5); pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        h = ["Main", "Side", "Cut", "Nom de la Carte", "Type", "CMC"]
        w = [12, 12, 12, 70, 64, 20]
        for i, txt in enumerate(h): pdf.cell(w[i], 7, txt, 1, 0, "C", True)
        pdf.ln()
        pdf.set_font("Arial", "", 7)
        for i, (_, r) in enumerate(edited.sort_values("Card Name").iterrows()):
            pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(12, 6, str(int(r['Main'])), 1, 0, "C", True)
            pdf.cell(12, 6, str(int(r['Side'])), 1, 0, "C", True)
            pdf.cell(12, 6, str(int(r['Cut'])), 1, 0, "C", True)
            pdf.cell(70, 6, f" {clean_pdf_text(r['Card Name'])}", 1, 0, "L", True)
            pdf.cell(64, 6, f" {clean_pdf_text(r['Type'][:40])}", 1, 0, "L", True)
            pdf.cell(20, 6, str(int(r['CMC'])), 1, 1, "C", True)

        pdf_bytes = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 TÉLÉCHARGER LE PDF GEEK", data=pdf_bytes, file_name=f"Deck_{last_n}.pdf")
