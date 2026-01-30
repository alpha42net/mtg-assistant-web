import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

st.set_page_config(page_title="MTG Assistant Pro", layout="wide")

class MTGPDF(FPDF):
    def draw_header_box(self, x, y, label, value, w, h=8):
        self.rect(x, y, w, h)
        self.set_xy(x, y)
        self.set_font("Arial", "B", 8)
        self.cell(20, h, f" {label}:", 0)
        self.set_font("Arial", "", 9)
        self.cell(w-20, h, str(value), 0)

    def rotated_text(self, x, y, text):
        with self.rotation(90, x, y):
            self.set_font("Arial", "B", 11)
            self.text(x, y, text)

def safe_encode(text):
    if not isinstance(text, str): return str(text)
    return text.replace('//', '/').encode('latin-1', 'replace').decode('latin-1')

def get_scryfall(name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={name.strip()}"
        res = requests.get(url, timeout=3).json()
        tl = res.get("type_line", "")
        return {"land": "Land" in tl, "basic": "Basic" in tl}
    except: return {"land": False, "basic": False}

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("Registration")
    last_n = st.text_input("NOM (Famille)", "BELEREN").upper()
    first_n = st.text_input("PRÉNOM", "Jace")
    event_v = st.text_input("ÉVÉNEMENT", "Tournament")
    loc_v = st.text_input("LIEU", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("NOM DU DECK", "My Deck")
    
    if st.button("🚨 FORCER LE PASSAGE À 60 CARTES"):
        st.session_state.clear()
        st.rerun()

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

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
            
            # --- LOGIQUE DE RETRAIT AUTOMATIQUE (2-1-1) ---
            # Si c'est un terrain de base, on garde tout.
            # Sinon, on limite à 2 en Main, 1 en Side, le reste en Cut.
            m = qty if info["basic"] else min(qty, 2)
            s = 0 if info["basic"] else (1 if qty >= 3 else 0)
            c = 0 if info["basic"] else (max(0, qty - 3))
            
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": info["land"]})
        st.session_state.master_df = pd.DataFrame(data).sort_values("Card Name")

    # ÉDITEUR (On utilise une clé unique pour tuer le cache du 80)
    edited_df = st.data_editor(st.session_state.master_df, hide_index=True, use_container_width=True, key="mtg_force_60")
    
    tm, ts = edited_df['Main'].sum(), edited_df['Side'].sum()
    
    # Message d'alerte si le total est incorrect
    if tm != 60:
        st.error(f"Attention : Vous avez {tm} cartes. Le deck doit en avoir exactement 60.")
    else:
        st.success("Parfait : 60 cartes détectées.")

    if st.button("📄 GÉNÉRER PDF (VERSION FINALE)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        pdf.add_page()
        
        # 1. EN-TÊTES
        pdf.set_font("Arial", "B", 18); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.draw_header_box(35, 20, "DATE", date_v, 65)
        pdf.draw_header_box(100, 20, "LIEU", loc_v, 85)
        pdf.draw_header_box(35, 28, "ÉVÉNEMENT", event_v, 150)
        pdf.draw_header_box(35, 36, "DECK", dname_v, 150)

        # 2. NOM VERTICAL (Retourné à 90°)
        pdf.rect(10, 50, 15, 230)
        pdf.rotated_text(18, 160, f"NOM: {last_n}, {first_n}")

        # 3. MAIN DECK (Gauche)
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y_m = 56
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y_m); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4.2, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(78, 4.2, safe_encode(r['Card Name']), "B", 1)
            y_m += 4.2
        
        pdf.set_xy(30, 255); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")

        # 4. LANDS & SIDEBOARD (Ajusté pour ne pas disparaître)
        rx, ry = 120, 50
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(75, 6, "Terrains:", 0, 1); ry += 6
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4.2, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(68, 4.2, safe_encode(r['Card Name']), "B", 1); ry += 4.2
        
        ry += 8
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(75, 6, "Sideboard:", 0, 1); ry += 6
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4.2, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(68, 4.2, safe_encode(r['Card Name']), "B", 1); ry += 4.2
        
        # 5. TOTAL SIDEBOARD ET JUGES
        pdf.set_xy(rx, 222); pdf.set_font("Arial", "B", 9)
        pdf.cell(55, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(ts)), 1, 1, "C")

        pdf.set_xy(120, 235); pdf.set_font("Arial", "B", 7); pdf.cell(75, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(120, 240); pdf.cell(37.5, 10, "Deck Check:", 1); pdf.cell(37.5, 10, "Status:", 1)
        pdf.set_xy(120, 250); pdf.cell(37.5, 10, "Judge:", 1); pdf.cell(37.5, 10, "Main Check:", 1)

        st.download_button("📥 TÉLÉCHARGER LE PDF 60 CARTES", data=pdf.output(dest='S').encode('latin-1'), file_name="decklist_final.pdf")
