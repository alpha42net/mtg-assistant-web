import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Web Edition")

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            d = res.json()
            type_line = d.get("type_line", "")
            return {
                "type": type_line, 
                "cmc": d.get("cmc", 0),
                "is_basic": "Basic Land" in type_line
            }
    except: pass
    return {"type": "Unknown", "cmc": 0, "is_basic": False}

# --- SIDEBAR ---
with st.sidebar:
    st.header("📋 Infos Decklist")
    last_n = st.text_input("NOM", value="BELEREN")
    first_n = st.text_input("PRÉNOM", value="Jace")
    dname_v = st.text_input("DECK NAME", value="Mon Deck")

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Répartition intelligente...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                total_qty = int(row['Quantity'])
                
                # --- LOGIQUE DE RÉPARTITION RÉPARÉE ---
                if sf["is_basic"]:
                    # Terrains de base : Tout va dans le Main par défaut
                    m, s, c = total_qty, 0, 0
                else:
                    # Sorts : 4 Main, le reste en Sideboard (ou Cut si Sideboard plein)
                    m = min(total_qty, 4)
                    reste = total_qty - m
                    s = reste # On met le reste en Sideboard par défaut
                    c = 0     # L'utilisateur déplacera vers Cut manuellement
                
                processed.append({
                    "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                    "Total": total_qty, "Type": sf["type"], "CMC": sf["cmc"]
                })
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Chargement terminé !", state="complete")

    # --- ÉDITEUR INTERACTIF ---
    # Ici, edited_df contient les valeurs MODIFIÉES par l'utilisateur
    edited_df = st.data_editor(
        st.session_state.master_df,
        hide_index=True,
        use_container_width=True,
        key="editor_key"
    )

    # --- CALCULS EN TEMPS RÉEL ---
    # On force la mise à jour des totaux basés sur l'édition
    m_total = edited_df['Main'].sum()
    s_total = edited_df['Side'].sum()
    c_total = edited_df['Cut'].sum()
    
    # Mise à jour du Total par ligne pour la cohérence
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']

    st.divider()
    col1, col2, col3 = st.columns(3)
    
    # Affichage des compteurs avec delta (rouge si trop de cartes)
    col1.metric("MAIN DECK", f"{m_total} / 60", delta=int(m_total-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_total} / 15", delta=int(s_total-15), delta_color="inverse")
    col3.metric("TOTAL CUT", c_total)

    if st.button("📄 GÉNÉRER LE PDF TOURNAMENT", use_container_width=True, type="primary"):
        # Le bouton utilisera edited_df qui contient tes modifications
        st.write("Génération du PDF avec", m_total, "cartes en Main...")
        # ... (Logique PDF)
