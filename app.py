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
            type_line = d.get("type_line", "")
            return {
                "type": type_line, 
                "cmc": d.get("cmc", 0),
                "is_basic": "Basic Land" in type_line or "Basic Snow Land" in type_line
            }
    except: pass
    return {"type": "Unknown", "cmc": 0, "is_basic": False}

# --- SIDEBAR (Tous tes champs) ---
with st.sidebar:
    st.header("👤 Player Info")
    last_n = st.text_input("LAST NAME", value="BELEREN")
    first_n = st.text_input("FIRST NAME", value="Jace")
    dci_v = st.text_input("DCI / ID", value="000")
    st.header("🏆 Tournament Info")
    event_v = st.text_input("EVENT", value="")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION", value="")
    table_v = st.text_input("TABLE #", value="")
    dname_v = st.text_input("DECK NAME", value="My Deck")

file = st.file_uploader("📂 Chargez votre CSV", type="csv")

if file:
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        
        with st.status("🔮 Logic Windows Distribution...", expanded=True) as status:
            for i, row in df_g.iterrows():
                name = str(row[col_name])
                sf = get_scryfall_data(name)
                total_qty = int(row['Quantity'])
                
                # LOGIQUE WINDOWS : Basic Lands (ex: 7 Forets) -> Tout en Main
                if sf["is_basic"]:
                    m, s, c = total_qty, 0, 0
                else:
                    m = min(total_qty, 4)
                    reste = total_qty - m
                    s = min(reste, 4)
                    c = reste - s
                
                processed.append({
                    "Card Name": name, "Main": m, "Side": s, "Cut": c, 
                    "Total": total_qty, "Type": sf["type"], "CMC": sf["cmc"]
                })
            
            # --- TRI AUTOMATIQUE PAR NOM ---
            st.session_state.master_df = pd.DataFrame(processed).sort_values("Card Name")
            status.update(label="Distribution & Sorting Complete!", state="complete")

    # --- ÉDITEUR ET CALCULS ---
    # On affiche le tableau trié
    edited_df = st.data_editor(
        st.session_state.master_df,
        hide_index=True,
        use_container_width=True,
        key="editor_pro"
    )

    # RECALCUL EN DIRECT
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

    # --- PDF (Miroir Windows avec Tableaux) ---
    if st.button("📄 GENERATE PROFESSIONAL PDF", use_container_width=True, type="primary"):
        pdf = FPDF()
        
        # PAGE 1 : DECKLIST
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(190, 10, "MAGIC: THE GATHERING DECKLIST", 0, 1, "C")
        
        pdf.set_font("Arial", "", 8)
        pdf.cell(95, 7, f"LAST NAME: {last_n.upper()}", 1)
        pdf.cell(95, 7, f"FIRST NAME: {first_n}", 1, 1)
        pdf.cell(190, 7, f"EVENT: {event_v} | DECK: {dname_v}", 1, 1)
        
        pdf.ln(5)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(20, 8, "QTY", 1, 0, "C"); pdf.cell(170, 8, "MAIN DECK (Sorted)", 1, 1, "C")
        pdf.set_font("Arial", "", 9)
        # Trié pour le PDF
        for _, r in edited_df[edited_df['Main'] > 0].sort_values("Card Name").iterrows():
            pdf.cell(20, 6, str(r['Main']), 1, 0, "C")
            pdf.cell(170, 6, f" {r['Card Name']}", 1, 1)

        # PAGE 2 : FULL TABLE (M/S/C)
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(190, 10, "FULL INVENTORY & ANALYSIS", 0, 1, "C")
        pdf.ln(5)
        pdf.set_font("Arial", "B", 8)
        pdf.set_fill_color(230, 230, 230)
        h = ["M", "S", "C", "Tot", "Card Name", "Type", "CMC"]
        w = [10, 10, 10, 10, 75, 63, 12]
        for i, text in enumerate(h): pdf.cell(w[i], 7, text, 1, 0, "C", True)
        pdf.ln()
        
        pdf.set_font("Arial", "", 7)
        for _, r in edited_df.sort_values("Card Name").iterrows():
            pdf.cell(10, 5, str(r['Main']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Side']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Cut']), 1, 0, "C")
            pdf.cell(10, 5, str(r['Total']), 1, 0, "C")
            pdf.cell(75, 5, f" {r['Card Name']}", 1, 0, "L")
            pdf.cell(63, 5, f" {r['Type'][:38]}", 1, 0, "L")
            pdf.cell(12, 5, str(r['CMC']), 1, 1, "C")

        pdf_out = pdf.output(dest='S').encode('latin-1', 'replace')
        st.download_button("📥 DOWNLOAD FINAL PDF", data=pdf_out, file_name=f"Decklist_{last_n}.pdf")
