from datetime import datetime
import hashlib
import sqlite3
import pandas as pd
import streamlit as st

# ---------------------------------------------------------
# CONFIGURAZIONE PAGINA
# ---------------------------------------------------------
st.set_page_config(
    page_title="Portale Manutenzioni MAM", page_icon="🛠️", layout="wide"
)

# Costanti di sistema
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

# ---------------------------------------------------------
# GESTIONE UTENTI (PASSWORD HASHED)
# ---------------------------------------------------------
UTENTI_DB = {
    "op_attrezzeria": {
        "nome": "Operatore Attrezzeria",
        "password_hash": hashlib.sha256("password123".encode()).hexdigest(),
        "ruolo": "Reparto",
        "reparto": "ATTREZZERIA",
    },
    "op_montaggi": {
        "nome": "Operatore Montaggi",
        "password_hash": hashlib.sha256("password123".encode()).hexdigest(),
        "ruolo": "Reparto",
        "reparto": "MONTAGGI",
    },
    "tecnico_mam": {
        "nome": "Luca Bianchi (Tecnico MAM)",
        "password_hash": hashlib.sha256("mam2026".encode()).hexdigest(),
        "ruolo": "MAM",
        "reparto": "MAM",
    },
    "admin_mam": {
        "nome": "Responsabile MAM",
        "password_hash": hashlib.sha256("admin2026".encode()).hexdigest(),
        "ruolo": "MAM",
        "reparto": "MAM",
    },
}


def verify_password(password, hashed_password):
    return hashlib.sha256(password.encode()).hexdigest() == hashed_password


# ---------------------------------------------------------
# DATABASE SQLITE & MIGRATION AUTOMATICA
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("manutenzioni_mam.db")


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()
        # 1. Crea la tabella se non esiste
        cursor.execute("""
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

        # 2. Aggiunge automaticamente la colonna utente_creatore se manca nei vecchi DB
        cursor.execute("PRAGMA table_info(richieste)")
        colonne = [col[1] for col in cursor.fetchall()]
        if "utente_creatore" not in colonne:
            cursor.execute(
                "ALTER TABLE richieste ADD COLUMN utente_creatore TEXT"
            )


init_db()

# ---------------------------------------------------------
# SESSIONE ED AUTENTICAZIONE
# ---------------------------------------------------------
if "autenticato" not in st.session_state:
    st.session_state["autenticato"] = False
    st.session_state["username"] = None
    st.session_state["ruolo"] = None
    st.session_state["nome_utente"] = None
    st.session_state["reparto_utente"] = None


def login_screen():
    st.title("🛠️ Portale Manutenzioni MAM - Accesso")
    st.subheader("Inserisci le tue credenziali aziendali")

    col_login, _ = st.columns([1, 1])
    with col_login:
        with st.form("form_login"):
            username = st.text_input("Username").strip().lower()
            password = st.text_input("Password", type="password")
            btn_login = st.form_submit_button("Accedi")

            if btn_login:
                if username in UTENTI_DB and verify_password(
                    password, UTENTI_DB[username]["password_hash"]
                ):
                    user_info = UTENTI_DB[username]
                    st.session_state["autenticato"] = True
                    st.session_state["username"] = username
                    st.session_state["nome_utente"] = user_info["nome"]
                    st.session_state["ruolo"] = user_info["ruolo"]
                    st.session_state["reparto_utente"] = user_info["reparto"]
                    st.success(f"Benvenuto, {user_info['nome']}!")
                    st.rerun()
                else:
                    st.error("Username o password non corretti.")

        st.info("""
        **Credenziali Demo per Prova:**
        * **Operatore Attrezzeria:** `op_attrezzeria` / `password123`
        * **Operatore Montaggi:** `op_montaggi` / `password123`
        * **Tecnico MAM:** `tecnico_mam` / `mam2026`
        * **Admin MAM:** `admin_mam` / `admin2026`
        """)


def logout():
    st.session_state["autenticato"] = False
    st.session_state["username"] = None
    st.session_state["ruolo"] = None
    st.session_state["nome_utente"] = None
    st.session_state["reparto_utente"] = None
    st.rerun()


# ---------------------------------------------------------
# APPLICAZIONE PRINCIPALE
# ---------------------------------------------------------
if not st.session_state["autenticato"]:
    login_screen()
else:
    # Sidebar Info Utente
    st.sidebar.title(f"👤 {st.session_state['nome_utente']}")
    st.sidebar.caption(
        f"**Ruolo:** {st.session_state['ruolo']} | **Reparto:** {st.session_state['reparto_utente']}"
    )

    if st.sidebar.button("🚪 Disconnetti (Logout)"):
        logout()

    st.sidebar.markdown("---")

    # Menu dinamico in base al ruolo
    if st.session_state["ruolo"] == "MAM":
        opzioni_menu = [
            "Gestione Interventi (MAM)",
            "Nuova Richiesta",
            "Analisi & Report",
        ]
    else:
        opzioni_menu = ["Nuova Richiesta", "I Miei Interventi"]

    menu = st.sidebar.radio("Navigazione", opzioni_menu)
    st.title("🛠️ Portale Gestione Manutenzioni MAM")

    # ---------------------------------------------------------
    # 1. NUOVA RICHIESTA
    # ---------------------------------------------------------
    if menu == "Nuova Richiesta":
        st.subheader("Invia una nuova segnalazione di manutenzione")

        with st.form("form_richiesta", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                default_reparto = st.session_state["reparto_utente"]
                if default_reparto in REPARTI:
                    reparto = st.selectbox(
                        "Reparto richiedente *",
                        REPARTI,
                        index=REPARTI.index(default_reparto),
                    )
                else:
                    reparto = st.selectbox("Reparto richiedente *", REPARTI)

                macchinario = st.text_input(
                    "Macchinario / Sigla Impianto *",
                    placeholder="es. Trancia T-04",
                )
                tipo_intervento = st.selectbox(
                    "Tipo Intervento", TIPI_INTERVENTO
                )

            with col2:
                priorita = st.select_slider(
                    "Livello di Priorità *", options=PRIORITA, value="Media"
                )
                descrizione = st.text_area(
                    "Descrizione del guasto o intervento richiesto *",
                    placeholder="Descrivi dettagliatamente il problema...",
                )

            submitted = st.form_submit_button("🚀 Invia Richiesta a MAM")

            if submitted:
                if not macchinario or not descrizione:
                    st.error("Compilare tutti i campi obbligatori (*).")
                else:
                    data_ora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO richieste (data_ora, reparto, macchinario, tipo_intervento, priorita, descrizione, stato, tecnico_mam, note_mam, utente_creatore)
                            VALUES (?, ?, ?, ?, ?, ?, 'Aperta', '', '', ?)
                        """,
                            (
                                data_ora,
                                reparto,
                                macchinario,
                                tipo_intervento,
                                priorita,
                                descrizione,
                                st.session_state["username"],
                            ),
                        )
                    st.success(
                        f"Richiesta inoltrata con successo al team MAM per il reparto {reparto}!"
                    )

    # ---------------------------------------------------------
    # 2. I MIEI INTERVENTI (Solo Reparti)
    # ---------------------------------------------------------
    elif menu == "I Miei Interventi":
        st.subheader(
            f"Stato interventi per il reparto: {st.session_state['reparto_utente']}"
        )

        with get_connection() as conn:
            df = pd.read_sql_query(
                "SELECT id, data_ora, reparto, macchinario, tipo_intervento, priorita, descrizione, stato, tecnico_mam, note_mam FROM richieste WHERE reparto = ? ORDER BY id DESC",
                conn,
                params=(st.session_state["reparto_utente"],),
            )

        if df.empty:
            st.info("Nessuna richiesta inserita per il tuo reparto.")
        else:
            st.dataframe(df, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # 3. GESTIONE INTERVENTI (Solo MAM)
    # ---------------------------------------------------------
    elif menu == "Gestione Interventi (MAM)":
        if st.session_state["ruolo"] != "MAM":
            st.error("Accesso non autorizzato. Sezione riservata al team MAM.")
        else:
            st.subheader("Pannello Controllo Manutenzioni - Team MAM")

            with get_connection() as conn:
                df = pd.read_sql_query(
                    "SELECT * FROM richieste ORDER BY id DESC", conn
                )

            if df.empty:
                st.info("Nessuna richiesta di manutenzione presente a sistema.")
            else:
                col_f1, col_f2 = st.columns(2)
                with col_f1:
                    filtro_stato = st.multiselect(
                        "Filtra per Stato",
                        STATI,
                        default=["Aperta", "In Corso"],
                    )
                with col_f2:
                    filtro_reparto = st.multiselect(
                        "Filtra per Reparto", REPARTI
                    )

                df_filtrato = df.copy()
                if filtro_stato:
                    df_filtrato = df_filtrato[
                        df_filtrato["stato"].isin(filtro_stato)
                    ]
                if filtro_reparto:
                    df_filtrato = df_filtrato[
                        df_filtrato["reparto"].isin(filtro_reparto)
                    ]

                st.dataframe(
                    df_filtrato, use_container_width=True, hide_index=True
                )

                st.markdown("---")
                st.write("### Aggiorna Stato Intervento")

                col_id, _ = st.columns([1, 3])

                with col_id:
                    id_selezionato = st.selectbox(
                        "Seleziona ID Richiesta", options=df["id"].tolist()
                    )

                record_attuale = df[df["id"] == id_selezionato]

                if not record_attuale.empty:
                    rec = record_attuale.iloc[0]
                    utente_creatore = (
                        rec.get("utente_creatore")
                        if pd.notna(rec.get("utente_creatore"))
                        else "N/D"
                    )

                    st.caption(
                        f"Modifica ID #{id_selezionato} - **{rec['reparto']}** ({rec['macchinario']}) | Inviato da: {utente_creatore}"
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
                                "Tecnico MAM Assegnato",
                                value=rec["tecnico_mam"]
                                if pd.notna(rec["tecnico_mam"])
                                and rec["tecnico_mam"] != ""
                                else st.session_state["nome_utente"],
                            )
                        with c2:
                            note = st.text_area(
                                "Note d'intervento / Componenti sostituiti",
                                value=rec["note_mam"]
                                if pd.notna(rec["note_mam"])
                                else "",
                            )

                        btn_salva = st.form_submit_button("💾 Salva Modifiche")

                        if btn_salva:
                            with get_connection() as conn:
                                conn.execute(
                                    """
                                    UPDATE richieste 
                                    SET stato = ?, tecnico_mam = ?, note_mam = ?
                                    WHERE id = ?
                                """,
                                    (
                                        nuovo_stato,
                                        tecnico,
                                        note,
                                        id_selezionato,
                                    ),
                                )
                            st.success(
                                f"Richiesta #{id_selezionato} aggiornata!"
                            )
                            st.rerun()

    # ---------------------------------------------------------
    # 4. ANALISI & REPORT (Solo MAM)
    # ---------------------------------------------------------
    elif menu == "Analisi & Report":
        if st.session_state["ruolo"] != "MAM":
            st.error("Accesso non autorizzato. Sezione riservata al team MAM.")
        else:
            st.subheader("Statistiche e Performance Manutenzioni")

            with get_connection() as conn:
                df = pd.read_sql_query("SELECT * FROM richieste", conn)

            if df.empty:
                st.info("Dati insufficienti per generare report.")
            else:
                kpi1, kpi2, kpi3 = st.columns(3)
                kpi1.metric("Totale Richieste", len(df))
                kpi2.metric(
                    "Aperte / In Corso",
                    len(df[df["stato"].isin(["Aperta", "In Corso"])]),
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
