import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MTG Assistant Web", layout="wide")
st.title("🎴 MTG Decklist & Geek Analytics")

def clean_pdf_text(text):
    if not isinstance(text, str): return str(text)
    return text.replace('_', ' ').encode('latin-1', 'replace').decode('latin-1')

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        response = requests.get(url, timeout=5)
        if response.status_code == 200:
            data = response.json()
            return {"type": data.get("type_line", "Unknown"), "cmc": data.get("cmc", 0)}
    except: pass
    return {"type": "Unknown", "cmc": 0}

# --- FORMULAIRE INFOS ---
with st.sidebar:
    st.header("Infos Tournoi")
    nom = st.text_input("NOM")
    prenom = st.text_input("PRÉNOM")
    date = st.text_input("DATE")
    loc = st.text_input("LOCATION")
    event = st.text_input("EVENT")
    dname = st.text_input("DECK NAME")

uploaded_file = st.file_uploader("Charge ton CSV MTG", type="csv")

if uploaded_file:
    df_raw = pd.read_csv(uploaded_file)
    df_raw.columns = [c.strip() for c in df_raw.columns]
    col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
    
    df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
    processed_data = []
    
    # Analyse
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    for i, (_, r) in enumerate(df_g.sort_values(by=col_name).iterrows()):
        name = str(r[col_name])
        status_text.text(f"Analyse Scryfall : {name}")
        progress_bar.progress((i + 1) / len(df_g))
        
        sf = get_scryfall_data(name)
        time.sleep(0.05)
        
        m = min(int(r['Quantity']), 4) # Logique simplifiée pour l'exemple
        s = int(r['Quantity']) - m
        processed_data.append({"Nom": name, "Total": int(r['Quantity']), "Main": m, "Side": s, "Type": sf["type"], "CMC": sf["cmc"]})

    # Affichage Tableau Editable
    st.subheader("Édition des quantités")
    edited_df = st.data_editor(pd.DataFrame(processed_data), num_rows="dynamic")

    if st.button("Générer le PDF"):
        # Ici on insère ta logique FPDF (la même que ton script)
        # Sauf qu'à la fin, on utilise st.download_button
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, f"DECKLIST: {dname}", 0, 1, "C")
        # ... (ajouter le reste de ton design PDF ici) ...
        
        pdf_output = pdf.output(dest='S').encode('latin-1')
        st.download_button("⬇️ Télécharger le PDF", data=pdf_output, file_name="decklist.pdf", mime="application/pdf")