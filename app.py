import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro")

# --- FONCTION NETTOYAGE TEXTE ---
def clean_pdf_text(text):
    if not isinstance(text, str): return str(text)
    return text.replace('_', ' ').encode('latin-1', 'replace').decode('latin-1')

# --- FONCTION SCRYFALL ---
def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            d = res.json()
            return {"type": d.get("type_line", "Unknown"), "cmc": d.get("cmc", 0)}
    except: pass
    return {"type": "Unknown", "cmc": 0}

# --- BARRE LATÉRALE ---
with st.sidebar:
    st.header("📋 Informations")
    last_n = st.text_input("NOM", value="BELEREN")
    first_n = st.text_input("PRÉNOM", value="Jace")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION", value="")
    event_v = st.text_input("EVENT", value="")
    dname_v = st.text_input("DECK NAME", value="")

# --- LOGIQUE DE FICHIER ---
file = st.file_uploader("📂 Chargez votre CSV MTG", type="csv")

if file:
    # On initialise les données dans la session pour éviter de recharger l'API
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Analyse Scryfall en cours...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                st.write(f"Vérification : {name}")
                sf = get_scryfall_data(name)
                time.sleep(0.05)
                
                is_land = "Land" in sf["type"]
                qty = int(row['Quantity'])
                
                processed.append({
                    "Nom": name, 
                    "Main": qty if is_land else min(qty, 4), 
                    "Side": 0 if is_land else max(0, qty - 4), 
                    "Cut": 0, 
                    "Type": sf["type"], 
                    "CMC": sf["cmc"]
                })
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Analyse terminée !", state="complete")

    if 'master_df' in st.session_state:
        df = st.session_state.master_df
        
        # Affichage des stats
        m_count = df['Main'].sum()
        s_count = df['Side'].sum()
        c1, c2 = st.columns(2)
        c1.metric("MAIN DECK", f"{m_count} / 60")
        c2.metric("SIDEBOARD", f"{s_count} / 15")

        # Éditeur de tableau
        edited_df = st.data_editor(df, hide_index=True, use_container_width=True, key="mtg_editor")
        st.session_state.master_df = edited_df

        # Bouton Génération PDF
        if st.button("📄 GÉNÉRER LE PDF", use_container_width=True, type="primary"):
            pdf = FPDF()
            
            # --- PAGE 1 ---
            pdf.add_page()
            pdf.set_font("Arial", "B", 16)
            pdf.cell(190, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
            
            pdf.set_font("Arial", "", 10)
            pdf.cell(95, 8, f"NOM: {last_n} {first_n}", 1)
            pdf.cell(95, 8, f"DECK: {dname_v}", 1, 1)
            pdf.cell(95, 8, f"EVENT: {event_v}", 1)
            pdf.cell(95, 8, f"DATE: {date_v}", 1, 1)
            pdf.ln(10)
            
            pdf.set_font("Arial", "B", 12)
            pdf.cell(190, 8, "LISTE DES CARTES", 1, 1, "C", fill=False)
            
            pdf.set_font("Arial", "", 9)
            for _, r in edited_df.iterrows():
                if r['Main'] > 0:
                    pdf.cell(10, 6, str(r['Main']), 1, 0, "C")
                    pdf.cell(180, 6, clean_pdf_text(r['Nom']), 1, 1)

            # --- PAGE 2 ---
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(190, 10, "INVENTAIRE GEEK COMPLET", 0, 1, "C")
            pdf.ln(5)
            
            pdf.set_font("Arial", "B", 8)
            cols = [10, 10, 10, 80, 70, 10]
            headers = ["M", "S", "C", "Nom", "Type", "CMC"]
            for i, h in enumerate(headers): pdf.cell(cols[i], 7, h, 1, 0, "C")
            pdf.ln()
            
            pdf.set_font("Arial", "", 7)
            for i, row in edited_df.iterrows():
                pdf.cell(10, 5, str(row['Main']), 1, 0, "C")
                pdf.cell(10, 5, str(row['Side']), 1, 0, "C")
                pdf.cell(10, 5, str(row['Cut']), 1, 0, "C")
                pdf.cell(80, 5, clean_pdf_text(row['Nom']), 1, 0, "L")
                pdf.cell(70, 5, clean_pdf_text(row['Type']), 1, 0, "L")
                pdf.cell(10, 5, str(row['CMC']), 1, 1, "C")

            pdf_out = pdf.output(dest='S').encode('latin-1')
            st.download_button("📥 TÉLÉCHARGER LE PDF", data=pdf_out, file_name="decklist.pdf", mime="application/pdf")
