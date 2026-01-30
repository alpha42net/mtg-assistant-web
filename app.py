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

def safe_encode(text):
    """Nettoie les noms de cartes pour le PDF (ex: Trystan // Trystan)"""
    if not isinstance(text, str): return str(text)
    return text.replace('//', '/').encode('latin-1', 'replace').decode('latin-1')

def get_scryfall(name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={name.strip()}"
        res = requests.get(url, timeout=3).json()
        tl = res.get("type_line", "")
        return {"type": tl, "land": "Land" in tl, "basic": "Basic" in tl}
    except: return {"type": "Unknown", "land": False, "basic": False}

# --- SIDEBAR ---
with st.sidebar:
    st.header("Registration")
    last_n = st.text_input("LAST NAME", "BELEREN").upper()
    first_n = st.text_input("FIRST NAME", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", "My Deck")
    
    if st.button("🚨 FORCER LE RECALCUL (FIX 80)"):
        st.session_state.clear()
        st.rerun()

file = st.file_uploader("📂 Importez votre CSV", type="csv")

if file:
    # Création d'une clé unique basée sur le fichier pour briser le cache
    file_id = f"editor_{file.name}_{file.size}"
    
    if 'master_df' not in st.session_state:
        raw = pd.read_csv(file)
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        data = []
        for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name = str(row[n_col])
            info = get_scryfall(name)
            qty = int(row['Quantity'])
            
            # LOGIQUE 2-1-1 STRICTE POUR ARRIVER À 60
            m = qty if info["basic"] else min(qty, 2)
            s = 0 if info["basic"] else (1 if qty > 2 else 0)
            c = 0 if info["basic"] else (max(0, qty - 3))
            
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": info["land"]})
        st.session_state.master_df = pd.DataFrame(data).sort_values("Card Name")

    # On utilise la clé dynamique 'file_id' pour que Streamlit oublie le "80"
    edited_df = st.data_editor(st.session_state.master_df, hide_index=True, use_container_width=True, key=file_id)
    
    tm, ts = edited_df['Main'].sum(), edited_df['Side'].sum()
    st.metric("VÉRIFICATION MAIN DECK", f"{tm} / 60", delta=tm-60, delta_color="inverse")

    if st.button("📄 GÉNÉRER PDF COMPLET", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        pdf.add_page()
        
        # 1. EN-TÊTES
        pdf.set_font("Arial", "B", 18); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.draw_header_box(35, 20, "DATE", date_v, 65)
        pdf.draw_header_box(100, 20, "LOCATION", loc_v, 85)
        pdf.draw_header_box(35, 28, "EVENT", event_v, 150)
        pdf.draw_header_box(35, 36, "DECK", dname_v, 150)

        # 2. NOM VERTICAL (Version stable sans rotation)
        pdf.rect(10, 50, 15, 230)
        pdf.set_font("Courier", "B", 11)
        name_str = f"NAME: {last_n}, {first_n}"
        y_n = 60
        for char in name_str:
            pdf.text(15, y_n, char)
            y_n += 5

        # 3. MAIN DECK (Gauche)
        pdf.set_xy(28, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y_m = 56
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)].iterrows():
            pdf.set_xy(28, y_m); pdf.set_font("Arial", "", 7.5)
            pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(78, 4, safe_encode(r['Card Name']), "B", 1)
            y_m += 4
        
        pdf.set_xy(28, 255); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")

        # 4. LANDS & SIDEBOARD (Droite)
        rx, ry = 118, 50
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Lands:", 0, 1); ry += 6
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 7.5)
            pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(75, 4, safe_encode(r['Card Name']), "B", 1); ry += 4
        
        ry += 8
        pdf.set_xy(rx, ry); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Sideboard:", 0, 1); ry += 6
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.set_font("Arial", "", 7.5)
            pdf.cell(7, 4, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(75, 4, safe_encode(r['Card Name']), "B", 1); ry += 4
        
        pdf.set_xy(rx, 220); pdf.set_font("Arial", "B", 9)
        pdf.cell(62, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(ts)), 1, 1, "C")

        # 5. TABLEAU JUGES (Remis en bas à droite)
        pdf.set_xy(118, 235); pdf.set_font("Arial", "B", 7); pdf.cell(82, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(118, 240); pdf.cell(41, 10, "Deck Check:", 1); pdf.cell(41, 10, "Status:", 1)
        pdf.set_xy(118, 250); pdf.cell(41, 10, "Judge:", 1); pdf.cell(41, 10, "Main Check:", 1)

        st.download_button("📥 TÉLÉCHARGER LE PDF RÉPARÉ", data=pdf.output(dest='S').encode('latin-1'), file_name="decklist_mtg.pdf")
