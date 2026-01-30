import streamlit as st
import pandas as pd
from fpdf import FPDF
import time

# 1. FORCE LE NETTOYAGE DU CACHE AU DÉMARRAGE
if 'check_vfinal' not in st.session_state:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state['check_vfinal'] = True

st.set_page_config(page_title="MTG Assistant 60", layout="wide")

class MTGPDF(FPDF):
    def header_box(self, x, y, label, val, w):
        self.rect(x, y, w, 8)
        self.set_xy(x, y)
        self.set_font("Arial", "B", 8)
        self.cell(20, 8, f" {label}:", 0)
        self.set_font("Arial", "", 9)
        self.cell(w-20, 8, str(val), 0)

    # Rotation basique manuelle (plus d'AttributeError)
    def v_name(self, x, y, txt):
        self.set_font("Arial", "B", 10)
        self.rotate(90, x, y)
        self.text(x, y, txt)
        self.rotate(0)

def clean_txt(t):
    # Tue les erreurs Unicode (image_9b9a92.png)
    return str(t).replace('//', '-').encode('ascii', 'ignore').decode('ascii')

# --- UI ---
with st.sidebar:
    nom = st.text_input("NOM", "BELEREN").upper()
    pre = st.text_input("PRÉNOM", "Jace")
    even = st.text_input("EVENT", "Tournament")
    loc = st.text_input("LIEU", "Montreal")
    date = st.text_input("DATE", "30/01/2026")

up = st.file_uploader("📂 Chargez le CSV", type="csv")

if up:
    # On force une nouvelle clé pour tuer le "80" (image_9b34de.png)
    if 'data_60_fix' not in st.session_state:
        raw = pd.read_csv(up)
        # Nettoyage colonnes
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        cards = []
        for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name = str(row[n_col])
            qty = int(row['Quantity'])
            land = any(x in name.lower() for x in ["island", "swamp", "mountain", "forest", "plains", "land"])
            
            # LOGIQUE 60 CARTES FORCÉE
            if "basic" in name.lower() or name in ["Island", "Swamp", "Mountain", "Forest", "Plains"]:
                m, s, c = qty, 0, 0
            else:
                m = min(qty, 2)
                s = 1 if qty >= 3 else 0
                c = max(0, qty - 3)
            cards.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": land})
        st.session_state.data_60_fix = pd.DataFrame(cards)

    df = st.data_editor(st.session_state.data_60_fix, hide_index=True, key="edit_vFinal")
    tm, ts = df['Main'].sum(), df['Side'].sum()
    st.info(f"Vérification : {tm} cartes en Main / {ts} en Side")

    if st.button("📄 GÉNÉRER PDF (P1 + P2)", type="primary", use_container_width=True):
        pdf = MTGPDF()
        
        # --- PAGE 1 ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "MTG DECKLIST OFFICIAL", 0, 1, "C")
        pdf.header_box(35, 20, "DATE", date, 65)
        pdf.header_box(100, 20, "LIEU", loc, 85)
        pdf.header_box(35, 28, "EVENT", even, 150)
        
        # NOM VERTICAL (FIXÉ)
        pdf.rect(10, 50, 15, 230)
        pdf.v_name(18, 160, f"NAME: {nom}, {pre}")

        # MAIN DECK
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y = 56
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y); pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(78, 4, clean_txt(r['Card Name']), "B", 1); y += 4
        
        # LANDS & SIDE
        rx, ry = 120, 50
        pdf.set_xy(rx, ry); pdf.cell(75, 6, "Lands:", 0, 1); ry += 6
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(68, 4, clean_txt(r['Card Name']), "B", 1); ry += 4
        
        ry += 10
        pdf.set_xy(rx, ry); pdf.cell(75, 6, "Sideboard:", 0, 1); ry += 6
        for _, r in df[df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 4, str(int(r['Side'])), "B", 0, "C")
            pdf.cell(68, 4, clean_txt(r['Card Name']), "B", 1); ry += 4

        pdf.set_xy(30, 255); pdf.cell(65, 10, "TOTAL MAIN:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")

        # --- PAGE 2 : INVENTAIRE ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE COMPLET", 0, 1, "C"); pdf.ln(5)
        pdf.set_font("Arial", "B", 8)
        pdf.cell(10, 8, "M", 1); pdf.cell(10, 8, "S", 1); pdf.cell(10, 8, "C", 1); pdf.cell(100, 8, "Card Name", 1, 1)
        pdf.set_font("Arial", "", 8)
        for _, r in df.iterrows():
            pdf.cell(10, 7, str(int(r['Main'])), 1); pdf.cell(10, 7, str(int(r['Side'])), 1)
            pdf.cell(10, 7, str(int(r['Cut'])), 1); pdf.cell(100, 7, clean_txt(r['Card Name']), 1, 1)

        st.download_button("📥 TÉLÉCHARGER LE PDF RÉPARÉ", data=pdf.output(dest='S').encode('latin-1'), file_name="deck_final_60.pdf")
