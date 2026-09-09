import sqlite3
from datetime import datetime
import pandas as pd
import streamlit as st

# Configuratione della pagina
st.set_page_config(
    page_title="Portale Manutenzioni MAM", page_icon="🛠️", layout="wide"
)

REPARTI = [
    "ATTREZZERIA",
    "CONFEZIONAMENTO",
    "VERNICIATURA",
    "MONTAGGI",
    "TRANCERIA",
    "FISSAGGI",
]
TIPI_INTERVENTO = ["Elettrico", "Meccanico", "Elettro-meccanico", "Altro"]
PRIORITA = ["Bassa", "Media", "Alta", "Urgente (Fermo Macchina)"]
STATI = ["Aperta", "In Corso", "Risolta", "Annullata"]


# Inizializzazione Database SQLite
def get_connection():
    return sqlite3.connect("manutenzioni_mam.db")


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS richieste (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                data_ora TEXT,
                reparto TEXT,
                macchinario TEXT,
                tipo_intervento TEXT,
                priorita TEXT,
                descrizione TEXT,
                stato TEXT,
                tecnico_mam TEXT,
                note_mam TEXT
            )
        """)


init_db()

st.title("🛠️ Portale Gestione Manutenzioni MAM")

# Navigazione principale
menu = st.sidebar.radio(
    "Navigazione",
    [
        "Nuova Richiesta (Reparti)",
        "Gestione Interventi (MAM)",
        "Analisi & Report",
    ],
)

# ---------------------------------------------------------
# 1. NUOVA RICHIESTA
# ---------------------------------------------------------
if menu == "Nuova Richiesta (Reparti)":
    st.subheader("Invia una nuova segnalazione di manutenzione")

    with st.form("form_richiesta", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            reparto = st.selectbox("Reparto richiedente *", REPARTI)
            macchinario = st.text_input(
                "Macchinario / Sigla Impianto *",
                placeholder="es. Trancia T-04",
            )
            tipo_intervento = st.selectbox("Tipo Intervento", TIPI_INTERVENTO)

        with col2:
            priorita = st.select_slider(
                "Livello di Priorità *", options=PRIORITA, value="Media"
            )
            descrizione = st.text_area(
                "Descrizione del guasto o intervento richiesto *",
                placeholder="Descrivi dettagliatamente il problema...",
            )

        submitted = st.form_submit_button(" Invia Richiesta a MAM")

        if submitted:
            if not macchinario or not descrizione:
                st.error("Compilare tutti i campi obbligatori (*).")
            else:
                data_ora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO richieste (data_ora, reparto, macchinario, tipo_intervento, priorita, descrizione, stato, tecnico_mam, note_mam)
                        VALUES (?, ?, ?, ?, ?, ?, 'Aperta', '', '')
                    """,
                        (
                            data_ora,
                            reparto,
                            macchinario,
                            tipo_intervento,
                            priorita,
                            descrizione,
                        ),
                    )
                st.success(
                    f"Richiesta inoltrata con successo al team MAM per il reparto {reparto}!"
                )

# ---------------------------------------------------------
# 2. GESTIONE INTERVENTI (MAM)
# ---------------------------------------------------------
elif menu == "Gestione Interventi (MAM)":
    st.subheader("Pannello Controllo Manutenzioni - Team MAM")

    with get_connection() as conn:
        df = pd.read_sql_query(
            "SELECT * FROM richieste ORDER BY id DESC", conn
        )

    if df.empty:
        st.info("Nessuna richiesta di manutenzione presente a sistema.")
    else:
        # Filtri rapidi
        col_f1, col_f2 = st.columns(2)
        with col_f1:
            filtro_stato = st.multiselect(
                "Filtra per Stato",
                STATI,
                default=["Aperta", "In Corso"],
            )
        with col_f2:
            filtro_reparto = st.multiselect("Filtra per Reparto", REPARTI)

        df_filtrato = df.copy()
        if filtro_stato:
            df_filtrato = df_filtrato[df_filtrato["stato"].isin(filtro_stato)]
        if filtro_reparto:
            df_filtrato = df_filtrato[
                df_filtrato["reparto"].isin(filtro_reparto)
            ]

        st.dataframe(df_filtrato, use_container_width=True, hide_index=True)

        st.markdown("---")
        st.write("### Aggiorna Stato Intervento")

        col_id, col_update = st.columns([1, 3])

        with col_id:
            id_selezionato = st.number_input(
                "ID Richiesta",
                min_value=int(df["id"].min()),
                max_value=int(df["id"].max()),
                step=1,
            )

        record_attuale = df[df["id"] == id_selezionato]

        if not record_attuale.empty:
            rec = record_attuale.iloc[0]
            st.caption(
                f"Modifica ID #{id_selezionato} - **{rec['reparto']}** ({rec['macchinario']})"
            )

            with st.form("form_aggiorna"):
                c1, c2 = st.columns(2)
                with c1:
                    nuovo_stato = st.selectbox(
                        "Stato",
                        STATI,
                        index=STATI.index(rec["stato"])
                        if rec["stato"] in STATI
                        else 0,
                    )
                    tecnico = st.text_input(
                        "Tecnico MAM Assegnato", value=rec["tecnico_mam"]
                    )
                with c2:
                    note = st.text_area(
                        "Note d'intervento / Componenti sostituiti",
                        value=rec["note_mam"],
                    )

                btn_salva = st.form_submit_button("Aggiorna Richiesta")

                if btn_salva:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE richieste 
                            SET stato = ?, tecnico_mam = ?, note_mam = ?
                            WHERE id = ?
                        """,
                            (nuovo_stato, tecnico, note, id_selezionato),
                        )
                    st.success(f"Richiesta #{id_selezionato} aggiornata!")
                    st.rerun()

# ---------------------------------------------------------
# 3. ANALISI & REPORT
# ---------------------------------------------------------
elif menu == "Analisi & Report":
    st.subheader("Statistiche e Performance Manutenzioni")

    with get_connection() as conn:
        df = pd.read_sql_query("SELECT * FROM richieste", conn)

    if df.empty:
        st.info("Dati insufficienti per generare report.")
    else:
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Totale Richieste", len(df))
        kpi2.metric(
            "Aperte / In Corso", len(df[df["stato"].isin(["Aperta", "In Corso"])])
        )
        kpi3.metric("Risolte", len(df[df["stato"] == "Risolta"]))

        st.markdown("---")
        col_c1, col_c2 = st.columns(2)

        with col_c1:
            st.write("**Richieste per Reparto**")
            chart_reparti = df["reparto"].value_counts()
            st.bar_chart(chart_reparti)

        with col_c2:
            st.write("**Distribuzione per Priorità**")
            chart_prio = df["priorita"].value_counts()
            st.bar_chart(chart_prio)
