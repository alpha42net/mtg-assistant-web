import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Web Edition")

# --- FONCTION API ---
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
    st.header("📋 Infos Decklist")
    last_n = st.text_input("NOM", value="BELEREN")
    first_n = st.text_input("PRÉNOM", value="Jace")
    dci_v = st.text_input("DCI", value="000")
    event_v = st.text_input("EVENT", value="")
    dname_v = st.text_input("DECK NAME", value="Mon Deck")

# --- LOGIQUE DE CALCUL ---
file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    # 1. Chargement et répartition initiale
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Répartition initiale...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                total_qty = int(row['Quantity'])
                
                # RÉPARTITION AUTO : 4 Main / Reste en Side (max 15) / Reste en Cut
                m = min(total_qty, 4)
                reste = total_qty - m
                s = min(reste, 4) # On commence par 4 en side par défaut
                c = reste - s
                
                processed.append({
                    "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                    "Total": total_qty, "Type": sf["type"], "CMC": sf["cmc"]
                })
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Chargement terminé !", state="complete")

    # 2. L'ÉDITEUR AVEC SYNCHRONISATION FORCÉE
    # On affiche le tableau. Dès qu'une cellule change, le script repart du haut
    edited_df = st.data_editor(
        st.session_state.master_df,
        hide_index=True,
        use_container_width=True,
        key="editor",
        column_config={
            "Card Name": st.column_config.TextColumn("Card Name", disabled=True),
            "Total": st.column_config.NumberColumn("Total", disabled=True),
            "Type": st.column_config.TextColumn("Type", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True),
        }
    )

    # MISE À JOUR DU STATE : On recalcule le "Total" par ligne
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']
    st.session_state.master_df = edited_df

    # 3. AFFICHAGE DES CALCULS (METRICS)
    m_total = edited_df['Main'].sum()
    s_total = edited_df['Side'].sum()
    inv_total = edited_df['Total'].sum()
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{m_total} / 60", delta=int(m_total-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_total} / 15", delta=int(s_total-15), delta_color="inverse")
    col3.metric("TOTAL CARTES", inv_total)

    # 4. GÉNÉRATION PDF
    if st.button("📄 GÉNÉRER LE PDF TOURNAMENT", use_container_width=True, type="primary"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, f"DECKLIST : {dname_v}", 0, 1, "C")
        
        pdf.set_font("Arial", "", 10)
        pdf.cell(95, 8, f"PLAYER: {first_n} {last_n}", 1)
        pdf.cell(95, 8, f"EVENT: {event_v}", 1, 1)
        pdf.ln(5)
        
        # Table PDF
        pdf.set_font("Arial", "B", 8)
        pdf.cell(10, 7, "M", 1); pdf.cell(10, 7, "S", 1); pdf.cell(10, 7, "C", 1); pdf.cell(160, 7, "Nom", 1, 1)
        
        pdf.set_font("Arial", "", 8)
        for _, r in edited_df.iterrows():
            pdf.cell(10, 6, str(r['Main']), 1)
            pdf.cell(10, 6, str(r['Side']), 1)
            pdf.cell(10, 6, str(r['Cut']), 1)
            pdf.cell(160, 6, f" {r['Nom'] if 'Nom' in r else r['Card Name']}", 1, 1)

        pdf_bytes = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 Télécharger le PDF", data=pdf_bytes, file_name="decklist.pdf")
