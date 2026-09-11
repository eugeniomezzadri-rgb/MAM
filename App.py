
import json
import os
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import hashlib
import smtplib
import sqlite3
import pandas as pd
import streamlit as st

# =========================================================
# 1. CONFIGURAZIONE EMAIL SMTP (VIA JSON)
# =========================================================
def carica_config_email():
    """Carica i dati di configurazione SMTP dal file config.json"""
    file_config = "config.json"
    if os.path.exists(file_config):
        try:
            with open(file_config, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            st.error(f"Errore nella lettura di {file_config}: {e}")
            return None
    return None

def invia_notifica_email(oggetto, contenuto_messaggio):
    """Invia un'email HTML a uno o più destinatari letti dal config.json"""
    config = carica_config_email()

    if not config:
        st.warning(
            "⚠️ File 'config.json' non trovato o non valido. Email non inviata."
        )
        return False

    smtp_server = config.get("smtp_server", "")
    smtp_port = config.get("smtp_port", 587)
    sender_email = config.get("sender_email", "")
    sender_password = config.get("sender_password", "")
    receivers = config.get("receiver_emails", [])

    if not receivers or not sender_email:
        st.warning("⚠️ Impostazioni email incomplete nel file config.json.")
        return False

    # Gestione destinatari multipli (trasforma la lista in stringa separata da virgole)
    if isinstance(receivers, list):
        to_header = ", ".join(receivers)
        lista_destinatari = receivers
    else:
        to_header = receivers
        lista_destinatari = [receivers]

    msg = MIMEMultipart()
    msg["From"] = sender_email
    msg["To"] = to_header
    msg["Subject"] = oggetto

    corpo_html = f"""
    <html>
      <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; background-color: #f4f4f4; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; padding: 25px; border-radius: 8px; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
          <h2 style="color: #0056b3; border-bottom: 2px solid #0056b3; padding-bottom: 10px; margin-top: 0;">
            🏭 MAM CMMS - Notifica Sistema
          </h2>
          <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #0056b3; margin: 20px 0; font-size: 14px;">
            {contenuto_messaggio.replace('\n', '<br>')}
          </div>
          <p style="font-size: 12px; color: #777; margin-top: 30px;">
            Messaggio automatico generato dal portale MAM CMMS. Non rispondere a questa email.
          </p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(corpo_html, "html"))

    try:
        if smtp_port == 465:
            server = smtplib.SMTP_SSL(smtp_server, smtp_port, timeout=10)
        else:
            server = smtplib.SMTP(smtp_server, smtp_port, timeout=10)
            if smtp_port == 587:
                server.starttls()

        if sender_password:
            server.login(sender_email, sender_password)

        # Invia l'email a tutta la lista di destinatari
        server.sendmail(sender_email, lista_destinatari, msg.as_string())
        server.quit()
        return True

    except Exception as e:
        st.error(f"❌ Errore durante l'invio dell'email: {e}")
        return False


# =========================================================
# 2. CONFIGURAZIONE PAGINA E COSTANTI SISTEMA
# =========================================================
st.set_page_config(
    page_title="MAM CMMS - Gestione Manutenzioni",
    page_icon="🏭",
    layout="wide",
)

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
COSTO_ORARIO_MANODOPERA = 35.0 # €/ora predefinito

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


# =========================================================
# 3. DATABASE SQLITE & STRUCT INIZIALE
# =========================================================
def get_connection():
    return sqlite3.connect("mam_cmms.db")

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

        # Dati Iniziali Demo
        cursor.execute("SELECT COUNT(*) FROM macchine")
        if cursor.fetchone()[0] == 0:
            cursor.executemany(
                """
                INSERT INTO macchine (codice, nome, reparto, modello, anno_installazione, stato)
                VALUES (?, ?, ?, ?, ?, 'Operativa')
            """,
                [
                    ("MAC-01", "Trancia Idraulica T-04", "TRANCERIA", "Schuler 200T", 2018),
                    ("MAC-02", "Isola Verniciatura V-01", "VERNICIATURA", "Gema Powder", 2020),
                    ("MAC-03", "Nastro Confezionamento C-02", "CONFEZIONAMENTO", "FlexLink", 2021),
                    ("MAC-04", "Centro Lavoro CNC A-01", "ATTREZZERIA", "Haas VF-2", 2019),
                    ("MAC-05", "Avvitatore Multimandrino M-03", "MONTAGGI", "Atlas Copco", 2022),
                    ("MAC-06", "Pressa Fissaggi F-01", "FISSAGGI", "Promeccanica", 2017),
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
            scadenza_prossima = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
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
                ],
            )

init_db()

# =========================================================
# 4. LOGIN & GESTIONE SESSIONE
# =========================================================
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
    st.title("🏭 MAM CMMS - Accesso al Portale")
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

# =========================================================
# 5. APPLICAZIONE PRINCIPALE E MENU
# =========================================================
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

    # TEST EMAIL RAPIDO
    if st.sidebar.button("📧 Test Notifica Email"):
        esito = invia_notifica_email(
            "🧪 Test Notifica - MAM CMMS",
            "Questo è un messaggio di prova dal sistema di manutenzione MAM CMMS inviato via email.",
        )
        if esito:
            st.sidebar.success("Email di prova inviata con successo!")

    st.sidebar.markdown("---")

    if st.session_state["ruolo"] == "MAM":
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
    st.title("🏭 MAM CMMS - Gestione Manutenzione Industriale")

    with get_connection() as conn:
        df_macchine_all = pd.read_sql_query("SELECT * FROM macchine", conn)
    LISTA_MACCHINE = df_macchine_all["nome"].tolist()

    # ---------------------------------------------------------
    # 1. NUOVA SEGNALAZIONE
    # ---------------------------------------------------------
    if menu == "➕ Nuova Segnalazione":
        st.subheader("Invia una nuova segnalazione di manutenzione")

        col1, col2 = st.columns(2)

        with col1:
            if st.session_state["ruolo"] == "MAM":
                reparto = st.selectbox(
                    "Reparto *", REPARTI, key="seg_reparto_sel"
                )
            else:
                reparto = st.selectbox(
                    "Reparto *",
                    options=[st.session_state["reparto_utente"]],
                    disabled=True,
                    key="seg_reparto_sel",
                )

            macchine_filtrate = df_macchine_all[
                df_macchine_all["reparto"] == reparto
            ]["nome"].tolist()

            if not macchine_filtrate:
                macchine_filtrate = LISTA_MACCHINE

            macchinario = st.selectbox(
                "Macchinario / Asset *",
                macchine_filtrate,
                key="seg_macchina_sel",
            )
            tipo_intervento = st.selectbox(
                "Tipo Intervento", TIPI_INTERVENTO, key="seg_tipo_sel"
            )

        with col2:
            priorita = st.select_slider(
                "Livello di Priorità *",
                options=PRIORITA,
                value="Media",
                key="seg_prio_sel",
            )
            descrizione = st.text_area(
                "Descrizione Guasto / Anomalia *",
                placeholder="Descrivi il problema riscontrato...",
                key="seg_desc_text",
            )

        st.markdown("---")
        submitted = st.button("🚀 Invia Richiesta a MAM", type="primary")

        if submitted:
            if not descrizione.strip():
                st.error("Inserire una descrizione del problema.")
            else:
                data_ora_apertura = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
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
                    ticket_id = cursor.lastrowid

                # NOTIFICA EMAIL
                oggetto_email = f"🚨 NUOVA SEGNALAZIONE TICKET #{ticket_id} - {reparto}"
                msg_email = (
                    f"<b>Ticket N°:</b> #{ticket_id}<br>"
                    f"<b>Reparto:</b> {reparto}<br>"
                    f"<b>Macchinario:</b> {macchinario}<br>"
                    f"<b>Tipo Intervento:</b> {tipo_intervento}<br>"
                    f"<b>Priorità:</b> {priorita}<br>"
                    f"<b>Inviato da:</b> {st.session_state['nome_utente']}<br><br>"
                    f"<b>Descrizione Anomalia:</b><br>{descrizione}"
                )
                invia_notifica_email(oggetto_email, msg_email)

                st.success(f"Ticket #{ticket_id} inviato con successo e notifica Email spedita!")

    # ---------------------------------------------------------
    # 2. TICKETS & ORDINI DI LAVORO
    # ---------------------------------------------------------
    elif menu == "🔧 Tickets & Ordini di Lavoro":
        st.subheader("Gestione Ordini di Lavoro & Interventi Tecnico-Elettromeccanici")

        with get_connection() as conn:
            df_ticket = pd.read_sql_query("SELECT * FROM richieste ORDER BY id DESC", conn)

        if df_ticket.empty:
            st.info("Nessun ordine di lavoro presente.")
        else:
            col_f1, col_f2 = st.columns(2)
            with col_f1:
                filtro_stato = st.multiselect("Filtra per Stato", STATI, default=["Aperta", "In Corso"])
            with col_f2:
                filtro_reparto = st.multiselect("Filtra per Reparto", REPARTI)

            df_filtrato = df_ticket.copy()
            if filtro_stato:
                df_filtrato = df_filtrato[df_filtrato["stato"].isin(filtro_stato)]
            if filtro_reparto:
                df_filtrato = df_filtrato[df_filtrato["reparto"].isin(filtro_reparto)]

            st.dataframe(df_filtrato, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.write("### 🛠️ Dettaglio e Chiusura Ordine di Lavoro")

            col_id, _ = st.columns([1, 2])
            with col_id:
                id_selezionato = st.selectbox("Seleziona ID Ticket", options=df_ticket["id"].tolist())

            rec = df_ticket[df_ticket["id"] == id_selezionato].iloc[0]

            st.caption(
                f"Modifica ID #{id_selezionato} | **Macchina:** {rec['macchinario']} | **Reparto:** {rec['reparto']} | **Apertura:** {rec['data_ora']}"
            )

            # --- SEZIONE GESTIONE RICAMBI MULTIPLI ---
            st.markdown("#### 📦 Ricambi Associati a questo Intervento")

            with get_connection() as conn:
                df_utilizzati = pd.read_sql_query(
                    """
                    SELECT u.id, r.nome AS [Ricambio], u.quantita AS [Q.tà], r.costo_unitario AS [Prezzo Unit. €], u.costo_totale AS [Totale €]
                    FROM utilizzi_ricambi u
                    JOIN ricambi r ON u.ricambio_id = r.id
                    WHERE u.richiesta_id = ?
                """,
                    conn,
                    params=(id_selezionato,),
                )

            if not df_utilizzati.empty:
                st.dataframe(df_utilizzati, use_container_width=True, hide_index=True)
                costo_ricambi_attuali = df_utilizzati["Totale €"].sum()
            else:
                st.caption("Nessun ricambio ancora associato a questo ticket.")
                costo_ricambi_attuali = 0.0

            # Form per aggiungere ricambi
            with st.expander("➕ Aggiungi un ricambio a questo ticket"):
                with get_connection() as conn:
                    df_ricambi_select = pd.read_sql_query("SELECT * FROM ricambi WHERE quantita > 0", conn)

                if df_ricambi_select.empty:
                    st.warning("Nessun ricambio disponibile in magazzino.")
                else:
                    with st.form(f"form_add_ricambio_{id_selezionato}", clear_on_submit=True):
                        col_r1, col_r2 = st.columns([2, 1])
                        with col_r1:
                            ric_selezionato_nome = st.selectbox("Seleziona Ricambio", df_ricambi_select["nome"].tolist())
                        with col_r2:
                            qta_add = st.number_input("Quantità", min_value=1, value=1, step=1)

                        btn_add_ric = st.form_submit_button("➕ Associa Ricambio")

                        if btn_add_ric:
                            ric_row = df_ricambi_select[df_ricambi_select["nome"] == ric_selezionato_nome].iloc[0]
                            if qta_add > ric_row["quantita"]:
                                st.error(f"Quantità non disponibile! Giacenza attuale: {ric_row['quantita']}")
                            else:
                                ric_id = int(ric_row["id"])
                                costo_un = float(ric_row["costo_unitario"])
                                costo_tot_ric = costo_un * qta_add

                                with get_connection() as conn:
                                    conn.execute(
                                        "INSERT INTO utilizzi_ricambi (richiesta_id, ricambio_id, quantita, costo_totale) VALUES (?, ?, ?, ?)",
                                        (id_selezionato, ric_id, qta_add, costo_tot_ric),
                                    )
                                    conn.execute(
                                        "UPDATE ricambi SET quantita = quantita - ? WHERE id = ?",
                                        (qta_add, ric_id),
                                    )

                                    # Aggiorna totale ricambi e costo ticket totale
                                    c_ric_tot = (
                                        conn.execute(
                                            "SELECT SUM(costo_totale) FROM utilizzi_ricambi WHERE richiesta_id = ?",
                                            (id_selezionato,),
                                        ).fetchone()[0] or 0.0
                                    )
                                    c_mano = float(rec["ore_impiegate"]) * COSTO_ORARIO_MANODOPERA
                                    conn.execute(
                                        "UPDATE richieste SET costo_ricambi = ?, costo_totale = ? WHERE id = ?",
                                        (c_ric_tot, c_mano + c_ric_tot, id_selezionato),
                                    )

                                st.success(f"Aggiunto {qta_add}x '{ric_selezionato_nome}' al ticket #{id_selezionato}!")
                                st.rerun()

            st.markdown("---")
            # --- FORM PRINCIPALE PER STATO, ORE E NOTE ---
            st.markdown("#### 📝 Stato Intervento, Ore Lavoro e Note")
            with st.form(f"form_aggiorna_odl_{id_selezionato}"):
                col_u1, col_u2 = st.columns(2)

                with col_u1:
                    nuovo_stato = st.selectbox("Stato Intervento", STATI, index=STATI.index(rec["stato"]))
                    nuovo_tipo = st.selectbox(
                        "Tipo Intervento",
                        TIPI_INTERVENTO,
                        index=TIPI_INTERVENTO.index(rec["tipo_intervento"]) if rec["tipo_intervento"] in TIPI_INTERVENTO else 0,
                    )
                    tecnico = st.text_input("Tecnico MAM Assegnato", value=rec["tecnico_mam"] or st.session_state["nome_utente"])

                with col_u2:
                    ore_impiegate = st.number_input(
                        "Ore Lavoro Impiegate",
                        min_value=0.0,
                        value=float(rec["ore_impiegate"]),
                        step=0.5,
                    )
                    costo_manodopera = ore_impiegate * COSTO_ORARIO_MANODOPERA
                    costo_totale_calcolato = costo_manodopera + costo_ricambi_attuali

                    st.info(
                        f"**Riepilogo Costi Intervento:**\n"
                        f"- Manodopera ({ore_impiegate}h × {COSTO_ORARIO_MANODOPERA}€): **€ {costo_manodopera:.2f}**\n"
                        f"- Totale Ricambi Utilizzati: **€ {costo_ricambi_attuali:.2f}**\n"
                        f"- **Costo Totale Ticket: € {costo_totale_calcolato:.2f}**"
                    )

                note = st.text_area("Note Tecniche / Dettaglio Riparazione", value=rec["note_mam"] or "")

                btn_salva = st.form_submit_button("💾 Aggiorna & Salva Ordine di Lavoro", type="primary")

                if btn_salva:
                    chiusura_dt = rec["data_chiusura"]
                    if nuovo_stato in ["Risolta", "Annullata"]:
                        if not chiusura_dt:
                            chiusura_dt = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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
                                nuovo_stato, nuovo_tipo, tecnico, note, 
                                ore_impiegate, costo_ricambi_attuali, costo_totale_calcolato, chiusura_dt, id_selezionato,
                            ),
                        )

                    # NOTIFICA EMAIL ALLA CHIUSURA
                    if nuovo_stato == "Risolta":
                        oggetto_chiusura = f"✅ TICKET #{id_selezionato} RISOLTO - MAM"
                        msg_chiusura = (
                            f"<b>Ticket N°:</b> #{id_selezionato}<br>"
                            f"<b>Macchinario:</b> {rec['macchinario']}<br>"
                            f"<b>Reparto:</b> {rec['reparto']}<br>"
                            f"<b>Tecnico MAM:</b> {tecnico}<br>"
                            f"<b>Ore Impiegate:</b> {ore_impiegate} h<br>"
                            f"<b>Costo Totale Ticket:</b> € {costo_totale_calcolato:.2f}<br><br>"
                            f"<b>Note e Soluzione Applicata:</b><br>{note if note else 'Nessuna nota specificata'}"
                        )
                        invia_notifica_email(oggetto_chiusura, msg_chiusura)

                    st.success(f"Ordine di lavoro #{id_selezionato} aggiornato con successo!")
                    st.rerun()

    # ---------------------------------------------------------
    # 3. MANUTENZIONE PREVENTIVA
    # ---------------------------------------------------------
    elif menu == "📅 Manutenzione Preventiva":
        st.subheader("Pianificazione & Schedulario Manutenzioni Preventive")

        with get_connection() as conn:
            df_prev = pd.read_sql_query("SELECT * FROM piani_preventivi", conn)

        col_p1, col_p2 = st.columns([2, 1])

        with col_p1:
            st.write("### Piani di Manutenzione Attivi")
            st.dataframe(df_prev, use_container_width=True, hide_index=True)

            st.markdown("---")
            st.write("### ⚡ Genera Ordine di Lavoro da Piano Preventivo")
            id_prev = st.selectbox("Seleziona Piano da eseguire", df_prev["id"].tolist())
            piano_sel = df_prev[df_prev["id"] == id_prev].iloc[0]

            if st.button("🚀 Genera Ordine di Lavoro Preventivo"):
                data_ora_apertura = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                reparto_m = df_macchine_all[df_macchine_all["nome"] == piano_sel["macchinario"]]["reparto"].values[0]

                with get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO richieste (data_ora, reparto, macchinario, tipo_intervento, priorita, descrizione, stato, tecnico_mam, note_mam, utente_creatore, data_chiusura, origine)
                        VALUES (?, ?, ?, 'Preventivo', 'Media', ?, 'Aperta', '', '', 'SCHEDULER_MAM', '', 'Preventiva')
                    """,
                        (
                            data_ora_apertura, reparto_m, piano_sel["macchinario"],
                            f"[PREVENTIVA PROGRAMMATA] {piano_sel['titolo']}: {piano_sel['descrizione']}",
                        ),
                    )
                    ticket_id_prev = cursor.lastrowid

                    nuova_scad = (datetime.now() + timedelta(days=int(piano_sel["frequenza_giorni"]))).strftime("%Y-%m-%d")
                    conn.execute("UPDATE piani_preventivi SET prossima_scadenza = ? WHERE id = ?", (nuova_scad, id_prev))

                invia_notifica_email(
                    f"📅 PREVENTIVA AVVIATA - TICKET #{ticket_id_prev}",
                    f"<b>Ticket N°:</b> #{ticket_id_prev}<br><b>Macchinario:</b> {piano_sel['macchinario']}<br><b>Piano:</b> {piano_sel['titolo']}",
                )
                st.success(f"Generato con successo Ordine di Lavoro #{ticket_id_prev} per {piano_sel['macchinario']}!")
                st.rerun()

        with col_p2:
            st.write("### ➕ Aggiungi Piano Preventivo")
            with st.form("form_nuovo_piano", clear_on_submit=True):
                m_prev = st.selectbox("Macchinario", LISTA_MACCHINE)
                titolo_p = st.text_input("Titolo Piano", placeholder="es. Controllo Filtri")
                freq_giorni = st.number_input("Frequenza (Giorni)", min_value=1, value=30, step=5)
                desc_p = st.text_area("Descrizione Operazioni")
                scad_in = st.date_input("Prima Scadenza", datetime.now() + timedelta(days=30))

                btn_p = st.form_submit_button("Crea Piano Preventivo")
                if btn_p:
                    with get_connection() as conn:
                        conn.execute(
                            """
                            INSERT INTO piani_preventivi (macchinario, titolo, frequenza_giorni, prossima_scadenza, descrizione)
                            VALUES (?, ?, ?, ?, ?)
                        """,
                            (m_prev, titolo_p, freq_giorni, scad_in.strftime("%Y-%m-%d"), desc_p),
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
            lambda r: "⚠️ SOTTO SCORTA" if r["quantita"] <= r["soglia_minima"] else "OK", axis=1
        )

        st.dataframe(df_ricambi, use_container_width=True, hide_index=True)

        col_r1, col_r2 = st.columns(2)

        with col_r1:
            st.write("### ➕ Aggiungi Nuovo Ricambio")
            with st.form("form_ricambio"):
                c_ric = st.text_input("Codice Ricambio", placeholder="RIC-999")
                n_ric = st.text_input("Nome / Descrizione Componente")
                q_ric = st.number_input("Giacenza Iniziale", min_value=0, value=5)
                s_ric = st.number_input("Soglia Minima Riordino", min_value=1, value=2)
                p_ric = st.number_input("Costo Unitario (€)", min_value=0.0, value=10.0, step=1.0)

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
                id_r_carico = st.selectbox("Ricambio da Ricaricare", df_ricambi["id"].tolist())
                qta_carico = st.number_input("Quantità da Aggiungere", min_value=1, value=5)

                if st.form_submit_button("Aggiorna Giacenza"):
                    with get_connection() as conn:
                        conn.execute("UPDATE ricambi SET quantita = quantita + ? WHERE id = ?", (qta_carico, id_r_carico))
                    st.success("Giacenza aggiornata con successo!")
                    st.rerun()

    # ---------------------------------------------------------
    # 5. KPI & CONTROLLO COSTI
    # ---------------------------------------------------------
    elif menu == "📊 KPI & Controllo Costi":
        st.subheader("Indicatori Chiave di Performance (KPI) & Analytics Costi")

        with get_connection() as conn:
            df_kpi = pd.read_sql_query("SELECT * FROM richieste", conn)

        if df_kpi.empty:
            st.info("Nessun dato disponibile per il calcolo dei KPI.")
        else:
            df_risolte = df_kpi[(df_kpi["stato"] == "Risolta") & (df_kpi["data_chiusura"] != "")].copy()

            mttr_str = "N/D"
            if not df_risolte.empty:
                df_risolte["dt_apertura"] = pd.to_datetime(df_risolte["data_ora"], errors="coerce")
                df_risolte["dt_chiusura"] = pd.to_datetime(df_risolte["data_chiusura"], errors="coerce")
                df_risolte["ore_totali"] = (df_risolte["dt_chiusura"] - df_risolte["dt_apertura"]).dt.total_seconds() / 3600
                mttr_val = df_risolte["ore_totali"].mean()
                if pd.notna(mttr_val):
                    mttr_str = f"{mttr_val:.1f} ore"

            costo_totale_azienda = df_kpi["costo_totale"].sum()
            ore_totali_lavorate = df_kpi["ore_impiegate"].sum()

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("MTTR (Tempo Medio Riparazione)", mttr_str)
            k2.metric("Costo Totale Manutenzione", f"€ {costo_totale_azienda:,.2f}")
            k3.metric("Ore Manodopera Totali", f"{ore_totali_lavorate:.1f} h")
            k4.metric(
                "Interventi Preventivi vs Guasti",
                f"{len(df_kpi[df_kpi['origine']=='Preventiva'])} / {len(df_kpi[df_kpi['origine']=='Guasto'])}",
            )

            st.markdown("---")
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                st.write("**Costo Totale Manutenzione per Reparto (€)**")
                chart_costi_reparto = df_kpi.groupby("reparto")["costo_totale"].sum()
                st.bar_chart(chart_costi_reparto)

            with col_g2:
                st.write("**Numero Interventi per Macchinario**")
                chart_macchine = df_kpi["macchinario"].value_counts()
                st.bar_chart(chart_macchine)

    # ---------------------------------------------------------
    # 6. DIARIO DI BORDO ASSETS
    # ---------------------------------------------------------
    elif menu == "🏭 Diario di Bordo Assets":
        st.subheader("Registro Assets & Storico Integrato Macchine")

        macchina_sel = st.selectbox("Seleziona Macchinario da consultare", LISTA_MACCHINE)

        info_m = df_macchine_all[df_macchine_all["nome"] == macchina_sel].iloc[0]

        c_a1, c_a2, c_a3, c_a4 = st.columns(4)
        c_a1.info(f"**Codice:** {info_m['codice']}")
        c_a2.info(f"**Reparto:** {info_m['reparto']}")
        c_a3.info(f"**Modello:** {info_m['modello']}")
        c_a4.info(f"**Anno:** {info_m['anno_installazione']}")

        st.markdown("---")
        st.write(f"### 📜 Cronologia Interventi e Manutenzioni per: **{macchina_sel}**")

        with get_connection() as conn:
            df_storico = pd.read_sql_query(
                """
                SELECT 
                    id AS [ID Ticket], data_ora AS [Data Apertura], data_chiusura AS [Data Chiusura],
                    tipo_intervento AS [Tipo], priorita AS [Priorità], descrizione AS [Guasto / Oggetto],
                    stato AS [Stato], tecnico_mam AS [Tecnico MAM], ore_impiegate AS [Ore],
                    costo_totale AS [Costo Totale €], note_mam AS [Note Intervento]
                FROM richieste 
                WHERE macchinario = ? 
                ORDER BY id DESC
            """,
                conn,
                params=(macchina_sel,),
            )

        if df_storico.empty:
            st.warning("Nessun intervento registrato nello storico per questa macchina.")
        else:
            st.dataframe(df_storico, use_container_width=True, hide_index=True)

    # ---------------------------------------------------------
    # 7. I MIEI INTERVENTI (Per Utenti Reparto)
    # ---------------------------------------------------------
    elif menu == "📋 I Miei Interventi":
        st.subheader(f"Richieste Manutenzione Reparto: {st.session_state['reparto_utente']}")

        with get_connection() as conn:
            df_miei = pd.read_sql_query(
                """
                SELECT 
                    id AS [ID], data_ora AS [Apertura], data_chiusura AS [Chiusura], 
                    macchinario AS [Macchinario], tipo_intervento AS [Tipo], priorita AS [Priorità], 
                    descrizione AS [Descrizione], stato AS [Stato], tecnico_mam AS [Tecnico MAM], 
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

