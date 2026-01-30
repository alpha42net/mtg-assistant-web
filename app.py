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

    # Nouvelle méthode de rotation simplifiée pour éviter le plantage
    def vertical_text_fixed(self, x, y, text):
        self.set_font("Arial", "B", 10)
        self.rotate(90, x, y)
        self.text(x, y, text)
        self.rotate(0)

def safe_encode(text):
    if not isinstance(text, str): return str(text)
    # Nettoyage profond pour éviter l'erreur Unicode
    return text.replace('//', '/').encode('ascii', 'ignore').decode('ascii')

def get_scryfall(name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={name.strip()}"
        res = requests.get(url, timeout=2).json()
        tl = res.get("type_line", "")
        return {"land": "Land" in tl, "basic": "Basic" in tl, "type": tl, "cmc": res.get("cmc", 0)}
    except: return {"land": False, "basic": False, "type": "Unknown", "cmc": 0}

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("Infos Decklist")
    last_n = st.text_input("NOM", "BELEREN").upper()
    first_n = st.text_input("PRÉNOM", "Jace")
    event_v = st.text_input("ÉVÉNEMENT", "Tournament")
    loc_v = st.text_input("LIEU", "Montreal")
    date_v = st.text_input("DATE", time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("NOM DU DECK", "My Deck")
    
    # BOUTON DE SECOURS : Force le nettoyage complet sans perdre le fichier
    if st.button("🚨 RÉINITIALISER LE COMPTEUR À 60"):
        if 'master_data_v100' in st.session_state:
            del st.session_state['master_data_v100']
        st.rerun()

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    # On utilise un nom de clé (v100) jamais utilisé auparavant
    if 'master_data_v100' not in st.session_state:
        raw = pd.read_csv(file)
        raw.columns = [c.strip() for c in raw.columns]
        n_col = "Card Name" if "Card Name" in raw.columns else raw.columns[0]
        
        data = []
        for _, row in raw.groupby(n_col).agg({'Quantity': 'sum'}).reset_index().iterrows():
            name = str(row[n_col])
            info = get_scryfall(name)
            total = int(row['Quantity'])
            
            # --- LOGIQUE DE RÉDUCTION STRICTE ---
            if info["basic"]: 
                m, s, c = total, 0, 0
            else:
                m = min(total, 2)
                s = 1 if total >= 3 else 0
                c = max(0, total - 3)
            
            data.append({"Card Name": name, "Main": m, "Side": s, "Cut": c, 
                         "IsLand": info["land"], "Type": info["type"], "CMC": info["cmc"]})
        st.session_state.master_data_v100 = pd.DataFrame(data).sort_values("Card Name")

    # Éditeur de données avec une clé fixe
    df = st.data_editor(st.session_state.master_data_v100, hide_index=True, use_container_width=True, key="editor_v100")
    
    tm, ts = df['Main'].sum(), df['Side'].sum()
    st.subheader(f"Statut : {tm} cartes en Main / {ts} en Side")

    if st.button("📄 GÉNÉRER PDF (P1 + P2)", use_container_width=True, type="primary"):
        pdf = MTGPDF()
        
        # --- PAGE 1 : FORMULAIRE ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 18); pdf.cell(0, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        pdf.draw_header_box(35, 20, "DATE", date_v, 65)
        pdf.draw_header_box(100, 20, "LIEU", loc_v, 85)
        pdf.draw_header_box(35, 28, "ÉVÉNEMENT", event_v, 150)
        pdf.draw_header_box(35, 36, "DECK", dname_v, 150)

        # NOM VERTICAL
        pdf.rect(10, 50, 15, 230)
        pdf.vertical_text_fixed(18, 160, f"NOM: {last_n}, {first_n}")

        # LISTES
        pdf.set_xy(30, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck:", 0, 1)
        y_m = 56
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == False)].iterrows():
            pdf.set_xy(30, y_m); pdf.set_font("Arial", "", 8)
            pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C"); pdf.cell(78, 4, safe_encode(r['Card Name']), "B", 1); y_m += 4
        
        rx, ry = 120, 50
        pdf.set_xy(rx, ry); pdf.cell(75, 6, "Terrains:", 0, 1); ry += 6
        for _, r in df[(df['Main'] > 0) & (df['IsLand'] == True)].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 4, str(int(r['Main'])), "B", 0, "C"); pdf.cell(68, 4, safe_encode(r['Card Name']), "B", 1); ry += 4
        
        ry += 10
        pdf.set_xy(rx, ry); pdf.cell(75, 5, "Sideboard:", 0, 1); ry += 6
        for _, r in df[df['Side'] > 0].iterrows():
            pdf.set_xy(rx, ry); pdf.cell(7, 4, str(int(r['Side'])), "B", 0, "C"); pdf.cell(68, 4, safe_encode(r['Card Name']), "B", 1); ry += 4

        # TOTAUX & JUGES
        pdf.set_xy(30, 255); pdf.set_font("Arial", "B", 10)
        pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(int(tm)), 1, 1, "C")
        pdf.set_xy(120, 222); pdf.cell(55, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(int(ts)), 1, 1, "C")
        pdf.set_xy(120, 235); pdf.set_font("Arial", "B", 7); pdf.cell(75, 5, "RESERVÉ AUX JUGES", 1, 1, "C")
        pdf.set_xy(120, 240); pdf.cell(37.5, 10, "Check:", 1); pdf.cell(37.5, 10, "Status:", 1)

        # --- PAGE 2 : INVENTAIRE ---
        pdf.add_page()
        pdf.set_font("Arial", "B", 14); pdf.cell(0, 10, "INVENTAIRE COMPLET", 0, 1, "C"); pdf.ln(5)
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(230, 230, 230)
        h = ["Main", "Side", "Cut", "Carte", "Type", "CMC"]
        w = [10, 10, 10, 75, 70, 15]
        for i, txt in enumerate(h): pdf.cell(w[i], 8, txt, 1, 0, "C", True)
        pdf.ln()
        for _, r in df.iterrows():
            pdf.cell(10, 7, str(int(r['Main'])), 1)
            pdf.cell(10, 7, str(int(r['Side'])), 1)
            pdf.cell(10, 7, str(int(r['Cut'])), 1)
            pdf.cell(75, 7, f" {safe_encode(r['Card Name'])}", 1)
            pdf.cell(70, 7, f" {safe_encode(r['Type'][:40])}", 1)
            pdf.cell(15, 7, str(int(r['CMC'])), 1, 1)

        st.download_button("📥 TÉLÉCHARGER LE PDF 60 CARTES", data=pdf.output(dest='S').encode('latin-1'), file_name="deck_final.pdf")
