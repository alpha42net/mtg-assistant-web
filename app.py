import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time
import io

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MTG Assistant Pro Web", layout="wide")

# Style CSS pour coller à l'ambiance MTG
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_name_with_html=True)

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

# --- BARRE LATÉRALE : INFOS TOURNOI ---
with st.sidebar:
    st.header("📋 Informations Decklist")
    last_n = st.text_input("NOM", placeholder="ex: BELEREN")
    first_n = st.text_input("PRÉNOM", placeholder="ex: Jace")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION")
    event_v = st.text_input("EVENT")
    dname_v = st.text_input("DECK NAME")
    st.divider()
    st.info("Une fois l'analyse terminée, modifiez les quantités directement dans le tableau.")

# --- CHARGEMENT ET LOGIQUE ---
file = st.file_uploader("📂 Déposez votre CSV exporté (ex: ManaBox, Archidekt)", type="csv")

if file:
    # Initialisation de la session pour ne pas perdre les données au rafraîchissement
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        total_main = 0
        
        with st.status("🔮 Synchronisation avec Scryfall...", expanded=True) as status:
            for i, (_, r) in enumerate(df_g.sort_values(by=col_name).iterrows()):
                name = str(r[col_name])
                st.write(f"Analyse de : {name}")
                sf = get_scryfall_data(name)
                time.sleep(0.05)
                
                # Logique Terrain / Sorts
                is_land = "Land" in sf["type"] or any(x in name.lower() for x in ["island", "forest", "swamp", "mountain", "plains"])
                m = int(r['Quantity']) if is_land else min(int(r['Quantity']), 2)
                s = 0 if is_land else int(r['Quantity']) - m
                total_main += m
                processed.append({"Nom": name, "Total": int(r['Quantity']), "Main": m, "Side": s, "Cut": 0, "Type": sf["type"], "CMC": sf["cmc"]})
            
            # Correction automatique pour atteindre 60 si possible
            idx = len(processed) - 1
            while total_main > 60 and idx >= 0:
                if "Land" not in processed[idx]["Type"] and processed[idx]["Main"] > 0:
                    processed[idx]["Main"] -= 1
                    processed[idx]["Cut"] += 1
                    total_main -= 1
                else: idx -= 1
            
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Analyse terminée !", state="complete")

    # --- AFFICHAGE ÉDITEUR ---
    df = st.session_state.master_df
    
    m_count = df['Main'].sum()
    s_count = df['Side'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("MAIN DECK", f"{m_count} / 60", delta=int(m_count-60), delta_color="inverse")
    c2.metric("SIDEBOARD", f"{s_count} / 15", delta=int(s_count-15), delta_color="inverse")
    c3.metric("CARTES ANALYSÉES", len(df))

    st.subheader("📝 Édition de l'inventaire")
    edited_df = st.data_editor(
        df,
        column_config={
            "Nom": st.column_config.TextColumn("Nom de la Carte", width="large", disabled=True),
            "Main": st.column_config.NumberColumn("Main", min_value=0, step=1),
            "Side": st.column_config.NumberColumn("Side", min_value=0, step=1),
            "Cut": st.column_config.NumberColumn("Cut", min_value=0, step=1),
            "Total": st.column_config.NumberColumn("Total", disabled=True),
            "Type": st.column_config.TextColumn("Type Scryfall", width="medium", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True),
        },
        hide_index=True,
        use_container_width=True
    )
    st.session_state.master_df = edited_df

    # --- BOUTON GÉNÉRATION PDF ---
    if st.button("📄 GÉNÉRER LE PDF COMPLET (2 PAGES)", use_container_width=True, type="primary"):
        pdf = FPDF()
        
        # --- PAGE 1 : STANDARD JUDGE ---
        pdf.add_page()
        pdf.set_auto_page_break(False)
        pdf.set_font("Arial", "B", 16)
        pdf.text(35, 15, "MAGIC: THE GATHERING DECKLIST")
        
        pdf.set_font("Arial", "", 8)
        pdf.set_xy(35, 22)
        pdf.cell(82, 7, f" DATE: {clean_pdf_text(date_v)}", 1)
        pdf.cell(83, 7, f" LOCATION: {clean_pdf_text(loc_v)}", 1)
        pdf.set_xy(35, 29); pdf.cell(165, 7, f" EVENT: {clean_pdf_text(event_v)}", 1)
        pdf.set_xy(35, 36); pdf.cell(165, 7, f" DECK: {clean_pdf_text(dname_v)}", 1)
        
        pdf.rect(10, 50, 15, 230)
        with pdf.rotation(90, 17, 160):
            pdf.set_font("Arial", "B", 7)
            pdf.text(17, 160, f"NAME: {clean_pdf_text(last_n.upper())} {clean_pdf_text(first_n.upper())}")
        
        # Séparation Spells / Lands
        spells = edited_df[(edited_df['Main'] > 0) & (~edited_df['Type'].str.contains("Land", na=False))]
        lands = edited_df[(edited_df['Main'] > 0) & (edited_df['Type'].str.contains("Land", na=False))]
        side = edited_df[edited_df['Side'] > 0]

        # Colonne Gauche : Spells
        pdf.set_xy(28, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck Spells:", 0, 1)
        y = 56
        for _, r in spells.iterrows():
            pdf.set_xy(28, y); pdf.set_font("Arial", "", 7); pdf.cell(8, 4, str(r['Main']), "B", 0, "C")
            pdf.cell(77, 4, f" {clean_pdf_text(r['Nom'])}", "B", 1); y += 4
        
        # Colonne Droite : Lands & Side
        rx, yr = 118, 50
        pdf.set_xy(rx, yr); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Lands:", 0, 1); yr += 6
        for _, r in lands.iterrows():
            pdf.set_xy(rx, yr); pdf.set_font("Arial", "", 7); pdf.cell(8, 4, str(r['Main']), "B", 0, "C")
            pdf.cell(74, 4, f" {clean_pdf_text(r['Nom'])}", "B", 1); yr += 4
        
        yr += 5; pdf.set_xy(rx, yr); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Sideboard:", 0, 1); yr += 6
        for _, r in side.iterrows():
            pdf.set_xy(rx, yr); pdf.set_font("Arial", "", 7); pdf.cell(8, 4, str(r['Side']), "B", 0, "C")
            pdf.cell(74, 4, f" {clean_pdf_text(r['Nom'])}", "B", 1); yr += 4

        # Blocs Officiels
        pdf.set_xy(28, 260); pdf.set_font("Arial", "B", 10); pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(m_count), 1, 1, "C")
        pdf.set_xy(118, 225); pdf.cell(62, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(s_count), 1, 1, "C")
        pdf.set_xy(118, 238); pdf.set_font("Arial", "B", 7); pdf.cell(82, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(118, 243); pdf.cell(41, 10, "Deck Check:", 1); pdf.cell(41, 10, "Status:", 1)
        pdf.set_xy(118, 253); pdf.cell(41, 10, "Judge:", 1); pdf.cell(41, 10, "Main Check:", 1)

        # --- PAGE 2 : GEEK INVENTORY ---
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)
        pdf.set_font("Arial", "B", 14); pdf.cell(190, 10, "INVENTAIRE GEEK COMPLET", 0, 1, "C")
        
        # Stats rapide
        types = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker", "Land"]
        stats_line = " | ".join([f"{t}: {len(edited_df[edited_df['Type'].str.contains(t, na=False)])}" for t in types])
        pdf.set_font("Arial", "I", 8); pdf.cell(190, 6, stats_line, 0, 1, "C"); pdf.ln(5)

        # Tableau Multi-colonnes avec gestion du chevauchement
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(230, 230, 230)
        cw = [8, 8, 8, 70, 84, 12]
        titles = ["M", "S", "C", "Nom de la Carte", "Type Scryfall", "CMC"]
        for i, t in enumerate(titles): pdf.cell(cw[i], 7, t, 1, 0, "C", True)
        pdf.ln()

        pdf.set_font("Arial", "", 7)
        for i, row in edited_df.iterrows():
            h = 5 if len(str(row['Type'])) < 55 else 10
            if pdf.get_y() + h > 280: pdf.add_page()
            
            fill = (i % 2 == 0)
            if fill: pdf.set_fill_color(248, 248, 248)
            
            pdf.cell(8, h, str(row['Main']), 1, 0, "C", fill)
            pdf.cell(8, h, str(row['Side']), 1, 0, "C", fill)
            pdf.cell(8, h, str(row['Cut']), 1, 0, "C", fill)
            
            cx = pdf.get_x()
            pdf.multi_cell(70, h/(2 if h==10 else 1), clean_pdf_text(row['Nom']), 1, "L", fill)
            pdf.set_xy(cx + 70, pdf.get_y() - h)
            pdf.multi_cell(84, h/(2 if h==10 else 1), clean_pdf_text(row['Type']), 1, "L", fill)
            pdf.set_xy(cx + 70 + 84, pdf.get_y() - h)
            pdf.cell(12, h, str(row['CMC']), 1, 1, "C", fill)

        # Export final
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button(label="📥 TÉLÉCHARGER LE PDF PRO (2 PAGES)", data=pdf_out, file_name=f"Decklist_{last_n}.pdf", mime="application/pdf", use_container_width=True)import streamlit as st
import pandas as pd
from fpdf import FPDF
import requests
import time
import io

# --- CONFIGURATION PAGE ---
st.set_page_config(page_title="MTG Assistant Pro Web", layout="wide")

# Style CSS pour coller à l'ambiance MTG
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    stMetric { background-color: #ffffff; padding: 10px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
    </style>
    """, unsafe_allow_name_with_html=True)

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

# --- BARRE LATÉRALE : INFOS TOURNOI ---
with st.sidebar:
    st.header("📋 Informations Decklist")
    last_n = st.text_input("NOM", placeholder="ex: BELEREN")
    first_n = st.text_input("PRÉNOM", placeholder="ex: Jace")
    date_v = st.text_input("DATE", value=time.strftime("%d/%m/%Y"))
    loc_v = st.text_input("LOCATION")
    event_v = st.text_input("EVENT")
    dname_v = st.text_input("DECK NAME")
    st.divider()
    st.info("Une fois l'analyse terminée, modifiez les quantités directement dans le tableau.")

# --- CHARGEMENT ET LOGIQUE ---
file = st.file_uploader("📂 Déposez votre CSV exporté (ex: ManaBox, Archidekt)", type="csv")

if file:
    # Initialisation de la session pour ne pas perdre les données au rafraîchissement
    if 'master_df' not in st.session_state:
        df_raw = pd.read_csv(file)
        df_raw.columns = [c.strip() for c in df_raw.columns]
        col_name = "Card Name" if "Card Name" in df_raw.columns else df_raw.columns[0]
        
        df_g = df_raw.groupby(col_name).agg({'Quantity': 'sum'}).reset_index()
        processed = []
        total_main = 0
        
        with st.status("🔮 Synchronisation avec Scryfall...", expanded=True) as status:
            for i, (_, r) in enumerate(df_g.sort_values(by=col_name).iterrows()):
                name = str(r[col_name])
                st.write(f"Analyse de : {name}")
                sf = get_scryfall_data(name)
                time.sleep(0.05)
                
                # Logique Terrain / Sorts
                is_land = "Land" in sf["type"] or any(x in name.lower() for x in ["island", "forest", "swamp", "mountain", "plains"])
                m = int(r['Quantity']) if is_land else min(int(r['Quantity']), 2)
                s = 0 if is_land else int(r['Quantity']) - m
                total_main += m
                processed.append({"Nom": name, "Total": int(r['Quantity']), "Main": m, "Side": s, "Cut": 0, "Type": sf["type"], "CMC": sf["cmc"]})
            
            # Correction automatique pour atteindre 60 si possible
            idx = len(processed) - 1
            while total_main > 60 and idx >= 0:
                if "Land" not in processed[idx]["Type"] and processed[idx]["Main"] > 0:
                    processed[idx]["Main"] -= 1
                    processed[idx]["Cut"] += 1
                    total_main -= 1
                else: idx -= 1
            
            st.session_state.master_df = pd.DataFrame(processed)
            status.update(label="Analyse terminée !", state="complete")

    # --- AFFICHAGE ÉDITEUR ---
    df = st.session_state.master_df
    
    m_count = df['Main'].sum()
    s_count = df['Side'].sum()
    
    c1, c2, c3 = st.columns(3)
    c1.metric("MAIN DECK", f"{m_count} / 60", delta=int(m_count-60), delta_color="inverse")
    c2.metric("SIDEBOARD", f"{s_count} / 15", delta=int(s_count-15), delta_color="inverse")
    c3.metric("CARTES ANALYSÉES", len(df))

    st.subheader("📝 Édition de l'inventaire")
    edited_df = st.data_editor(
        df,
        column_config={
            "Nom": st.column_config.TextColumn("Nom de la Carte", width="large", disabled=True),
            "Main": st.column_config.NumberColumn("Main", min_value=0, step=1),
            "Side": st.column_config.NumberColumn("Side", min_value=0, step=1),
            "Cut": st.column_config.NumberColumn("Cut", min_value=0, step=1),
            "Total": st.column_config.NumberColumn("Total", disabled=True),
            "Type": st.column_config.TextColumn("Type Scryfall", width="medium", disabled=True),
            "CMC": st.column_config.NumberColumn("CMC", disabled=True),
        },
        hide_index=True,
        use_container_width=True
    )
    st.session_state.master_df = edited_df

    # --- BOUTON GÉNÉRATION PDF ---
    if st.button("📄 GÉNÉRER LE PDF COMPLET (2 PAGES)", use_container_width=True, type="primary"):
        pdf = FPDF()
        
        # --- PAGE 1 : STANDARD JUDGE ---
        pdf.add_page()
        pdf.set_auto_page_break(False)
        pdf.set_font("Arial", "B", 16)
        pdf.text(35, 15, "MAGIC: THE GATHERING DECKLIST")
        
        pdf.set_font("Arial", "", 8)
        pdf.set_xy(35, 22)
        pdf.cell(82, 7, f" DATE: {clean_pdf_text(date_v)}", 1)
        pdf.cell(83, 7, f" LOCATION: {clean_pdf_text(loc_v)}", 1)
        pdf.set_xy(35, 29); pdf.cell(165, 7, f" EVENT: {clean_pdf_text(event_v)}", 1)
        pdf.set_xy(35, 36); pdf.cell(165, 7, f" DECK: {clean_pdf_text(dname_v)}", 1)
        
        pdf.rect(10, 50, 15, 230)
        with pdf.rotation(90, 17, 160):
            pdf.set_font("Arial", "B", 7)
            pdf.text(17, 160, f"NAME: {clean_pdf_text(last_n.upper())} {clean_pdf_text(first_n.upper())}")
        
        # Séparation Spells / Lands
        spells = edited_df[(edited_df['Main'] > 0) & (~edited_df['Type'].str.contains("Land", na=False))]
        lands = edited_df[(edited_df['Main'] > 0) & (edited_df['Type'].str.contains("Land", na=False))]
        side = edited_df[edited_df['Side'] > 0]

        # Colonne Gauche : Spells
        pdf.set_xy(28, 50); pdf.set_font("Arial", "B", 9); pdf.cell(85, 6, "Main Deck Spells:", 0, 1)
        y = 56
        for _, r in spells.iterrows():
            pdf.set_xy(28, y); pdf.set_font("Arial", "", 7); pdf.cell(8, 4, str(r['Main']), "B", 0, "C")
            pdf.cell(77, 4, f" {clean_pdf_text(r['Nom'])}", "B", 1); y += 4
        
        # Colonne Droite : Lands & Side
        rx, yr = 118, 50
        pdf.set_xy(rx, yr); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Lands:", 0, 1); yr += 6
        for _, r in lands.iterrows():
            pdf.set_xy(rx, yr); pdf.set_font("Arial", "", 7); pdf.cell(8, 4, str(r['Main']), "B", 0, "C")
            pdf.cell(74, 4, f" {clean_pdf_text(r['Nom'])}", "B", 1); yr += 4
        
        yr += 5; pdf.set_xy(rx, yr); pdf.set_font("Arial", "B", 9); pdf.cell(82, 6, "Sideboard:", 0, 1); yr += 6
        for _, r in side.iterrows():
            pdf.set_xy(rx, yr); pdf.set_font("Arial", "", 7); pdf.cell(8, 4, str(r['Side']), "B", 0, "C")
            pdf.cell(74, 4, f" {clean_pdf_text(r['Nom'])}", "B", 1); yr += 4

        # Blocs Officiels
        pdf.set_xy(28, 260); pdf.set_font("Arial", "B", 10); pdf.cell(65, 10, "TOTAL MAIN DECK:", 1, 0, "R"); pdf.cell(20, 10, str(m_count), 1, 1, "C")
        pdf.set_xy(118, 225); pdf.cell(62, 8, "TOTAL SIDEBOARD:", 1, 0, "R"); pdf.cell(20, 8, str(s_count), 1, 1, "C")
        pdf.set_xy(118, 238); pdf.set_font("Arial", "B", 7); pdf.cell(82, 5, "FOR OFFICIAL USE ONLY", 1, 1, "C")
        pdf.set_xy(118, 243); pdf.cell(41, 10, "Deck Check:", 1); pdf.cell(41, 10, "Status:", 1)
        pdf.set_xy(118, 253); pdf.cell(41, 10, "Judge:", 1); pdf.cell(41, 10, "Main Check:", 1)

        # --- PAGE 2 : GEEK INVENTORY ---
        pdf.add_page()
        pdf.set_auto_page_break(True, 15)
        pdf.set_font("Arial", "B", 14); pdf.cell(190, 10, "INVENTAIRE GEEK COMPLET", 0, 1, "C")
        
        # Stats rapide
        types = ["Creature", "Instant", "Sorcery", "Artifact", "Enchantment", "Planeswalker", "Land"]
        stats_line = " | ".join([f"{t}: {len(edited_df[edited_df['Type'].str.contains(t, na=False)])}" for t in types])
        pdf.set_font("Arial", "I", 8); pdf.cell(190, 6, stats_line, 0, 1, "C"); pdf.ln(5)

        # Tableau Multi-colonnes avec gestion du chevauchement
        pdf.set_font("Arial", "B", 8); pdf.set_fill_color(230, 230, 230)
        cw = [8, 8, 8, 70, 84, 12]
        titles = ["M", "S", "C", "Nom de la Carte", "Type Scryfall", "CMC"]
        for i, t in enumerate(titles): pdf.cell(cw[i], 7, t, 1, 0, "C", True)
        pdf.ln()

        pdf.set_font("Arial", "", 7)
        for i, row in edited_df.iterrows():
            h = 5 if len(str(row['Type'])) < 55 else 10
            if pdf.get_y() + h > 280: pdf.add_page()
            
            fill = (i % 2 == 0)
            if fill: pdf.set_fill_color(248, 248, 248)
            
            pdf.cell(8, h, str(row['Main']), 1, 0, "C", fill)
            pdf.cell(8, h, str(row['Side']), 1, 0, "C", fill)
            pdf.cell(8, h, str(row['Cut']), 1, 0, "C", fill)
            
            cx = pdf.get_x()
            pdf.multi_cell(70, h/(2 if h==10 else 1), clean_pdf_text(row['Nom']), 1, "L", fill)
            pdf.set_xy(cx + 70, pdf.get_y() - h)
            pdf.multi_cell(84, h/(2 if h==10 else 1), clean_pdf_text(row['Type']), 1, "L", fill)
            pdf.set_xy(cx + 70 + 84, pdf.get_y() - h)
            pdf.cell(12, h, str(row['CMC']), 1, 1, "C", fill)

        # Export final
        pdf_out = pdf.output(dest='S').encode('latin-1')
        st.download_button(label="📥 TÉLÉCHARGER LE PDF PRO (2 PAGES)", data=pdf_out, file_name=f"Decklist_{last_n}.pdf", mime="application/pdf", use_container_width=True)
