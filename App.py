from datetime import datetime, timedelta
import hashlib
import sqlite3
import pandas as pd
import requests  # Per inviare chiamate HTTP a Telegram
import streamlit as st

# ---------------------------------------------------------
# CONFIGURAZIONE TELEGRAM (Sostituisci con i tuoi dati)
# ---------------------------------------------------------
TELEGRAM_BOT_TOKEN = (
    "8287541966:AAFd8QD3a18u9SlJr-KhZu9dSoc0OaBzkS4"  # es: "7123456789:ABCdefGhIJKlmNoPQRstuVWXyz"
)
TELEGRAM_CHAT_ID = "992794613"  # es: "987654321" (il tuo ID personale)


def invia_notifica_telegram(messaggio):
    """Invia un messaggio Telegram al Chat ID configurato"""
    if (
        TELEGRAM_BOT_TOKEN == "IL_TUO_TOKEN_BOT_QUI"
        or TELEGRAM_CHAT_ID == "IL_TUO_CHAT_ID_QUI"
    ):
        st.warning(
            "⚠️ Inserisci TOKEN e CHAT_ID validi per inviare notifiche Telegram."
        )
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": messaggio,
        "parse_mode": "Markdown",
    }
    try:
        response = requests.post(url, json=payload, timeout=5)
        if response.status_code == 200:
            return True
        else:
            st.error(f"Errore Telegram ({response.status_code}): {response.text}")
            return False
    except Exception as e:
        st.error(f"Errore connessione Telegram: {e}")
        return False


# ---------------------------------------------------------
# CONFIGURAZIONE PAGINA STREAMLIT
# ---------------------------------------------------------
st.set_page_config(
    page_title="MAMU CMMS - Gestione Manutenzioni",
    page_icon="🏭",
    layout="wide",
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
TIPI_INTERVENTO = [
    "Elettrico",
    "Meccanico",
    "Elettro-meccanico",
    "Idraulico/Pneumatico",
    "Preventivo",
    "Altro",
]
PRIORITA = ["Bassa", "Media", "Alta", "Urgente (Fermo Macchina)"]
STATI = ["Aperta", "In Corso", "Risolta", "Annullata"]
COSTO_ORARIO_MANODOPERA = 35.0  # €/ora predefinito per il calcolo costi MAMU

UTENTI_DB = {
    "op_attrezzeria": {
        "nome": "Operatore Attrezzeria",
        "password_hash": hashlib.sha256("password123".encode()).hexdigest(),
        "ruolo": "Reparto",
        "reparto": "ATTREZZERIA",
    },
    "op_tranceria": {
        "nome": "Operatore Tranceria",
        "password_hash": hashlib.sha256("password123".encode()).hexdigest(),
        "ruolo": "Reparto",
        "reparto": "TRANCERIA",
    },
    "tecnico_mamu": {
        "nome": "Luca Bianchi (Tecnico MAMU)",
        "password_hash": hashlib.sha256("mamu2026".encode()).hexdigest(),
        "ruolo": "MAMU",
        "reparto": "MAMU",
    },
    "admin_mamu": {
        "nome": "Responsabile MAMU",
        "password_hash": hashlib.sha256("admin2026".encode()).hexdigest(),
        "ruolo": "MAMU",
        "reparto": "MAMU",
    },
}


def verify_password(password, hashed_password):
    return hashlib.sha256(password.encode()).hexdigest() == hashed_password


# ---------------------------------------------------------
# DATABASE SQLITE E INIZIALIZZAZIONE STRUTTURA CMMS
# ---------------------------------------------------------
def get_connection():
    return sqlite3.connect("mamu_cmms.db")


def init_db():
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS macchine (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice TEXT UNIQUE,
                nome TEXT,
                reparto TEXT,
                modello TEXT,
                anno_installazione INTEGER,
                stato TEXT DEFAULT 'Operativa'
            )
        """)

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
                note_mam TEXT,
                utente_creatore TEXT,
                data_chiusura TEXT,
                ore_impiegate REAL DEFAULT 0.0,
                costo_ricambi REAL DEFAULT 0.0,
                costo_totale REAL DEFAULT 0.0,
                origine TEXT DEFAULT 'Guasto'
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ricambi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                codice TEXT UNIQUE,
                nome TEXT,
                quantita INTEGER,
                soglia_minima INTEGER,
                costo_unitario REAL
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS utilizzi_ricambi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                richiesta_id INTEGER,
                ricambio_id INTEGER,
                quantita INTEGER,
                costo_totale REAL,
                FOREIGN KEY(richiesta_id) REFERENCES richieste(id),
                FOREIGN KEY(ricambio_id) REFERENCES ricambi(id)
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS piani_preventivi (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                macchinario TEXT,
                titolo TEXT,
                frequenza_giorni INTEGER,
                prossima_scadenza TEXT,
                descrizione TEXT
            )
        """)

        cursor.execute("SELECT COUNT(*) FROM macchine")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                """
                INSERT INTO macchine (codice, nome, reparto, modello, anno_installazione, stato)
                VALUES (?, ?, ?, ?, ?, 'Operativa')
            """,
                [
                    (
                        "MAC-01",
                        "Trancia Idraulica T-04",
                        "TRANCERIA",
                        "Schuler 200T",
                        2018,
                    ),
                    (
                        "MAC-02",
                        "Isola Verniciatura V-01",
                        "VERNICIATURA",
                        "Gema Powder",
                        2020,
                    ),
                    (
                        "MAC-03",
                        "Nastro Confezionamento C-02",
                        "CONFEZIONAMENTO",
                        "FlexLink",
                        2021,
                    ),
                    (
                        "MAC-04",
                        "Centro Lavoro CNC A-01",
                        "ATTREZZERIA",
                        "Haas VF-2",
                        2019,
                    ),
                    (
                        "MAC-05",
                        "Avvitatore Multimandrino M-03",
                        "MONTAGGI",
                        "Atlas Copco",
                        2022,
                    ),
                    (
                        "MAC-06",
                        "Pressa Fissaggi F-01",
                        "FISSAGGI",
                        "Promeccanica",
                        2017,
                    ),
                ],
            )

        cursor.execute("SELECT COUNT(*) FROM ricambi")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                """
                INSERT INTO ricambi (codice, nome, quantita, soglia_minima, costo_unitario)
                VALUES (?, ?, ?, ?, ?)
            """,
                [
                    ("RIC-101", "Cuscinetto SKF 6204-2RSH", 12, 5, 14.50),
                    ("RIC-102", "Sensore Prossimità PNP M12", 4, 3, 38.00),
                    ("RIC-103", "Filtro Olio Idraulico FX-12", 2, 4, 45.00),
                    ("RIC-104", "Elettrovalvola 5/2 24VDC", 8, 2, 65.00),
                    ("RIC-105", "Cinghia Dentata HTD 8M", 3, 3, 22.00),
                ],
            )

        cursor.execute("SELECT COUNT(*) FROM piani_preventivi")
        if cursor.fetchone()[0] == 0:
            scadenza_prossima = (datetime.now() + timedelta(days=7)).strftime(
                "%Y-%m-%d"
            )
            cursor.executemany(
                """
                INSERT INTO piani_preventivi (macchinario, titolo, frequenza_giorni, prossima_scadenza, descrizione)
                VALUES (?, ?, ?, ?, ?)
            """,
                [
                    (
                        "Trancia Idraulica T-04",
                        "Cambio olio idraulico e filtri",
                        90,
                        scadenza_prossima,
                        "Sostituire olio e verificare usura guarnizioni stelo.",
                    ),
                    (
                        "Isola Verniciatura V-01",
                        "Pulizia ugelli e calibrazione",
                        30,
                        scadenza_prossima,
                        "Pulizia approfondita pistole e controllo aspirazione.",
                    ),
                    (
                        "Centro Lavoro CNC A-01",
                        "Controllo gioco assi e lubrificazione",
                        60,
                        scadenza_prossima,
                        "Ingrassaggio guide e verifica calibrazione mandrino.",
                    ),
                ],
            )


init_db()

# ---------------------------------------------------------
# AUTENTICAZIONE E GESTIONE SESSIONE PERSISTENTE
# ---------------------------------------------------------
if "autenticato" not in st.session_state:
    st.session_state["autenticato"] = False
    st.session_state["username"] = None
    st.session_state["ruolo"] = None
    st.session_state["nome_utente"] = None
    st.session_state["reparto_utente"] = None

if not st.session_state["autenticato"] and "user" in st.query_params:
    user_param = st.query_params["user"]
    if user_param in UTENTI_DB:
        user_info = UTENTI_DB[user_param]
        st.session_state["autenticato"] = True
        st.session_state["username"] = user_param
        st.session_state["nome_utente"] = user_info["nome"]
        st.session_state["ruolo"] = user_info["ruolo"]
        st.session_state["reparto_utente"] = user_info["reparto"]


def login_screen():
    st.title("🏭 MAMU CMMS - Accesso al Portale")
    st.subheader("Sistema Integrato Manutenzioni & Gestione Asset")

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
                    st.query_params["user"] = username
                    st.success(f"Benvenuto, {user_info['nome']}!")
                    st.rerun()
                else:
                    st.error("Username o password non corretti.")


def logout():
    for key in [
        "autenticato",
        "username",
        "ruolo",
        "nome_utente",
        "reparto_utente",
    ]:
        st.session_state[key] = None if key != "autenticato" else False
    st.query_params.clear()
    st.rerun()


# ---------------------------------------------------------
# APPLICAZIONE PRINCIPALE
# ---------------------------------------------------------
if not st.session_state["autenticato"]:
    login_screen()
else:
    st.sidebar.title(f"👤 {st.session_state['nome_utente']}")
    st.sidebar.caption(
        f"**Ruolo:** {st.session_state['ruolo']} | **Reparto:** {st.session_state['reparto_utente']}"
    )

    if st.sidebar.button("🚪 Disconnetti (Logout)"):
        logout()

    st.sidebar.markdown("---")

    # PULSANTE TEST TELEGRAM IN SIDEBAR
    if st.sidebar.button("🧪 Test Notifica Telegram"):
        esito = invia_notifica_telegram(
            "🔔 *TEST MAMU CMMS*\nQuesto è un messaggio di prova dal sistema di manutenzione MAMU!"
        )
        if esito:
            st.sidebar.success("Notifica inviata su Telegram!")

    st.sidebar.markdown("---")

    if st.session_state["ruolo"] == "MAMU":
        opzioni_menu = [
            "🔧 Tickets & Ordini di Lavoro",
            "📅 Manutenzione Preventiva",
            "📦 Ricambi & Magazzino",
            "📊 KPI & Controllo Costi",
            "🏭 Diario di Bordo Assets",
            "➕ Nuova Segnalazione",
        ]
    else:
        opzioni_menu = [
            "➕ Nuova Segnalazione",
            "📋 I Miei Interventi",
            "🏭 Diario di Bordo Assets",
        ]

    menu = st.sidebar.radio("Navigazione CMMS", opzioni_menu)
    st.title("🏭 MAMU CMMS - Gestione Manutenzione Industriale")

    with get_connection() as conn:
        df_macchine_all = pd.read_sql_query("SELECT * FROM macchine", conn)
    LISTA_MACCHINE = df_macchine_all["nome"].tolist()

    # ---------------------------------------------------------
    # 1. NUOVA SEGNALAZIONE (Con invio automatico Telegram)
    # ---------------------------------------------------------
    if menu == "➕ Nuova Segnalazione":
        st.subheader("Invia una nuova segnalazione di manutenzione")

        with st.form("form_richiesta", clear_on_submit=True):
            col1, col2 = st.columns(2)

            with col1:
                if st.session_state["ruolo"] == "MAMU":
                    reparto = st.selectbox("Reparto *", REPARTI)
                else:
                    reparto = st.selectbox(
                        "Reparto *",
                        options=[st.session_state["reparto_utente"]],
                        disabled=True,
                    )

                macchine_filtrate = df_macchine_all[
                    df_macchine_all["reparto"] == reparto
                ]["nome"].tolist()
                if not macchine_filtrate:
                    macchine_filtrate = LISTA_MACCHINE

                macchinario = st.selectbox(
                    "Macchinario / Asset *", macchine_filtrate
                )
                tipo_intervento = st.selectbox(
                    "Tipo Intervento", TIPI_INTERVENTO
                )

            with col2:
                priorita = st.select_slider(
                    "Livello di Priorità *", options=PRIORITA, value="Media"
                )
                descrizione = st.text_area(
                    "Descrizione Guasto / Anomalia *",
                    placeholder="Descrivi il problema riscontrato...",
                )

            submitted = st.form_submit_button("🚀 Invia Richiesta a MAMU")

            if submitted:
                if not descrizione:
                    st.error("Inserire una descrizione del problema.")
                else:
                    data_ora_apertura = datetime.now().strftime(
                        "%Y-%m-%d %H:%M:%S"
                    )
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO richieste (data_ora, reparto, macchinario, tipo_intervento, priorita, descrizione, stato, tecnico_mam, note_mam, utente_creatore, data_chiusura, origine)
                            VALUES (?, ?, ?, ?, ?, ?, 'Aperta', '', '', ?, '', 'Guasto')
                        """,
                            (
                                data_ora_apertura,
                                reparto,
                                macchinario,
                                tipo_intervento,
                                priorita,
                                descrizione,
                                st.session_state["username"],
                            ),
                        )

                    # INVIO NOTIFICA AUTOMATICA SU TELEGRAM
                    msg_telegram = (
                        f"🚨 *NUOVA SEGNALAZIONE MANUTENZIONE*\n\n"
                        f"📍 *Reparto:* {reparto}\n"
                        f"⚙️ *Macchinario:* {macchinario}\n"
                        f"⚡ *Tipo:* {tipo_intervento}\n"
                        f"🔥 *Priorità:* {priorita}\n"
                        f"📝 *Note:* {descrizione}\n"
                        f"👤 *Inviato da:* {st.session_state['nome_utente']}"
                    )
                    invia_notifica_telegram(msg_telegram)

                    st.success(
                        f"Ticket inviato con successo e notifica Telegram spedita!"
                    )

    # ---------------------------------------------------------
    # 2. TICKETS & ORDINI DI LAVORO
    # ---------------------------------------------------------
    elif menu == "🔧 Tickets & Ordini di Lavoro":
        st.subheader(
            "Gestione Ordini di Lavoro & Interventi Tecnico-Elettromeccanici"
        )

        with get_connection() as conn:
            df_ticket = pd.read_sql_query(
                "SELECT * FROM richieste ORDER BY id DESC", conn
            )

        if df_ticket.empty:
            st.info("Nessun ordine di lavoro presente.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_stato = st.multiselect(
                    "Filtra per Stato", STATI, default=["Aperta", "In Corso"]
                )
            with col_f2:
                filtro_reparto = st.multiselect("Filtra per Reparto", REPARTI)

            df_filtrato = df_ticket.copy()
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
            st.write("### 🛠️ Gestione & Chiusura Ordine di Lavoro")

            col_id, _ = st.columns([1, 2])
            with col_id:
                id_selezionato = st.selectbox(
                    "Seleziona ID Ticket", options=df_ticket["id"].tolist()
                )

            rec = df_ticket[df_ticket["id"] == id_selezionato].iloc[0]

            st.caption(
                f"Modifica ID #{id_selezionato} | **Macchina:** {rec['macchinario']} | **Reparto:** {rec['reparto']} | **Apertura:** {rec['data_ora']}"
            )

            with st.form("form_aggiorna_odl"):
                col_u1, col_u2, col_u3 = st.columns(3)

                with col_u1:
                    nuovo_stato = st.selectbox(
                        "Stato Intervento",
                        STATI,
                        index=STATI.index(rec["stato"]),
                    )
                    nuovo_tipo = st.selectbox(
                        "Tipo Intervento",
                        TIPI_INTERVENTO,
                        index=TIPI_INTERVENTO.index(rec["tipo_intervento"])
                        if rec["tipo_intervento"] in TIPI_INTERVENTO
                        else 0,
                    )
                    tecnico = st.text_input(
                        "Tecnico MAMU Assegnato",
                        value=rec["tecnico_mam"]
                        or st.session_state["nome_utente"],
                    )

                with col_u2:
                    ore_impiegate = st.number_input(
                        "Ore Lavoro Impiegate",
                        min_value=0.0,
                        value=float(rec["ore_impiegate"]),
                        step=0.5,
                    )
                    st.caption(
                        f"Costo Manodopera: € {ore_impiegate * COSTO_ORARIO_MANODOPERA:.2f} ({COSTO_ORARIO_MANODOPERA}€/h)"
                    )

                    with get_connection() as conn:
                        df_ricambi_select = pd.read_sql_query(
                            "SELECT * FROM ricambi WHERE quantita > 0", conn
                        )

                    ricambio_scelto = st.selectbox(
                        "Aggiungi Ricambio dal Magazzino",
                        options=["Nessuno"]
                        + df_ricambi_select["nome"].tolist(),
                    )
                    qta_ricambio = st.number_input(
                        "Quantità Ricambio Usata", min_value=1, value=1, step=1
                    )

                with col_u3:
                    note = st.text_area(
                        "Note Tecniche / Dettaglio Riparazione",
                        value=rec["note_mam"] or "",
                    )

                btn_salva = st.form_submit_button(
                    "💾 Aggiorna & Salva Ordine di Lavoro"
                )

                if btn_salva:
                    costo_manodopera = ore_impiegate * COSTO_ORARIO_MANODOPERA
                    costo_ricambio_aggiunto = 0.0

                    if ricambio_scelto != "Nessuno":
                        ric_row = df_ricambi_select[
                            df_ricambi_select["nome"] == ricambio_scelto
                        ].iloc[0]
                        ric_id = int(ric_row["id"])
                        costo_un = float(ric_row["costo_unitario"])
                        costo_ricambio_aggiunto = costo_un * qta_ricambio

                        with get_connection() as conn:
                            conn.execute(
                                """
                                INSERT INTO utilizzi_ricambi (richiesta_id, ricambio_id, quantita, costo_totale)
                                VALUES (?, ?, ?, ?)
                            """,
                                (
                                    id_selezionato,
                                    ric_id,
                                    qta_ricambio,
                                    costo_ricambio_aggiunto,
                                ),
                            )
                            conn.execute(
                                "UPDATE ricambi SET quantita = quantita - ? WHERE id = ?",
                                (qta_ricambio, ric_id),
                            )

                    costo_ricambi_totale = (
                        float(rec["costo_ricambi"]) + costo_ricambio_aggiunto
                    )
                    costo_totale_finale = (
                        costo_manodopera + costo_ricambi_totale
                    )

                    chiusura_dt = rec["data_chiusura"]
                    if nuovo_stato in ["Risolta", "Annullata"]:
                        if not chiusura_dt:
                            chiusura_dt = datetime.now().strftime(
                                "%Y-%m-%d %H:%M:%S"
                            )
                    else:
                        chiusura_dt = ""

                    with get_connection() as conn:
                        conn.execute(
                            """
                            UPDATE richieste 
                            SET stato = ?, tipo_intervento = ?, tecnico_mam = ?, note_mam = ?, 
                                ore_impiegate = ?, costo_ricambi = ?, costo_totale = ?, data_chiusura = ?
                            WHERE id = ?
                        """,
                            (
                                nuovo_stato,
                                nuovo_tipo,
                                tecnico,
                                note,
                                ore_impiegate,
                                costo_ricambi_totale,
                                costo_totale_finale,
                                chiusura_dt,
                                id_selezionato,
                            ),
                        )

                    # Notifica Telegram quando un guasto viene risolto
                    if nuovo_stato == "Risolta":
                        invia_notifica_telegram(
                            f"✅ *GUASTO RISOLTO*\nTicket #{id_selezionato} per *{rec['macchinario']}* chiuso dal tecnico {tecnico}."
                        )

                    st.success(
                        f"Ordine di lavoro #{id_selezionato} aggiornato con successo!"
                    )
                    st.rerun()

    # ---------------------------------------------------------
    # 3. MANUTENZIONE PREVENTIVA
    # ---------------------------------------------------------
    elif menu == "📅 Manutenzione Preventiva":
        st.subheader(
            "Pianificazione & Schedulario Manutenzioni Preventive"
        )

        with get_connection() as conn:
            df_prev = pd.read_sql_query("SELECT * FROM piani_preventivi", conn)

        col_p1, col_p2 = st.columns([2, 1])

        with col_p1:
            st.write("### Piani di Manutenzione Attivi")
            st.dataframe(df_prev, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.write("### ⚡ Genera Ordine di Lavoro da Piano Preventivo")
            id_prev = st.selectbox(
                "Seleziona Piano da eseguire", df_prev["id"].tolist()
            )
            piano_sel = df_prev[df_prev["id"] == id_prev].iloc[0]

            if st.button("🚀 Genera Ordine di Lavoro Preventivo"):
                data_ora_apertura = datetime.now().strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                reparto_m = df_macchine_all[
                    df_macchine_all["nome"] == piano_sel["macchinario"]
                ]["reparto"].values[0]

                with get_connection() as conn:
                    conn.execute(
                        """
                        INSERT INTO richieste (data_ora, reparto, macchinario, tipo_intervento, priorita, descrizione, stato, tecnico_mam, note_mam, utente_creatore, data_chiusura, origine)
                        VALUES (?, ?, ?, 'Preventivo', 'Media', ?, 'Aperta', '', '', 'SCHEDULER_MAMU', '', 'Preventiva')
                    """,
                        (
                            data_ora_apertura,
                            reparto_m,
                            piano_sel["macchinario"],
                            f"[PREVENTIVA PROGRAMMATA] {piano_sel['titolo']}: {piano_sel['descrizione']}",
                        ),
                    )

                    nuova_scad = (
                        datetime.now()
                        + timedelta(days=int(piano_sel["frequenza_giorni"]))
                    ).strftime("%Y-%m-%d")
                    conn.execute(
                        "UPDATE piani_preventivi SET prossima_scadenza = ? WHERE id = ?",
                        (nuova_scad, id_prev),
                    )

                invia_notifica_telegram(
                    f"📅 *MANUTENZIONE PREVENTIVA AVVIATA*\nGenerato ordine di lavoro per *{piano_sel['macchinario']}*: {piano_sel['titolo']}"
                )
                st.success(
                    f"Generato con successo Ordine di Lavoro Preventivo per {piano_sel['macchinario']}!"
                )
                st.rerun()

        with col_p2:
            st.write("### ➕ Aggiungi Piano Preventivo")
            with st.form("form_nuovo_piano", clear_on_submit=True):
                m_prev = st.selectbox("Macchinario", LISTA_MACCHINE)
                titolo_p = st.text_input(
                    "Titolo Piano", placeholder="es. Controllo Filtri"
                )
                freq_giorni = st.number_input(
                    "Frequenza (Giorni)", min_value=1, value=30, step=5
                )
                desc_p = st.text_area("Descrizione Operazioni")
                scad_in = st.date_input(
                    "Prima Scadenza", datetime.now() + timedelta(days=30)
                )

                btn_p = st.form_submit_button("Crea Piano Preventivo")
                if btn_p:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO piani_preventivi (macchinario, titolo, frequenza_giorni, prossima_scadenza, descrizione)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (
                                m_prev,
                                titolo_p,
                                freq_giorni,
                                scad_in.strftime("%Y-%m-%d"),
                                desc_p,
                            ),
                        )
                    st.success("Piano preventivo inserito!")
                    st.rerun()

    # ---------------------------------------------------------
    # 4. RICAMBI & MAGAZZINO TECNICO
    # ---------------------------------------------------------
    elif menu == "📦 Ricambi & Magazzino":
        st.subheader("Gestione Giacenze Ricambi e Componenti Tecnici")

        with get_connection() as conn:
            df_ricambi = pd.read_sql_query("SELECT * FROM ricambi", conn)

        df_ricambi["Stato Scorta"] = df_ricambi.apply(
            lambda r: "⚠️ SOTTO SCORTA"
            if r["quantita"] <= r["soglia_minima"]
            else "OK",
            axis=1,
        )

        st.dataframe(df_ricambi, use_container_width=True, hide_index=True)

        col_r1, col_r2 = st.columns(2)

        with col_r1:
            st.write("### ➕ Aggiungi Nuovo Ricambio")
            with st.form("form_ricambio"):
                c_ric = st.text_input("Codice Ricambio", placeholder="RIC-999")
                n_ric = st.text_input("Nome / Descrizione Componente")
                q_ric = st.number_input(
                    "Giacenza Iniziale", min_value=0, value=5
                )
                s_ric = st.number_input(
                    "Soglia Minima Riordino", min_value=1, value=2
                )
                p_ric = st.number_input(
                    "Costo Unitario (€)", min_value=0.0, value=10.0, step=1.0
                )

                if st.form_submit_button("Salva Ricambio"):
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO ricambi (codice, nome, quantita, soglia_minima, costo_unitario)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (c_ric, n_ric, q_ric, s_ric, p_ric),
                        )
                    st.success("Ricambio registrato in magazzino!")
                    st.rerun()

        with col_r2:
            st.write("### 🔄 Carico / Riordino Magazzino")
            with st.form("form_carico"):
                id_r_carico = st.selectbox(
                    "Ricambio da Ricaricare", df_ricambi["id"].tolist()
                )
                qta_carico = st.number_input(
                    "Quantità da Aggiungere", min_value=1, value=5
                )

                if st.form_submit_button("Aggiorna Giacenza"):
                    with get_connection() as conn:
                        conn.execute(
                            "UPDATE ricambi SET quantita = quantita + ? WHERE id = ?",
                            (qta_carico, id_r_carico),
                        )
                    st.success("Giacenza aggiornata con successo!")
                    st.rerun()

    # ---------------------------------------------------------
    # 5. KPI & CONTROLLO COSTI
    # ---------------------------------------------------------
    elif menu == "📊 KPI & Controllo Costi":
        st.subheader(
            "Indicatori Chiave di Performance (KPI) & Analytics Costi"
        )

        with get_connection() as conn:
            df_kpi = pd.read_sql_query("SELECT * FROM richieste", conn)

        if df_kpi.empty:
            st.info("Nessun dato disponibile per il calcolo dei KPI.")
        else:
            df_risolte = df_kpi[
                (df_kpi["stato"] == "Risolta") & (df_kpi["data_chiusura"] != "")
            ].copy()

            mttr_str = "N/D"
            if not df_risolte.empty:
                df_risolte["dt_apertura"] = pd.to_datetime(
                    df_risolte["data_ora"], errors="coerce"
                )
                df_risolte["dt_chiusura"] = pd.to_datetime(
                    df_risolte["data_chiusura"], errors="coerce"
                )
                df_risolte["ore_totali"] = (
                    df_risolte["dt_chiusura"] - df_risolte["dt_apertura"]
                ).dt.total_seconds() / 3600
                mttr_val = df_risolte["ore_totali"].mean()
                if pd.notna(mttr_val):
                    mttr_str = f"{mttr_val:.1f} ore"

            costo_totale_azienda = df_kpi["costo_totale"].sum()
            ore_totali_lavorate = df_kpi["ore_impiegate"].sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("MTTR (Tempo Medio Riparazione)", mttr_str)
            k2.metric(
                "Costo Totale Manutenzione", f"€ {costo_totale_azienda:,.2f}"
            )
            k3.metric("Ore Manodopera Totali", f"{ore_totali_lavorate:.1f} h")
            k4.metric(
                "Interventi Preventivi vs Guasti",
                f"{len(df_kpi[df_kpi['origine']=='Preventiva'])} / {len(df_kpi[df_kpi['origine']=='Guasto'])}",
            )

            st.markdown("---")
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                st.write("**Costo Totale Manutenzione per Reparto (€)**")
                chart_costi_reparto = df_kpi.groupby("reparto")[
                    "costo_totale"
                ].sum()
                st.bar_chart(chart_costi_reparto)

            with col_g2:
                st.write("**Numero Interventi per Macchinario**")
                chart_macchine = df_kpi["macchinario"].value_counts()
                st.bar_chart(chart_macchine)

    # ---------------------------------------------------------
    # 6. DIARIO DI BORDO ASSETS (STORICO MACCHINA)
    # ---------------------------------------------------------
    elif menu == "🏭 Diario di Bordo Assets":
        st.subheader("Registro Assets & Storico Integrato Macchine")

        macchina_sel = st.selectbox(
            "Seleziona Macchinario da consultare", LISTA_MACCHINE
        )

        info_m = df_macchine_all[
            df_macchine_all["nome"] == macchina_sel
        ].iloc[0]

        c_a1, c_a2, c_a3, c_a4 = st.columns(4)
        c_a1.info(f"**Codice:** {info_m['codice']}")
        c_a2.info(f"**Reparto:** {info_m['reparto']}")
        c_a3.info(f"**Modello:** {info_m['modello']}")
        c_a4.info(f"**Anno:** {info_m['anno_installazione']}")

        st.markdown("---")
        st.write(
            f"### 📜 Cronologia Interventi e Manutenzioni per: **{macchina_sel}**"
        )

        with get_connection() as conn:
            df_storico = pd.read_sql_query(
                """
                SELECT 
                    id AS [ID Ticket],
                    data_ora AS [Data Apertura],
                    data_chiusura AS [Data Chiusura],
                    tipo_intervento AS [Tipo],
                    priorita AS [Priorità],
                    descrizione AS [Guasto / Oggetto],
                    stato AS [Stato],
                    tecnico_mam AS [Tecnico],
                    ore_impiegate AS [Ore],
                    costo_totale AS [Costo Totale €],
                    note_mam AS [Note Intervento]
                FROM richieste 
                WHERE macchinario = ? 
                ORDER BY id DESC
            """,
                conn,
                params=(macchina_sel,),
            )

        if df_storico.empty:
            st.warning(
                "Nessun intervento registrato nello storico per questa macchina."
            )
        else:
            st.dataframe(df_storico, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # 7. I MIEI INTERVENTI (Solo per Reparti)
    # ---------------------------------------------------------
    elif menu == "📋 I Miei Interventi":
        st.subheader(
            f"Richieste Manutenzione Reparto: {st.session_state['reparto_utente']}"
        )

        with get_connection() as conn:
            df_miei = pd.read_sql_query(
                """
                SELECT 
                    id AS [ID], 
                    data_ora AS [Apertura], 
                    data_chiusura AS [Chiusura], 
                    macchinario AS [Macchinario], 
                    tipo_intervento AS [Tipo], 
                    priorita AS [Priorità], 
                    descrizione AS [Descrizione], 
                    stato AS [Stato], 
                    tecnico_mam AS [Tecnico MAMU], 
                    note_mam AS [Note / Soluzione] 
                FROM richieste 
                WHERE reparto = ? 
                ORDER BY id DESC
            """,
                conn,
                params=(st.session_state["reparto_utente"],),
            )

        if df_miei.empty:
            st.info("Nessuna richiesta inserita per il tuo reparto.")
        else:
            st.dataframe(df_miei, use_container_width=True, hide_index=True)
