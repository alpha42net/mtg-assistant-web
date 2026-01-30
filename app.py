import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ET CLASSE PDF ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")

class MTGPDF(FPDF):
    def draw_header_box(self, x, y, label, value, w, h=7):
        """Dessine les boîtes fermées du haut comme sur Windows"""
        self.set_xy(x, y)
        self.rect(x, y, w, h) 
        self.set_font("Arial", "B", 8)
        self.cell(20, h, f"  {label}:", 0)
        self.set_font("Arial", "", 8)
        self.cell(w-20, h, str(value), 0)

    def vertical_name(self, x, y, text):
        """Rotation du nom sans erreur AttributeError"""
        self.set_font("Arial", "B", 8)
        self.rotate(90, x, y)
        self.text(x, y, text)
        self.rotate(0)

def clean_pdf_text(text):
    if not isinstance(text, str): return str(text)
    return text.encode('latin-1', 'replace').decode('latin-1')

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=3).json()
        t = res.get("type_line", "Unknown")
        return {"type": t, "is_land": "Land" in t, "is_basic": "Basic" in t, "cmc": res.get("cmc", 0)}
    except:
        return {"type": "Unknown", "is_land": False, "is_basic": False, "cmc": 0}

# --- INTERFACE UTILISATEUR ---
with st.sidebar:
    st.header("📝 Registration")
    last_n = st.text_input("LAST NAME", "BELEREN").upper()
    first_n = st.text_input("FIRST NAME", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", "My Deck")
    
    if st.button("♻️ RESET TOUT (FIX 80 CARTES)"):
        st.session_state.clear()
        st.rerun()

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        raw_df = pd.read_csv(file)
        raw_df.columns = [c.strip() for c in raw_df.columns]
        n_col = "Card Name" if "Card Name" in raw_df.columns else raw_df.columns[0]
        
        data = []
        for _, row in raw_df.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name, qty = str(row[n_col]), int(row['Quantity'])
            sf = get_scryfall_data(name)
            
            # --- LOGIQUE 2-1-1 POUR ÉVITER LE 80/60 ---
            m, s, c = 0, 0, 0
            if sf["is_basic"]:
                m = qty
            else:
                for i in range(1, qty + 1):
                    if i <= 2: m += 1
                    elif i == 3: s += 1
                    else: c += 1
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": sf["is_land"], "Type": sf["type"], "CMC": sf["cmc"]})
        st.session_state.master_df = pd.DataFrame(data).sort_values("Card Name")

    # ÉDITEUR
    edited_df = st.data_editor(st.session_state.master_df, hide_index=True, use_container_width=True)
    st.session_state.master_df = edited_df

    # MÉTRIQUES
    c_m, c_s = edited_df['Main'].sum(), edited_df['Side'].sum()
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN", f"{c_m} / 60", delta=int(c_m-60), delta_color="inverse")
    col2.metric("SIDE", f"{c_s} / 15", delta=int(c_s-15), delta_color="inverse")
    col3.metric("CUT", edited_df['Cut'].sum())

    if st.button("📄 GÉNERER LE PDF COMPLET (2 PAGES)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        
        # --- PAGE 1 : FORMULAIRE OFFICIEL ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.text(35, 15, "MAGIC: THE GATHERING DECKLIST")
        
        # Tableaux du haut (Boîtes fermées Windows)
        pdf.draw_header_box(35, 20, "DATE", date_v, 65)
        pdf.draw_header_box(100, 20, "LOCATION", loc_v, 85)
        pdf.draw_header_box(35, 27, "EVENT", event_v, 150)
        pdf.draw_header_box(35, 34, "DECK", dname_v, 150)
        
        # Barre latérale et Nom Vertical
        pdf.rect(10, 50, 15, 230)
        pdf.vertical_name(17, 160, f"NAME: {clean_pdf_text(last_n)}, {clean_pdf_text(first_n)}")

        # SECTION SPELLS (Gauche)
        pdf.set_xy(28, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y = 56
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)].iterrows():
            pdf.set_xy(28, y); pdf.set_font("Arial", "", 7)
            pdf.cell(8, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(77, 4, clean_pdf_text(r['Card Name']), "B", 1); y += 4
        
        pdf.set_xy(28, 260); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(c_m)), 1, 1, "C")

        # SECTION LANDS & SIDEBOARD (Droite)
        rx, ry = 118, 50
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Lands:", 0, 1); ry += 6
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 7)
            pdf.cell(8, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(74, 4, clean_pdf_text(r['Card Name']), "B", 1); ry += 4
        
        ry += 10
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Sideboard:", 0, 1); ry += 6
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 7)
            pdf.cell(8, 4, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(74, 4, clean_pdf_text(r['Card Name']), "B", 1); ry += 4
            
        pdf.set_xy(rx, 225); pdf.set_font("Arial", "B", 10)
        pdf.cell(62, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(c_s)), 1, 1, "C")

        # TABLEAU DES JUGES (Bas Droite)
        jy = 238
        pdf.set_xy(118, jy); pdf.set_font("Arial", "B", 7); pdf.cell(82, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(118, jy+5); pdf.cell(41, 10, "Deck Check:", 1); pdf.cell(41, 10, "Status:", 1)
        pdf.set_xy(118, jy+15); pdf.cell(41, 10, "Judge:", 1); pdf.cell(41, 10, "Main Check:", 1)

        # --- PAGE 2 : ANALYSE GEEK ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "ANALYSE GEEK DU DECK (INVENTAIRE)", 0, 1, "C")
        pdf.ln(5)
        
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        h = ["Main", "Side", "Cut", "Nom de la Carte", "Type", "CMC"]
        w = [12, 12, 12, 70, 64, 20]
        for i, text in enumerate(h): pdf.cell(w[i], 7, text, 1, 0, "C", True)
        pdf.ln()
        
        pdf.set_font("Arial", "", 7)
        for i, (_, r) in enumerate(edited_df.sort_values("Card Name").iterrows()):
            pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(12, 6, str(int(r['Main'])), 1, 0, "C", True)
            pdf.cell(12, 6, str(int(r['Side'])), 1, 0, "C", True)
            pdf.cell(12, 6, str(int(r['Cut'])), 1, 0, "C", True)
            pdf.cell(70, 6, f" {clean_pdf_text(r['Card Name'])}", 1, 0, "L", True)
            pdf.cell(64, 6, f" {clean_pdf_text(r['Type'][:40])}", 1, 0, "L", True)
            pdf.cell(20, 6, str(int(r['CMC'])), 1, 1, "C", True)

        pdf_bytes = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 TÉLÉCHARGER LE PACK PDF", data=pdf_bytes, file_name=f"Deck_{last_n}.pdf")
