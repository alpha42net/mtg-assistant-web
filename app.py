import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

st.set_page_config(page_title="MTG Assistant Final", layout="wide")

class MTGPDF(FPDF):
    def draw_header_box(self, x, y, label, value, w, h=8):
        self.rect(x, y, w, h)
        self.set_xy(x, y)
        self.set_font("Arial", "B", 8)
        self.cell(20, h, f" {label}:", 0)
        self.set_font("Arial", "", 9)
        self.cell(w-20, h, str(value), 0)

    # Méthode de rotation ultra-stable (compatible toutes versions)
    def vertical_text_stable(self, x, y, text):
        self.set_font("Arial", "B", 10)
        self.rotate(90, x, y)
        self.text(x, y, text)
        self.rotate(0)

def safe_encode(text):
    if not isinstance(text, str): return str(text)
    return text.replace('//', '/').encode('latin-1', 'replace').decode('latin-1')

# --- LOGIQUE DE FILTRAGE ---
def get_card_data(file):
    raw = pd.read_csv(file)
    raw.columns = [c.strip() for c in raw.columns]
    n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
    
    data = []
    for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
        name = str(row[n_col])
        qty = int(row['Quantity'])
        
        # Simulation API rapide pour land/type
        is_land = "Land" in name or "Island" in name or "Swamp" in name or "Mountain" in name or "Forest" in name or "Plains" in name
        is_basic = name in ["Island", "Swamp", "Mountain", "Forest", "Plains"]
        
        # FORÇAGE MATHÉMATIQUE DU 60 (2-1-1)
        if is_basic: 
            m, s, c = qty, 0, 0
        else:
            m = min(qty, 2)
            s = 1 if qty >= 3 else 0
            c = max(0, qty - 3)
            
        data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": is_land})
    return pd.DataFrame(data)

# --- INTERFACE ---
with st.sidebar:
    st.header("Infos Joueur")
    last_n = st.text_input("NOM", "BELEREN").upper()
    first_n = st.text_input("PRÉNOM", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LOCATION", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))

uploaded_file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if uploaded_file:
    # Utilisation d'un cache spécifique pour tuer le "80"
    if 'deck_data' not in st.session_state:
        st.session_state.deck_data = get_card_data(uploaded_file)
    
    # ÉDITEUR (Clé unique pour forcer le rafraîchissement)
    df = st.data_editor(st.session_state.deck_data, hide_index=True, use_container_width=True, key="editor_final_v1")
    
    total_m = df['Main'].sum()
    st.metric("TOTAL MAIN DECK", f"{total_m} / 60", delta=int(total_m-60), delta_color="inverse")

    if st.button("📄 GÉNÉRER LE PDF (P1 + P2)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        
        # --- PAGE 1 ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.draw_header_box(35, 20, "DATE", date_v, 65)
        pdf.draw_header_box(100, 20, "LOCATION", loc_v, 85)
        pdf.draw_header_box(35, 28, "EVENT", event_v, 150)
        
        # NOM VERTICAL (FIXÉ)
        pdf.rect(10, 50, 15, 230)
        pdf.vertical_text_stable(19, 160, f"NAME: {last_n}, {first_n}")

        # Liste Main Deck
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        curr_y = 56
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, curr_y); pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(78, 4, safe_encode(r['Card Name']), "B", 1); curr_y += 4

        # Lands & Side (Droite)
        rx, ry = 120, 50
        pdf.set_xy(rx, ry); pdf.cell(75, 6, "Lands:", 0, 1); ry += 6
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(68, 4, safe_encode(r['Card Name']), "B", 1); ry += 4
        
        ry += 10
        pdf.set_xy(rx, ry); pdf.cell(75, 6, "Sideboard:", 0, 1); ry += 6
        for _, r in df[df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 4, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(68, 4, safe_encode(r['Card Name']), "B", 1); ry += 4

        # TOTAL ET JUGES
        pdf.set_xy(30, 255); pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(total_m)), 1, 1, "C")
        pdf.set_xy(120, 235); pdf.set_font("Arial", "B", 7); pdf.cell(75, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(120, 240); pdf.cell(37.5, 10, "Deck Check:", 1); pdf.cell(37.5, 10, "Status:", 1)

        # --- PAGE 2 : INVENTAIRE ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE COMPLET", 0, 1, "C")
        pdf.set_font("Arial", "B", 8)
        cols = ["Main", "Side", "Cut", "Card Name"]
        for c in cols: pdf.cell(40, 8, c, 1, 0, "C")
        pdf.ln()
        pdf.set_font("Arial", "", 8)
        for _, r in df.iterrows():
            pdf.cell(40, 7, str(int(r['Main'])), 1)
            pdf.cell(40, 7, str(int(r['Side'])), 1)
            pdf.cell(40, 7, str(int(r['Cut'])), 1)
            pdf.cell(40, 7, safe_encode(r['Card Name']), 1, 1)

        st.download_button("📥 TÉLÉCHARGER LE PDF RÉPARÉ", data=pdf.output(dest='S').encode('latin-1'), file_name="decklist_60.pdf")
