import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time

# --- CONFIGURATION ---
st.set_page_config(page_title="MTG Assistant Pro", layout="wide")
st.title("🧙‍♂️ MTG Assistant Pro : Logique 2-1-1")

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
    event_v = st.text_input("EVENT")
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
                
                # --- LOGIQUE 2-1-1 ---
                if sf["is_basic"]:
                    m, s, c = total_qty, 0, 0
                else:
                    # Pour chaque tranche de 4 : 2 Main, 1 Side, 1 Cut
                    # Exemple: 4 cartes -> 2, 1, 1
                    # Exemple: 1 carte  -> 1, 0, 0 (priorité au Main)
                    m, s, c = 0, 0, 0
                    for _ in range(total_qty):
                        if m < 2: m += 1
                        elif s < 1: s += 1
                        elif c < 1: c += 1
                        else: # Si on dépasse 4, on recommence la boucle ou on empile
                            m += 1 # Ajuste ici si tu veux que le surplus de 4 aille ailleurs
                
                processed.append({
                    "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                    "Total": total_qty, "Type": sf["type"], "CMC": sf["cmc"]
                })
            
            # TRI PAR NOM
            st.session_state.master_df = pd.DataFrame(processed).sort_values("Card Name")
            status.update(label="Répartition 2-1-1 Terminée !", state="complete")

    # --- ÉDITEUR ET CALCULS ---
    # On affiche le tableau trié. Les calculs se mettent à jour quand on change une cellule.
    edited_df = st.data_editor(
        st.session_state.master_df,
        hide_index=True,
        use_container_width=True,
        key="editor_211"
    )

    # RECALCUL IMMÉDIAT DES TOTAUX
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

    # --- PDF ---
    if st.button("📄 GÉNÉRER LE PDF PRO", use_container_width=True, type="primary"):
        pdf = FPDF()
        
        # Page 1: Decklist
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "MTG DECKLIST - 2-1-1 LOGIC", 0, 1, "C")
        pdf.set_font("Arial", "", 9)
        pdf.cell(190, 7, f"PLAYER: {first_n} {last_n} | EVENT: {event_v}", 1, 1)
        pdf.ln(5)
        
        # Tableau Page 2: Inventaire (Le tableau Windows)
        pdf.add_page()
        pdf.set_font("Arial", "B", 12)
        pdf.cell(190, 10, "INVENTAIRE COMPLET (M / S / C)", 0, 1, "C")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 8)
        headers = ["M", "S", "C", "Tot", "Nom", "Type"]
        w = [10, 10, 10, 10, 80, 70]
        for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1, 0, "C")
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
