import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Logique 2-1-1 Stricte")

def clean_for_pdf(text):
    if not isinstance(text, str): return str(text)
    return text.encode('latin-1', 'replace').decode('latin-1')

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
                "is_basic": "Basic Land" in type_line or "Basic Snow Land" in type_line
            }
    except: pass
    return {"type": "Unknown", "cmc": 0, "is_basic": False}

# --- SIDEBAR ---
with st.sidebar:
    st.header("👤 Player Info")
    last_n = st.text_input("NOM", value="BELEREN")
    first_n = st.text_input("PRÉNOM", value="Jace")
    dci_v = st.text_input("DCI", value="000")
    st.header("🏆 Tournament")
    event_v = st.text_input("EVENT", value="")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    dname_v = st.text_input("DECK NAME", value="Mon Deck")

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Calcul Répartition 2-1-1...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                total_qty = int(row['Quantity'])
                
                # --- LOGIQUE 2-1-1 STRICTE ---
                m, s, c = 0, 0, 0
                if sf["is_basic"]:
                    # Terrains de base : Tout en Main
                    m = total_qty
                else:
                    # Pour chaque carte individuelle de la pile :
                    for card_index in range(1, total_qty + 1):
                        if card_index <= 2:
                            m += 1  # Les 2 premières -> Main
                        elif card_index == 3:
                            s += 1  # La 3ème -> Side
                        elif card_index == 4:
                            c += 1  # La 4ème -> Cut
                        else:
                            c += 1  # Tout le surplus au-delà de 4 -> Cut
                
                processed.append({
                    "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                    "Total": total_qty, "Type": sf["type"], "CMC": sf["cmc"]
                })
            
            # Sauvegarde et Tri
            st.session_state.master_df = pd.DataFrame(processed).sort_values("Card Name")
            status.update(label="Répartition 2-1-1 Terminée !", state="complete")

    # --- ÉDITEUR ET CALCULS DYNAMIQUES ---
    # On utilise l'éditeur pour permettre les ajustements manuels
    edited_df = st.data_editor(
        st.session_state.master_df,
        hide_index=True,
        use_container_width=True,
        key="editor_211"
    )

    # RECALCUL DES TOTAUX (Si tu modifies une case, les compteurs en bas bougent)
    edited_df['Total'] = edited_df['Main'] + edited_df['Side'] + edited_df['Cut']
    st.session_state.master_df = edited_df 

    m_total = edited_df['Main'].sum()
    s_total = edited_df['Side'].sum()
    c_total = edited_df['Cut'].sum()
    
    st.divider()
    col1, col2, col3 = st.columns(3)
    col1.metric("MAIN DECK", f"{m_total} / 60", delta=int(m_total-60), delta_color="inverse")
    col2.metric("SIDEBOARD", f"{s_total} / 15", delta=int(s_total-15), delta_color="inverse")
    col3.metric("TOTAL CUT", c_total)

    # --- PDF SANS ERREUR UNICODE ---
    if st.button("📄 GÉNÉRER LE PDF PRO", use_container_width=True, type="primary"):
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        
        pdf.set_font("Arial", "", 8)
        pdf.cell(95, 7, f"NAME: {clean_for_pdf(last_n.upper())} {clean_for_pdf(first_n)}", 1)
        pdf.cell(95, 7, f"EVENT: {clean_for_pdf(event_v)}", 1, 1)
        pdf.ln(5)

        # Tableau Inventaire (Page 1)
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        h = ["M", "S", "C", "Tot", "Nom", "Type"]
        w = [10, 10, 10, 10, 80, 70]
        for i, head in enumerate(h): pdf.cell(w[i], 7, head, 1, 0, "C", True)
        pdf.ln()
        
        pdf.set_font("Arial", "", 7)
        for _, r in edited_df.sort_values("Card Name").iterrows():
            pdf.cell(10, 5, str(r['Main']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Side']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Cut']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Total']), 1, 0, "C")
            pdf.cell(80, 5, f" {clean_for_pdf(r['Card Name'])}", 1, 0, "L")
            pdf.cell(70, 5, f" {clean_for_pdf(r['Type'][:45])}", 1, 1, "L")

        pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 Télécharger le PDF", data=pdf_out, file_name=f"Decklist_{last_n}.pdf")
