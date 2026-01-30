import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Web Edition")

def get_scryfall_data(card_name):
    try:
        url = f"https://api.scryfall.com/cards/named?exact={card_name.strip()}"
        res = requests.get(url, timeout=4)
        if res.status_code == 200:
            d = res.json()
            return {"type": d.get("type_line", "Unknown"), "cmc": d.get("cmc", 0)}
    except: pass
    return {"type": "Unknown", "cmc": 0}

# --- SIDEBAR ---
with st.sidebar:
    st.header("📋 Infos Joueur & Tournoi")
    last_n = st.text_input("NOM", value="BELEREN")
    first_n = st.text_input("PRÉNOM", value="Jace")
    dci_v = st.text_input("DCI / ID", value="00000000")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION")
    event_v = st.text_input("ÉVÉNEMENT")
    dname_v = st.text_input("NOM DU DECK", value="Mon Deck")

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Analyse & Répartition automatique...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                total_qty = int(row['Quantity'])
                
                # --- LOGIQUE DE RÉPARTITION WINDOWS ---
                is_land = "Land" in sf["type"]
                
                if is_land:
                    m, s, c = total_qty, 0, 0
                else:
                    m = min(total_qty, 4)        # Max 4 en Main
                    remainder = total_qty - m
                    s = min(remainder, 4)       # Max 4 en Side (optionnel, selon tes règles)
                    c = remainder - s           # Le reste en Cut
                
                processed.append({
                    "Nom": name, 
                    "Main": m, 
                    "Side": s, 
                    "Cut": c, 
                    "Total": total_qty,
                    "Type": sf["type"], 
                    "CMC": sf["cmc"]
                })
                time.sleep(0.02)
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Répartition terminée !", state="complete")

    # --- ÉDITEUR ET CALCULS ---
    df = st.session_state.master_df

    # L'éditeur met à jour le Total si on change Main/Side/Cut
    edited_df = st.data_editor(
        df, 
        hide_index=True, 
        use_container_width=True,
        column_config={
            "Nom": st.column_config.TextColumn("Card Name", width="large", disabled=True),
            "Total": st.column_config.NumberColumn("Total", disabled=True),
            "Type": st.column_config.TextColumn("Type", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True),
        }
    )
    
    # Recalcul du Total en cas de modif manuelle
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']
    st.session_state.master_df = edited_df

    # --- METRICS ---
    m_total = edited_df['Main'].sum()
    s_total = edited_df['Side'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{m_total} / 60", delta=int(m_total-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_total} / 15", delta=int(s_total-15), delta_color="inverse")
    col3.metric("TOTAL INVENTAIRE", edited_df['Total'].sum())

    # --- PDF ---
    if st.button("📄 GÉNÉRER PDF PRO", use_container_width=True, type="primary"):
        # (Le code PDF reste le même que précédemment pour la mise en page)
        st.success("Génération lancée...")
        # ... (insérer ici la logique PDF précédente)
