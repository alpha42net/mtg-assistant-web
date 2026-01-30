import streamlit as st
import pandas as pd
from fpdf import FPDF
import time

# --- 1. DESTRUCTION RADICALE DU CACHE ---
# On change la clé de version pour forcer Streamlit à tout oublier
V_KEY = "VERSION_PRO_FINAL_FINAL"
if V_KEY not in st.session_state:
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.session_state[V_KEY] = True

st.set_page_config(page_title="MTG Fix 60", layout="wide")

class MTGPDF(FPDF):
    def draw_box(self, x, y, label, val, w):
        self.rect(x, y, w, 8)
        self.set_xy(x, y)
        self.set_font("Arial", "B", 8)
        self.cell(20, 8, f" {label}:", 0)
        self.set_font("Arial", "", 9)
        self.cell(w-20, 8, str(val), 0)

    # Rotation ultra-compatible (plus de AttributeError)
    def draw_name_vertical(self, x, y, text):
        self.set_font("Arial", "B", 10)
        self.rotate(90, x, y)
        self.text(x, y, text)
        self.rotate(0)

def sanitize(txt):
    # Répare l'erreur Unicode (image_9b9a92.png)
    return str(txt).replace('//', '-').encode('ascii', 'ignore').decode('ascii')

# --- UI SIDEBAR ---
with st.sidebar:
    st.header("Joueur")
    nom_v = st.text_input("NOM", "BELEREN").upper()
    pre_v = st.text_input("PRENOM", "Jace")
    event_v = st.text_input("EVENT", "Tournament")
    loc_v = st.text_input("LIEU", "Montreal")

up = st.file_uploader("📂 Chargez votre CSV", type="csv")

if up:
    # On force le calcul à 60 ici pour tuer le "80"
    if 'data_final' not in st.session_state:
        raw = pd.read_csv(up)
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        cards = []
        for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name = str(row[n_col])
            qty = int(row['Quantity'])
            land = any(x in name.lower() for x in ["island", "swamp", "mountain", "forest", "plains", "land"])
            
            # LOGIQUE STRICTE 2-1-1 POUR ARRIVER À 60
            if "basic" in name.lower() or name in ["Island", "Swamp", "Mountain", "Forest", "Plains"]:
                m, s, c = qty, 0, 0
            else:
                m = min(qty, 2)
                s = 1 if qty >= 3 else 0
                c = max(0, qty - 3)
            cards.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, "IsLand": land})
        st.session_state.data_final = pd.DataFrame(cards)

    # Affichage du tableau (clé unique pour éviter le bug d'image_9b30a1)
    df = st.data_editor(st.session_state.data_final, hide_index=True, key="editor_v99")
    
    tm = df['Main'].sum()
    st.write(f"### Total Main Deck : {tm}")

    if st.button("📄 GÉNÉRER PDF COMPLET (P1 + P2)", type="primary"):
        pdf = MTGPDF()
        
        # PAGE 1 : FORMULAIRE
        pdf.add_page()
        pdf.set_font("Arial", "B", 16); pdf.cell(0, 10, "MTG DECKLIST", 0, 1, "C")
        pdf.draw_box(35, 20, "DATE", "30/01/2026", 65)
        pdf.draw_box(100, 20, "LIEU", loc_v, 85)
        pdf.draw_box(35, 28, "EVENT", event_v, 150)

        # NOM VERTICAL SANS CRASH
        pdf.rect(10, 50, 15, 230)
        pdf.draw_name_vertical(18, 160, f"NAME: {nom_v}, {pre_v}")

        # LISTE MAIN
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y = 56
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y); pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C")
            pdf.cell(78, 4, sanitize(r['Card Name']), "B", 1); y += 4
            if y > 250: break

        pdf.set_xy(30, 255); pdf.cell(65, 10, "TOTAL MAIN:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")

        # PAGE 2 : INVENTAIRE
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE COMPLET", 0, 1, "C"); pdf.ln(5)
        pdf.set_font("Arial", "B", 8)
        pdf.cell(10, 8, "M", 1); pdf.cell(10, 8, "S", 1); pdf.cell(10, 8, "C", 1); pdf.cell(120, 8, "Nom", 1, 1)
        pdf.set_font("Arial", "", 8)
        for _, r in df.iterrows():
            pdf.cell(10, 7, str(int(r['Main'])), 1); pdf.cell(10, 7, str(int(r['Side'])), 1)
            pdf.cell(10, 7, str(int(r['Cut'])), 1); pdf.cell(120, 7, sanitize(r['Card Name']), 1, 1)

        st.download_button("📥 TELECHARGER LE PDF", data=pdf.output(dest='S').encode('latin-1'), file_name="deck_60_fix.pdf")
