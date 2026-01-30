import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time
import io

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Web Edition")

# --- FONCTIONS TECHNIQUES ---
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

# --- FORMULAIRE COMPLET (Comme Windows) ---
with st.sidebar:
    st.header("📋 Informations Joueur")
    last_n = st.text_input("NOM (Last Name)", value="BELEREN")
    first_n = st.text_input("PRÉNOM (First Name)", value="Jace")
    dci_v = st.text_input("DCI / ID", value="00000000")
    
    st.header("🏢 Informations Tournoi")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION", placeholder="Ville, Boutique...")
    event_v = st.text_input("ÉVÉNEMENT", placeholder="Regional, FNM...")
    dname_v = st.text_input("NOM DU DECK", value="Mon Deck")
    st.divider()
    st.info("La logique 'Main + Side + Cut = Total' est appliquée automatiquement.")

# --- CHARGEMENT ET CALCULS ---
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
                total_qty = int(row['Quantity'])
                
                # Logique par défaut : 4 Main, le reste en Side
                is_land = "Land" in sf["type"]
                m = total_qty if is_land else min(total_qty, 4)
                s = 0 if is_land else max(0, total_qty - 4)
                
                processed.append({
                    "Nom": name, 
                    "Main": m, 
                    "Side": s, 
                    "Cut": 0, 
                    "Total": total_qty,
                    "Type": sf["type"], 
                    "CMC": sf["cmc"]
                })
                time.sleep(0.05)
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Analyse terminée !", state="complete")

    # --- ÉDITION ET CALCULS DYNAMIQUES ---
    df = st.session_state.master_df

    # Recalcul automatique : on s'assure que le Total reste la somme des 3
    # Note: L'utilisateur peut modifier Main, Side ou Cut.
    edited_df = st.data_editor(
        df, 
        hide_index=True, 
        use_container_width=True,
        column_config={
            "Nom": st.column_config.TextColumn("Card Name", width="large", disabled=True),
            "Main": st.column_config.NumberColumn("Main", min_value=0, step=1),
            "Side": st.column_config.NumberColumn("Side", min_value=0, step=1),
            "Cut": st.column_config.NumberColumn("Cut", min_value=0, step=1),
            "Total": st.column_config.NumberColumn("Total", help="Somme de Main+Side+Cut", disabled=True),
            "Type": st.column_config.TextColumn("Type", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True),
        }
    )
    
    # Mise à jour du Total calculé
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']
    st.session_state.master_df = edited_df

    # --- AFFICHAGE DES COMPTEURS ---
    m_count, s_count = edited_df['Main'].sum(), edited_df['Side'].sum()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{m_count} / 60", delta=int(m_count-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_count} / 15", delta=int(s_count-15), delta_color="inverse")
    col3.metric("TOTAL CARTES", edited_df['Total'].sum())

    # --- GÉNÉRATION PDF (2 PAGES) ---
    if st.button("📄 GÉNÉRER LE PDF COMPLET", use_container_width=True, type="primary"):
        pdf = FPDF()
        
        # PAGE 1 : FEUILLE OFFICIELLE
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        
        pdf.set_font("Arial", "", 9)
        pdf.cell(95, 8, f" LAST NAME: {clean_pdf_text(last_n.upper())}", 1)
        pdf.cell(95, 8, f" FIRST NAME: {clean_pdf_text(first_n)}", 1, 1)
        pdf.cell(95, 8, f" DCI / ID: {clean_pdf_text(dci_v)}", 1)
        pdf.cell(95, 8, f" DATE: {clean_pdf_text(date_v)}", 1, 1)
        pdf.cell(95, 8, f" LOCATION: {clean_pdf_text(loc_v)}", 1)
        pdf.cell(95, 8, f" EVENT: {clean_pdf_text(event_v)}", 1, 1)
        pdf.cell(190, 8, f" DECK NAME: {clean_pdf_text(dname_v)}", 1, 1)
        
        pdf.ln(5)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(190, 8, f"MAIN DECK LIST ({m_count} cards)", 1, 1, "C", fill=False)
        
        pdf.set_font("Arial", "", 8)
        # Affichage des cartes du Main Deck
        for _, r in edited_df[edited_df['Main'] > 0].sort_values("Nom").iterrows():
            pdf.cell(10, 5, str(r['Main']), 1, 0, "C")
            pdf.cell(180, 5, f" {clean_pdf_text(r['Nom'])}", 1, 1)

        # PAGE 2 : INVENTAIRE GEEK
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "INVENTAIRE COMPLET (MAIN / SIDE / CUT)", 0, 1, "C")
        pdf.ln(5)
        
        # Header Tableau
        pdf.set_font("Arial", "B", 8)
        cols_w = [10, 10, 10, 10, 75, 65, 10]
        titles = ["M", "S", "C", "Tot", "Nom de la Carte", "Type", "CMC"]
        for i, t in enumerate(titles): pdf.cell(cols_w[i], 7, t, 1, 0, "C")
        pdf.ln()
        
        # Données triées
        pdf.set_font("Arial", "", 7)
        for _, r in edited_df.sort_values("Nom").iterrows():
            pdf.cell(10, 5, str(r['Main']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Side']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Cut']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Total']), 1, 0, "C")
            pdf.cell(75, 5, f" {clean_pdf_text(r['Nom'])}", 1, 0, "L")
            pdf.cell(65, 5, f" {clean_pdf_text(r['Type'])}", 1, 0, "L")
            pdf.cell(10, 5, str(r['CMC']), 1, 1, "C")

        # Export
        pdf_bytes = pdf.output(dest='S').encode('latin-1')
        st.download_button("📥 TÉLÉCHARGER LE PDF PRO", data=pdf_bytes, file_name=f"Decklist_{last_n}.pdf")
