import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# Mode large obligatoire pour voir toutes les colonnes
st.set_page_config(page_title="MTG Full View", layout="wide")

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
    return text.replace('//', '-').encode('ascii', 'ignore').decode('ascii')

def get_scryfall_info(name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={name.strip()}"
        res = requests.get(url, timeout=1).json()
        tl = res.get("type_line", "Unknown")
        return {"land": "Land" in tl, "type": tl, "cmc": res.get("cmc", 0)}
    except: return {"land": False, "type": "Unknown", "cmc": 0}

# --- BARRE LATERALE ---
with st.sidebar:
    st.header("Identification")
    nom = st.text_input("LAST NAME", "BELEREN").upper()
    pre = st.text_input("FIRST NAME", "Jace")
    event = st.text_input("EVENT", "Tournament")
    loc = st.text_input("LOCATION", "Montreal")
    dname = st.text_input("DECK NAME", "My Deck")
    st.divider()
    if st.button("🚨 FORCE RESET (V100)"):
        st.session_state.clear()
        st.rerun()

st.title("🎴 Vue Intégrale (100 cartes sans défilement)")

up = st.file_uploader("📂 Importez votre CSV", type="csv")

if up:
    if 'full_view_df' not in st.session_state:
        raw = pd.read_csv(up)
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        data = []
        with st.spinner('Chargement des 100 cartes...'):
            for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
                name = str(row[n_col])
                info = get_scryfall_info(name)
                qty = int(row['Quantity'])
                m = min(qty, 2) if not info["land"] else qty
                s = 1 if (qty >= 3 and not info["land"]) else 0
                c = max(0, qty - (m+s))
                data.append({"Nom": name, "Main": m, "Side": s, "Cut": c, "Mana": info["cmc"], "Category": info["type"], "IsLand": info["land"]})
        st.session_state.full_view_df = pd.DataFrame(data).sort_values(["IsLand", "Nom"])

    # --- LE TABLEAU GEANT ---
    # height=None ou une valeur très haute (4000) force l'affichage de toutes les lignes
    edited_df = st.data_editor(
        st.session_state.full_view_df,
        column_config={
            "Main": st.column_config.NumberColumn(width="small"),
            "Side": st.column_config.NumberColumn(width="small"),
            "Cut": st.column_config.NumberColumn(width="small"),
            "Mana": st.column_config.NumberColumn(disabled=True),
            "Category": st.column_config.TextColumn(width="large", disabled=True),
        },
        hide_index=True, 
        use_container_width=True, 
        height=4000  # C'est ici qu'on force l'affichage total
    )

    tm, ts = edited_df['Main'].sum(), edited_df['Side'].sum()
    st.divider()
    st.info(f"Vérification finale : {tm} Main / {ts} Side")

    if st.button("📄 GENERER LE PDF OFFICIEL", type="primary", use_container_width=True):
        pdf = MTGPDF()
        pdf.add_page()
        # Formulaire P1
        pdf.set_font("Arial", "B", 18); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.draw_header_box(35, 20, "DATE", time.strftime("%d/%m/%Y"), 65)
        pdf.draw_header_box(100, 20, "LOCATION", loc, 85)
        pdf.draw_header_box(35, 28, "EVENT", event, 150)
        pdf.draw_header_box(35, 36, "DECK NAME", dname, 150)
        pdf.rect(10, 50, 15, 230)
        pdf.vertical_name_safe(18, 160, f"NAME: {nom}, {pre}")

        # Listes
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y_m = 56
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y_m); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 3.8, str(int(r['Main'])), "B", 0, "C"); pdf.cell(78, 3.8, safe_encode(r['Nom']), "B", 1); y_m += 3.8
        
        rx, ry = 120, 50
        pdf.set_xy(rx, ry); pdf.cell(75, 6, "Lands:", 0, 1); ry += 6
        for _, r in edited_df[(edited_df['Main'] > 0) & (edited_df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 3.8, str(int(r['Main'])), "B", 0, "C"); pdf.cell(68, 3.8, safe_encode(r['Nom']), "B", 1); ry += 3.8
        
        ry += 8
        pdf.set_xy(rx, ry); pdf.cell(75, 5, "Sideboard:", 0, 1); ry += 6
        for _, r in edited_df[edited_df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 3.8, str(int(r['Side'])), "B", 0, "C"); pdf.cell(68, 3.8, safe_encode(r['Nom']), "B", 1); ry += 3.8

        # Pied de page officiel
        pdf.set_xy(30, 255); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")
        pdf.set_xy(120, 222); pdf.cell(55, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(ts)), 1, 1, "C")
        pdf.set_xy(120, 235); pdf.set_font("Arial", "B", 7); pdf.cell(75, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(120, 240); pdf.cell(37.5, 10, "Deck Check:", 1); pdf.cell(37.5, 10, "Status:", 1)
        pdf.set_xy(120, 250); pdf.cell(37.5, 10, "Judge:", 1); pdf.cell(37.5, 10, "Main Check:", 1)

        # Page 2
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE COMPLET", 0, 1, "C"); pdf.ln(5)
        pdf.set_font("Arial", "B", 8)
        for h in ["M", "S", "C", "Card Name", "Mana", "Category"]: pdf.cell(30, 8, h, 1)
        pdf.ln()
        pdf.set_font("Arial", "", 8)
        for _, r in edited_df.iterrows():
            pdf.cell(10, 6, str(int(r['Main'])), 1); pdf.cell(10, 6, str(int(r['Side'])), 1)
            pdf.cell(10, 6, str(int(r['Cut'])), 1); pdf.cell(75, 6, safe_encode(r['Nom']), 1)
            pdf.cell(15, 6, str(int(r['Mana'])), 1); pdf.cell(70, 6, safe_encode(r['Category'][:40]), 1, 1)

        st.download_button("📥 TELECHARGER LE PDF COMPLET", data=pdf.output(dest='S').encode('latin-1'), file_name="deck_final.pdf")
