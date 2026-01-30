import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro")

def clean_pdf_text(text):
    if not isinstance(text, str): return str(text)
    return text.replace('_', ' ').encode('latin-1', 'replace').decode('latin-1')

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
    dname_v = st.text_input("DECK NAME", value="Mon Deck")

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Analyse Scryfall...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                qty = int(row['Quantity'])
                processed.append({
                    "Nom": name, 
                    "Main": qty, 
                    "Side": 0, 
                    "Cut": 0, 
                    "Total": qty,
                    "Type": sf["type"], 
                    "CMC": sf["cmc"]
                })
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Analyse terminée !", state="complete")

    # --- LOGIQUE DE CALCUL AUTOMATIQUE ---
    df = st.session_state.master_df

    # Affichage de l'éditeur
    st.write("### 📝 Éditeur Interactif")
    st.info("Modifiez 'Main', 'Side' ou 'Cut'. Le 'Total' se mettra à jour après validation.")
    
    edited_df = st.data_editor(
        df, 
        hide_index=True, 
        use_container_width=True,
        column_config={
            "Total": st.column_config.NumberColumn("Total", disabled=True), # Bloqué car calculé
            "Nom": st.column_config.TextColumn("Nom", disabled=True),
            "Type": st.column_config.TextColumn("Type", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True),
        }
    )

    # Calcul automatique du Total : Total = Main + Side + Cut
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']
    st.session_state.master_df = edited_df

    # --- COMPTEURS ---
    m_total = edited_df['Main'].sum()
    s_total = edited_df['Side'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{m_total} / 60", delta=int(m_total-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_total} / 15", delta=int(s_total-15), delta_color="inverse")
    col3.metric("CARTES TOTALES", edited_df['Total'].sum())

    # --- PDF ---
    if st.button("📄 GÉNÉRER LE PDF"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, f"DECKLIST : {dname_v}", 0, 1, "C")
        
        pdf.set_font("Arial", "B", 12)
        pdf.ln(5)
        pdf.cell(190, 8, "INVENTAIRE (Trié par Nom)", 1, 1, "C")
        
        pdf.set_font("Arial", "", 8)
        # On trie par nom pour le PDF
        pdf_df = edited_df.sort_values("Nom")
        
        for _, r in pdf_df.iterrows():
            if r['Total'] > 0:
                line = f"[{r['Main']} Main] [{r['Side']} Side] [{r['Cut']} Cut] - {r['Nom']} ({r['Type']})"
                pdf.cell(190, 6, clean_pdf_text(line), "B", 1)

        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button("📥 Télécharger le PDF", data=pdf_out, file_name="deck_calcul.pdf")
