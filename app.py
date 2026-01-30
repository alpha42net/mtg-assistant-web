import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

st.set_page_config(page_title="MTG Decklist Pro", layout="wide")

class MTGPDF(FPDF):
    def draw_header_box(self, x, y, label, value, w, h=8):
        self.rect(x, y, w, h)
        self.set_xy(x, y)
        self.set_font("Arial", "B", 8)
        self.cell(20, h, f" {label}:", 0)
        self.set_font("Arial", "", 9)
        self.cell(w-20, h, str(value), 0)

    def vertical_name_safe(self, x, y, text):
        self.set_font("Arial", "B", 10)
        self.rotate(90, x, y)
        self.text(x, y, text)
        self.rotate(0)

def safe_encode(text):
    if not isinstance(text, str): return str(text)
    return text.replace('//', '/').encode('latin-1', 'replace').decode('latin-1')

def get_scryfall_info(name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={name.strip()}"
        res = requests.get(url, timeout=3).json()
        tl = res.get("type_line", "")
        return {"land": "Land" in tl, "basic": "Basic" in tl, "type": tl, "cmc": res.get("cmc", 0)}
    except: return {"land": False, "basic": False, "type": "Unknown", "cmc": 0}

# --- INTERFACE ---
with st.sidebar:
    st.header("Registration")
    last_n = st.text_input("NOM", "BELEREN").upper()
    first_n = st.text_input("PRÉNOM", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", "My Deck")

file = st.file_uploader("📂 Importez votre CSV", type="csv")

if file:
    # Si on vient de charger un fichier ou si on veut forcer le calcul
    if 'raw_data' not in st.session_state or st.button("🔄 RECALCULER 60 CARTES (SANS SUPPRIMER LE FICHIER)"):
        raw = pd.read_csv(file)
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        data = []
        for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name = str(row[n_col])
            info = get_scryfall_info(name)
            total = int(row['Quantity'])
            
            # --- LOGIQUE 2-1-1 ---
            if info["basic"]: m, s, c = total, 0, 0
            else:
                m = min(total, 2)
                s = 1 if total >= 3 else 0
                c = max(0, total - 3)
            
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, 
                         "IsLand": info["land"], "Type": info["type"], "CMC": info["cmc"]})
        
        st.session_state.raw_data = pd.DataFrame(data).sort_values("Card Name")

    # Éditeur de données
    edited_df = st.data_editor(st.session_state.raw_data, hide_index=True, use_container_width=True, key="mtg_editor_v15")
    tm, ts = edited_df['Main'].sum(), edited_df['Side'].sum()
    st.info(f"Main Deck: {tm} | Sideboard: {ts}")

    if st.button("📄 GÉNÉRER PDF COMPLET (P1 + P2)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        
        # --- PAGE 1 ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 18); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.draw_header_box(35, 20, "DATE", date_v, 65)
        pdf.draw_header_box(100, 20, "LOCATION", loc_v, 85)
        pdf.draw_header_box(35, 28, "EVENT", event_v, 150)
        pdf.draw_header_box(35, 36, "DECK", dname_v, 150)

        pdf.rect(10, 50, 15, 230)
        pdf.vertical_name_safe(18, 160, f"NAME: {last_n}, {first_n}")

        # Listes
        y_l = 56
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y_l); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C"); pdf.cell(78, 4, safe_encode(r['Card Name']), "B", 1); y_l += 4
        
        pdf.set_xy(30, 255); pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")

        rx, ry = 120, 50
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(75, 6, "Lands:", 0, 1); ry += 6
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C"); pdf.cell(68, 4, safe_encode(r['Card Name']), "B", 1); ry += 4
        
        ry += 10
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(75, 5, "Sideboard:", 0, 1); ry += 6
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4, str(int(r['Side'])), "B", 0, "C"); pdf.cell(68, 4, safe_encode(r['Card Name']), "B", 1); ry += 4
        
        pdf.set_xy(rx, 222); pdf.cell(55, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(ts)), 1, 1, "C")

        # Juges
        pdf.set_xy(120, 235); pdf.set_font("Arial", "B", 7); pdf.cell(75, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(120, 240); pdf.cell(37.5, 10, "Deck Check:", 1); pdf.cell(37.5, 10, "Status:", 1)
        pdf.set_xy(120, 250); pdf.cell(37.5, 10, "Judge:", 1); pdf.cell(37.5, 10, "Main Check:", 1)

        # --- PAGE 2 : INVENTAIRE ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE COMPLET (ANALYSE GEEK)", 0, 1, "C"); pdf.ln(5)
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(220, 220, 220)
        h = ["Main", "Side", "Cut", "Nom de la Carte", "Type", "CMC"]
        w = [10, 10, 10, 75, 65, 15]
        for i, txt in enumerate(h): pdf.cell(w[i], 8, txt, 1, 0, "C", True)
        pdf.ln()
        for i, (_, r) in enumerate(edited_df.iterrows()):
            pdf.set_fill_color(245, 245, 245) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
            pdf.cell(10, 7, str(int(r['Main'])), 1, 0, "C", True)
            pdf.cell(10, 7, str(int(r['Side'])), 1, 0, "C", True)
            pdf.cell(10, 7, str(int(r['Cut'])), 1, 0, "C", True)
            pdf.cell(75, 7, f" {safe_encode(r['Card Name'])}", 1, 0, "L", True)
            pdf.cell(65, 7, f" {safe_encode(r['Type'][:35])}", 1, 0, "L", True)
            pdf.cell(15, 7, str(int(r['CMC'])), 1, 1, "C", True)

        st.download_button("📥 TÉLÉCHARGER LE PDF COMPLET", data=pdf.output(dest='S').encode('latin-1'), file_name="deck_final.pdf")
