# -*- coding: utf-8 -*-

# ==============================================================================
# Import delle librerie necessarie
# ==============================================================================
import asyncio                   # Per la programmazione asincrona (gestione di eventi concorrenti)
import requests                  # Per effettuare richieste heartbeat a Heartchecks.io (per verificare che lo script venga eseguito)
import aiohttp                   # Per effettuare richieste HTTP asincrone (es. API Telegram)
import random                    # Per generare numeri casuali (es. tempo di attesa)
import hashlib                   # Per generare hash MD5 (identificatori univoci per le quote)
import json                      # Per leggere e scrivere dati in formato JSON (cronologia quote)
import os                        # Per interagire con il sistema operativo (es. leggere variabili d'ambiente, verificare file)
import re                        # Per utilizzare espressioni regolari (es. estrarre ID sport dall'URL)
from datetime import datetime    # Per lavorare con date e orari (es. timestamp)
from dotenv import load_dotenv   # Per caricare variabili d'ambiente da un file .env
from playwright.async_api import async_playwright # Per controllare un browser web in modo asincrono (scraping)
import gspread                   # Libreria client per interagire con Google Sheets API
from google.oauth2.service_account import Credentials # Per autenticarsi con Google API tramite service account

# ==============================================================================
# Caricamento Configurazione da Variabili d'Ambiente
# ==============================================================================
print("ℹ️ [CONFIG] Caricamento variabili d'ambiente dal file .env...")
load_dotenv() # Carica le variabili dal file .env nella directory corrente

# --- Variabili per Telegram e Cronologia ---
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") # Token API del bot Telegram
TELEGRAM_CHAT_IDS = os.getenv("TELEGRAM_CHAT_IDS").split(",") # Lista degli ID chat Telegram a cui inviare notifiche
SUPERQUOTE_HISTORY_FILE = os.getenv("SUPERQUOTE_HISTORY_FILE") # Path del file JSON per salvare la cronologia

# --- Variabili per Google Sheets ---
GOOGLE_SHEETS_CREDENTIALS_FILE = os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE") # Path del file JSON delle credenziali Google Service Account
GOOGLE_SHEETS_SPREADSHEET_ID = os.getenv("GOOGLE_SHEETS_SPREADSHEET_ID") # ID dello Spreadsheet Google Sheets (dall'URL)
GOOGLE_SHEETS_WORKSHEET_NAME = os.getenv("GOOGLE_SHEETS_WORKSHEET_NAME")

# --- Logica Abilitazione Google Sheets ---
ENABLE_GOOGLE_SHEETS = False # Flag per abilitare/disabilitare l'integrazione con Google Sheets. Inizialmente False.

# --- Validazione Variabili Essenziali ---
print("ℹ️ [CONFIG] Validazione variabili d'ambiente...")
if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS or not SUPERQUOTE_HISTORY_FILE:
    # Errore fatale se mancano le configurazioni base
    raise ValueError("❌ ERRORE FATALE: Variabili d'ambiente per Telegram/Cronologia mancanti (TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS, SUPERQUOTE_HISTORY_FILE). Controlla il file .env")
else:
    print(f"✅ [CONFIG] Variabili Telegram/Cronologia caricate. Trovati {len(TELEGRAM_CHAT_IDS)} ID chat.")

# --- Validazione Variabili Google Sheets ---
if not GOOGLE_SHEETS_CREDENTIALS_FILE or not GOOGLE_SHEETS_SPREADSHEET_ID:
    # Se mancano le variabili per Sheets, l'integrazione viene disabilitata (ma lo script continua)
    print("⚠️ [CONFIG] Variabili Google Sheets (GOOGLE_SHEETS_CREDENTIALS_FILE, GOOGLE_SHEETS_SPREADSHEET_ID) non configurate nel .env. L'aggiornamento dello spreadsheet sarà DISABILITATO.")
    ENABLE_GOOGLE_SHEETS = False
else:
    # Se le variabili ci sono, verifica che il file delle credenziali esista
    if not os.path.exists(GOOGLE_SHEETS_CREDENTIALS_FILE):
         # Errore fatale se il file specificato non esiste
         raise ValueError(f"❌ ERRORE FATALE: File credenziali Google Sheets '{GOOGLE_SHEETS_CREDENTIALS_FILE}' specificato nel .env non trovato.")
    # Se tutto è ok, abilita l'integrazione
    ENABLE_GOOGLE_SHEETS = True
    print("✅ [CONFIG] Configurazione Google Sheets trovata e valida. Integrazione ABILITATA.")

# ==============================================================================
# Costanti e Mappature
# ==============================================================================

# --- Mappa ID Sport -> Nome Sport ---
# Usata per tradurre l'ID numerico estratto dall'URL dell'icona nel nome leggibile dello sport.
SPORT_ICON_MAP = {
    '1': 'Calcio', '2': 'Ippica', '3': 'Cricket', '5': 'Speciali', '7': 'Golf',
    '8': 'Rugby', '9': 'Boxe', '10': 'Formula 1', '12': 'Tennis',
    '14': 'Snooker', '15': 'Freccette', '16': 'Baseball', '17': 'Hockey Su Ghiaccio',
    '18': 'Basket', '19': 'Rugby League', '24': 'Speedway', '36': 'Football Australiano',
    '38': 'Ciclismo', '78': 'Pallamano', '83': 'Calcio a 5'
}
print(f"ℹ️ [CONFIG] Mappa Sport caricata con {len(SPORT_ICON_MAP)} voci.")

# ==============================================================================
# Variabili Globali di Stato
# ==============================================================================

# --- Dizionario delle Superquote Attualmente Attive ---
# Mantiene traccia delle superquote rilevate come attive nell'ultimo controllo.
# Chiave: ID univoco della superquota (hash MD5). Valore: dizionario con i dettagli della quota.
active_superquotes = {}

# ==============================================================================
# Funzioni Ausiliarie
# ==============================================================================

# --- Funzione per inviare notifiche su Telegram ---
async def send_telegram_notification(message: str):
    """
    Invia un messaggio di notifica a tutte le chat ID configurate tramite il bot Telegram.

    Utilizza aiohttp per richieste asincrone non bloccanti.
    Gestisce e logga eventuali errori durante l'invio.

    :param message: Il testo del messaggio da inviare (supporta Markdown).
    """
    print(f"✉️ [TELEGRAM] Tentativo invio messaggio: '{message[:50]}...'") # Log abbreviato del messaggio
    for chat_id in TELEGRAM_CHAT_IDS:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {"chat_id": chat_id, "text": message, "parse_mode": "Markdown"}
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=payload) as response:
                    response_text = await response.text()
                    if response.status == 200:
                        print(f"✅ [TELEGRAM] Messaggio inviato con successo a chat ID: {chat_id}")
                    else:
                        # Logga un errore specifico se Telegram risponde con status non 200
                        print(f"🚨 [TELEGRAM] Errore invio a {chat_id}: Status {response.status} - Risposta: {response_text}")
        except aiohttp.ClientError as e:
            # Logga un errore generico di connessione/richiesta aiohttp
             print(f"🚨 [TELEGRAM] Errore di rete durante invio a {chat_id}: {e}")
        except Exception as e:
            # Logga qualsiasi altro errore imprevisto
             print(f"🚨 [TELEGRAM] Errore imprevisto durante invio a {chat_id}: {type(e).__name__} - {e}")

# --- Funzione per trovare i contenitori HTML delle Superquote ---
async def find_superquota_containers(page):
    """
    Cerca sulla pagina Playwright gli elementi HTML che contengono le Superquote.

    Prova una serie di selettori CSS noti per identificare i contenitori principali.
    Filtra ulteriormente per assicurarsi che contengano elementi specifici
    delle Superquote (es. icone boost, quote).

    :param page: L'oggetto Page di Playwright che rappresenta la scheda del browser.
    :return: Una lista di oggetti Locator di Playwright, ciascuno rappresentante un contenitore di Superquota trovato.
             Restituisce una lista vuota se nessun contenitore viene trovato.
    """
    print("🔎 [SCRAPER] Ricerca contenitori Superquote sulla pagina...")
    # Lista di selettori CSS usati per identificare i blocchi delle quote popolari/superquote
    container_selectors = [".pbb-PopularBetsList > div", ".pbb-SuperBetBoost-parent", ".pbb-PopularBet"]
    containers = [] # Lista per memorizzare i locator dei contenitori validi

    for selector in container_selectors:
        print(f"   - Tentativo con selettore: '{selector}'")
        elements = page.locator(selector) # Trova tutti gli elementi che matchano il selettore
        count = await elements.count() # Conta quanti elementi sono stati trovati
        print(f"     > Trovati {count} elementi potenziali.")

        if count > 0:
            temp_containers = [] # Lista temporanea per i contenitori validati di questo selettore
            # Itera su ogni elemento trovato
            for i in range(count):
                element = elements.nth(i) # Ottieni il locator del singolo elemento
                # Verifica la presenza di elementi specifici delle Superquote (es. ".pbb-SuperBetBoost")
                boost_elements = element.locator(".pbb-SuperBetBoost, .pbb-SuperBoostChevron")
                # Verifica la presenza delle quote (maggiorate o normali)
                odds_element = element.locator(".pbb-PopularBet_BoostedOdds, .pbb-PopularBet_Odds")

                # Se l'elemento contiene sia un indicatore di boost sia le quote, consideralo un contenitore valido
                if await boost_elements.count() > 0 and await odds_element.count() > 0:
                     temp_containers.append(element)

            # Se abbiamo trovato contenitori validi con questo selettore, usiamoli e interrompiamo la ricerca
            if temp_containers:
                containers = temp_containers
                print(f"✅ [SCRAPER] Trovati {len(containers)} contenitori Superquote validi usando il selettore '{selector}'.")
                break # Esce dal ciclo dei selettori una volta trovati i contenitori

    if not containers:
         print("⚠️ [SCRAPER] Nessun contenitore Superquote valido trovato sulla pagina dopo aver provato tutti i selettori.")

    return containers

# --- Funzione per mappare l'URL dell'icona allo Sport ---
def map_src_to_sport(src_url: str) -> str:
    """
    Estrae l'ID numerico dello sport dall'attributo 'src' dell'immagine dell'icona
    e lo mappa al nome dello sport corrispondente usando la mappa SPORT_ICON_MAP.

    :param src_url: L'URL dell'immagine dell'icona (es. "/path/to/1.svg").
    :return: Il nome dello sport (es. "Calcio") se l'ID è trovato e mappato.
             "Sport Sconosciuto (ID: [id])" se l'ID è estratto ma non in mappa.
             "Sport Sconosciuto (Formato URL non riconosciuto)" se l'ID non può essere estratto.
             "Sport Sconosciuto (URL vuoto)" se l'URL è vuoto o None.
    """
    if not src_url:
        print("⚠️ [MAPPER] URL icona sport vuoto o None.")
        return "Sport Sconosciuto (URL vuoto)"

    # Espressione regolare per trovare uno o più numeri (\d+) che precedono '.svg' alla fine ($) dell'URL,
    # e sono immediatamente preceduti da una barra (/). Cattura solo i numeri.
    match = re.search(r'/(\d+)\.svg$', src_url)

    if match:
        sport_id = match.group(1) # Estrae il numero (ID sport) catturato
        sport_name = SPORT_ICON_MAP.get(sport_id) # Cerca l'ID nella mappa

        if sport_name:
            # ID trovato e mappato correttamente
            return sport_name
        else:
            # ID trovato ma non presente nella mappa SPORT_ICON_MAP
            print(f"⚠️ [MAPPER] ID Sport '{sport_id}' estratto da '{src_url}', ma non presente nella mappa SPORT_ICON_MAP.")
            return f"Sport Sconosciuto (ID: {sport_id})"
    else:
        # L'URL non corrisponde al pattern atteso (es. non finisce con /numero.svg)
        print(f"⚠️ [MAPPER] Impossibile estrarre ID numerico dello sport dall'URL: {src_url}. Pattern non riconosciuto.")
        return "Sport Sconosciuto (Formato URL non riconosciuto)"

# --- Funzione per estrarre i dettagli da un contenitore Superquota ---
async def extract_superquota_info_from_container(container) -> dict:
    """
    Estrae le informazioni rilevanti (sport, partita, quote, etc.) da un singolo
    contenitore HTML di Superquota identificato da Playwright.

    Cerca elementi specifici all'interno del contenitore usando selettori CSS.
    Gestisce la possibile assenza di alcuni elementi e formatta le quote.

    :param container: L'oggetto Locator di Playwright che rappresenta il contenitore della Superquota.
    :return: Un dizionario contenente le informazioni estratte. I valori sono "N/D" (Non Disponibile)
             se un'informazione specifica non viene trovata. Le quote vengono formattate con la virgola come separatore decimale.
    """
    # Inizializza un dizionario con valori di default
    info = {
        "sport": "N/D", "dettagli": "N/D", "partita": "N/D",
        "tipo_scommessa": "N/D", "quota_non_maggiorata": "N/D",
        "quota_maggiorata": "N/D", "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S") # Timestamp di estrazione
    }
    try:
        # --- Estrazione Sport (tramite icona) ---
        icon_el = container.locator("img.pbb-PopularBet_Icon") # Trova l'elemento <img> dell'icona
        if await icon_el.count() > 0:
            try:
                icon_src = await icon_el.first.get_attribute("src") # Ottieni l'URL dall'attributo 'src'
                if icon_src:
                    info["sport"] = map_src_to_sport(icon_src) # Mappa l'URL allo sport
                else:
                    info["sport"] = "Sport (src mancante)"
                    print("⚠️ [EXTRACTOR] Trovata icona sport ma attributo 'src' è vuoto.")
            except Exception as e_icon:
                # Gestisce errori durante l'accesso all'attributo src o la mappatura
                info["sport"] = f"Sport (errore icona: {e_icon})"
                print(f"⚠️ [EXTRACTOR] Errore durante estrazione/mappatura icona sport: {e_icon}")
        else:
            # Se l'elemento icona non viene proprio trovato
            info["sport"] = "Sport (icona assente)"
            print("⚠️ [EXTRACTOR] Elemento icona sport non trovato nel contenitore.")

        # --- Estrazione Testo Descrizione Quota ---
        text_el = container.locator(".pbb-PopularBet_Text") # Trova l'elemento con la descrizione testuale
        if await text_el.count() > 0:
            info["dettagli"] = (await text_el.first.inner_text()).strip() # Estrai il testo interno e rimuovi spazi extra

        # --- Estrazione Nome Partita/Evento ---
        betline_el = container.locator(".pbb-PopularBet_BetLine") # Trova l'elemento con i dettagli della partita
        if await betline_el.count() > 0:
            info["partita"] = (await betline_el.first.inner_text()).strip()

        # --- Estrazione Tipo di Scommessa/Mercato ---
        marketname_el = container.locator(".pbb-PopularBet_MarketName") # Trova l'elemento con il nome del mercato
        if await marketname_el.count() > 0:
            info["tipo_scommessa"] = (await marketname_el.first.inner_text()).strip()

        # --- Estrazione Quota Non Maggiorata (Originale) ---
        prevodds_el = container.locator(".pbb-PopularBet_PreviousOdds") # Trova l'elemento con la quota precedente (barrata)
        if await prevodds_el.count() > 0:
            raw_odds = (await prevodds_el.first.inner_text()).strip() # Estrai il testo della quota
            # Sostituisce il punto con la virgola per uniformità/uso in Sheets (formato italiano)
            info["quota_non_maggiorata"] = raw_odds.replace('.', ',')

        # --- Estrazione Quota Maggiorata (Boosted) ---
        boosted_odds_el = container.locator(".pbb-PopularBet_BoostedOdds") # Trova l'elemento con la quota maggiorata
        if await boosted_odds_el.count() > 0:
            raw_odds = (await boosted_odds_el.first.inner_text()).strip()
            # Sostituisce il punto con la virgola
            info["quota_maggiorata"] = raw_odds.replace('.', ',')

    except Exception as e:
        # Logga un errore generico se qualcosa va storto durante l'estrazione da questo contenitore
        print(f"🚨 [EXTRACTOR] Errore durante l'estrazione dei dettagli da un contenitore: {type(e).__name__} - {e}")
        # Le informazioni già estratte (o i default "N/D") verranno comunque restituite

    return info

# --- Funzione per generare un ID univoco per una Superquota ---
def generate_superquota_id(superquota_info: dict) -> str:
    """
    Genera un identificatore univoco (hash MD5) per una Superquota basandosi
    su una combinazione dei suoi dettagli principali (partita, tipo scommessa, testo).

    Questo ID serve per tracciare la stessa Superquota tra diversi controlli,
    anche se la sua posizione sulla pagina o le quote cambiano leggermente.

    :param superquota_info: Il dizionario contenente le informazioni estratte della Superquota.
    :return: Una stringa esadecimale rappresentante l'hash MD5.
    """
    # Componenti usati per creare la stringa univoca. Usare 'N/D' se un campo non è disponibile.
    components = [
        superquota_info.get('partita', 'N/D'),
        superquota_info.get('tipo_scommessa', 'N/D'),
        superquota_info.get('dettagli', 'N/D'),
        # Nota: Le quote non vengono incluse nell'ID per permettere il tracciamento
        # anche se la quota stessa viene leggermente modificata da Bet365.
    ]
    # Unisce i componenti con un separatore per creare una singola stringa
    unique_str = "|".join(components)
    # Calcola l'hash MD5 della stringa (codificata in UTF-8) e restituisce la rappresentazione esadecimale
    return hashlib.md5(unique_str.encode('utf-8')).hexdigest()

# --- Funzione per caricare la cronologia delle Superquote da file JSON ---
def load_superquote_history() -> dict:
    """
    Carica la cronologia delle Superquote precedentemente salvate dal file JSON
    specificato in SUPERQUOTE_HISTORY_FILE.

    Gestisce il caso in cui il file non esista (restituisce dizionario vuoto)
    o contenga JSON non valido (logga errore, restituisce dizionario vuoto).

    :return: Un dizionario rappresentante la cronologia. Chiavi sono gli ID delle Superquote,
             valori sono i dizionari con i dettagli e lo stato ('attiva').
             Restituisce {} se il file non esiste o in caso di errore di lettura/parsing.
    """
    print(f"💾 [HISTORY] Tentativo di caricamento cronologia da: {SUPERQUOTE_HISTORY_FILE}")
    if os.path.exists(SUPERQUOTE_HISTORY_FILE):
        try:
            with open(SUPERQUOTE_HISTORY_FILE, 'r', encoding='utf-8') as f:
                history = json.load(f)
                print(f"✅ [HISTORY] Cronologia caricata con successo. Trovate {len(history)} voci.")
                return history
        except json.JSONDecodeError as e:
            # Errore se il file esiste ma non è JSON valido
            print(f"🚨 [HISTORY] Errore decodifica JSON nel file di cronologia: {e}. Il file potrebbe essere corrotto. Verrà creato un nuovo file vuoto al prossimo salvataggio.")
            return {} # Restituisce un dizionario vuoto per non bloccare l'esecuzione
        except Exception as e:
            # Altri errori durante la lettura del file
            print(f"🚨 [HISTORY] Errore imprevisto durante il caricamento della cronologia: {type(e).__name__} - {e}")
            return {}
    else:
        # Se il file non esiste, è la prima esecuzione o è stato cancellato
        print(f"ℹ️ [HISTORY] File cronologia '{SUPERQUOTE_HISTORY_FILE}' non trovato. Verrà creato al primo salvataggio.")
        return {} # Restituisce un dizionario vuoto

# --- Funzione per salvare la cronologia aggiornata su file JSON ---
def save_superquote_history(history: dict):
    """
    Salva il dizionario della cronologia Superquote (aggiornato) nel file JSON
    specificato in SUPERQUOTE_HISTORY_FILE.

    Sovrascrive il file esistente. Gestisce potenziali errori di scrittura.

    :param history: Il dizionario della cronologia da salvare.
    """
    print(f"💾 [HISTORY] Tentativo di salvataggio cronologia ({len(history)} voci) su: {SUPERQUOTE_HISTORY_FILE}")
    try:
        with open(SUPERQUOTE_HISTORY_FILE, 'w', encoding='utf-8') as f:
            # Salva il dizionario in formato JSON, con indentazione per leggibilità
            # ensure_ascii=False permette di salvare correttamente caratteri non ASCII (es. lettere accentate)
            json.dump(history, f, indent=2, ensure_ascii=False)
        print(f"✅ [HISTORY] Cronologia salvata con successo.")
    except IOError as e:
        # Errore durante la scrittura del file (es. permessi mancanti, disco pieno)
        print(f"🚨 [HISTORY] Errore di I/O durante il salvataggio della cronologia: {e}")
    except Exception as e:
        # Altri errori imprevisti
        print(f"🚨 [HISTORY] Errore imprevisto durante il salvataggio della cronologia: {type(e).__name__} - {e}")

# --- Funzione per aggiornare Google Sheet ---
async def update_google_sheet(sheet, worksheet_name, row_data):
    """
    Appende una nuova riga di dati al foglio di lavoro specificato in Google Sheets.

    Calcola un ID progressivo basato sul numero di righe esistenti.
    Aggiunge l'ID e placeholder vuoti per completare le colonne attese nel foglio.
    Gestisce eccezioni comuni dell'API di Google Sheets (WorksheetNotFound, APIError).

    :param sheet: L'oggetto Spreadsheet di gspread (il file Google Sheets aperto).
    :param worksheet_name: Il nome esatto (case-sensitive, inclusi spazi) del foglio di lavoro (tab) all'interno dello spreadsheet.
    :param row_data: Una lista contenente i dati da inserire nelle colonne B-H (7 elementi attesi).
                     Formato: [Data, Sport, Tipo, Dettagli, Partita, Q_non_magg, Q_magg]
    """
    # Non fare nulla se l'integrazione Sheets è disabilitata
    if not ENABLE_GOOGLE_SHEETS:
        print("ℹ️ [GSHEETS] Aggiornamento Google Sheet saltato perché la funzione è disabilitata.")
        return

    # Verifica preliminare che l'oggetto sheet sia valido
    if not sheet:
         print("🚨 [GSHEETS] Tentativo di aggiornamento Google Sheet fallito: oggetto Spreadsheet non valido (None).")
         return

    print(f"📝 [GSHEETS] Tentativo di aggiungere una riga al worksheet: '{worksheet_name}'")
    try:
        # Accedi al worksheet specifico tramite il suo nome
        worksheet = sheet.worksheet(worksheet_name)
        print(f"   - Accesso al worksheet '{worksheet.title}' riuscito.")

        # Conta le righe esistenti per determinare il prossimo ID (semplice contatore basato su righe)
        # Nota: questo metodo può essere impreciso se ci sono righe vuote o cancellate.
        # Un approccio più robusto potrebbe leggere l'ultimo ID dalla colonna A.
        num_existing_rows = len(worksheet.get_all_values()) # Ottiene tutte le righe (può essere lento per fogli grandi)
        next_id = num_existing_rows # Assume header nella riga 1, quindi il nuovo ID è il numero totale di righe attuali

        # Controllo di sicurezza sul numero di elementi nei dati ricevuti
        expected_data_columns = 7 # Colonne da B a H
        if len(row_data) != expected_data_columns:
             # Logga un errore grave se il numero di dati non corrisponde a quanto atteso
             print(f"🚨 [GSHEETS] ERRORE INTERNO: Numero di dati errato per la riga Google Sheet.")
             print(f"   - Attesi: {expected_data_columns} elementi (per colonne B-H).")
             print(f"   - Ricevuti: {len(row_data)} elementi.")
             print(f"   - Dati ricevuti: {row_data}")
             print(f"   - Riga NON aggiunta per evitare corruzione dati.")
             return # Interrompe l'operazione

        # Prepara la riga completa da inserire: [ID, Dati..., Placeholder...]
        # Le colonne attese sono 12 (da A a L): ID, 7 dati, 4 placeholder per Esito, Andamento, Picco, Drawdown
        num_placeholders = 4
        full_row = [next_id] + row_data + [""] * num_placeholders # Aggiunge l'ID e 4 stringhe vuote

        # Appende la riga al fondo del foglio
        # 'USER_ENTERED' permette a Google Sheets di interpretare i valori (es. date, numeri) come se fossero inseriti manualmente
        worksheet.append_row(full_row, value_input_option='USER_ENTERED')
        print(f"✅ [GSHEETS] Riga aggiunta con successo al worksheet '{worksheet.title}' (ID: {next_id}). Dati: {row_data}")

    except gspread.exceptions.WorksheetNotFound:
         # Errore se il nome del worksheet fornito non esiste nello spreadsheet
         print(f"🚨 [GSHEETS] ERRORE: Worksheet '{worksheet_name}' NON TROVATO nello spreadsheet '{sheet.title}'.")
         print(f"   - Controlla che il nome sia esatto (maiuscole/minuscole, spazi finali!).")
         try:
             # Logga i nomi dei fogli disponibili per aiutare la diagnosi
             available_sheets = [ws.title for ws in sheet.worksheets()]
             print(f"   - Fogli disponibili: {available_sheets}")
         except Exception as e_list:
             print(f"   - Impossibile ottenere la lista dei fogli disponibili: {e_list}")
    except gspread.exceptions.APIError as e:
        # Errore generico dell'API di Google Sheets (es. quota superata, problemi di autenticazione temporanei)
        print(f"🚨 [GSHEETS] ERRORE API Google Sheets durante l'aggiunta della riga: {e}")
        print(f"   - Dati che si tentava di inserire: {row_data}")
        # Potrebbe essere utile implementare un meccanismo di retry qui
    except Exception as e:
        # Qualsiasi altro errore imprevisto durante l'operazione
        print(f"🚨 [GSHEETS] ERRORE Sconosciuto durante l'aggiornamento di Google Sheets: {type(e).__name__} - {e}")
        print(f"   - Dati che si tentava di inserire: {row_data}")

# --- Funzione per inviare notifiche in modo sicuro (anche in caso di loop eventi chiuso) ---
async def safe_send_notification(message: str):
    """
    Tenta di inviare una notifica Telegram gestendo il caso in cui l'event loop
    principale potrebbe essere già stato chiuso (es. durante la gestione di KeyboardInterrupt).

    :param message: Il messaggio da inviare.
    """
    print(f"ℹ️ [SAFE_NOTIFY] Tentativo invio notifica sicura: '{message[:50]}...'")
    try:
        # Prova a usare l'event loop esistente se ce n'è uno in esecuzione
        loop = asyncio.get_running_loop()
        await send_telegram_notification(message)
        print("✅ [SAFE_NOTIFY] Notifica inviata tramite loop esistente.")
    except RuntimeError:
        # Se non c'è un loop in esecuzione (es. asyncio.run() è terminato)
        print("⚠️ [SAFE_NOTIFY] Nessun event loop in esecuzione. Tentativo creazione loop temporaneo...")
        try:
            # Crea un nuovo event loop temporaneo solo per inviare questa notifica
            asyncio.run(send_telegram_notification(message))
            print("✅ [SAFE_NOTIFY] Notifica inviata tramite loop temporaneo.")
        except Exception as e_run:
            print(f"🚨 [SAFE_NOTIFY] Errore durante invio notifica con loop temporaneo: {e_run}")
    except Exception as e:
        # Altri errori imprevisti durante l'invio sicuro
        print(f"🚨 [SAFE_NOTIFY] Errore imprevisto durante l'invio della notifica sicura: {type(e).__name__} - {e}")


# ==============================================================================
# Funzione Principale (main)
# ==============================================================================
async def main():
    """
    Funzione principale asincrona che orchestra l'intero processo:
    1. Inizializza la cronologia e la connessione a Google Sheets.
    2. Avvia il browser Playwright.
    3. Entra in un ciclo infinito di controllo:
        - Naviga alla pagina Bet365.
        - Trova e analizza le Superquote presenti.
        - Confronta con le quote attive note.
        - Invia notifiche per quote nuove o rimosse.
        - Aggiorna Google Sheets per le nuove quote (se abilitato).
        - Aggiorna e salva la cronologia.
        - Attende un intervallo casuale prima del ciclo successivo.
    4. Gestisce errori a livello di ciclo di controllo e di browser, con tentativi di recupero/riavvio.
    5. Gestisce la chiusura pulita del browser all'uscita.
    """
    global ENABLE_GOOGLE_SHEETS # Permette di modificare la variabile globale in caso di fallimento connessione Sheets
    global active_superquotes  # Permette di modificare il dizionario globale delle quote attive

    print("\n======================================")
    print("🚀 Avvio Script Monitoraggio Superquote")
    print(f"⏰ Ora Avvio: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("======================================\n")

    # --- Caricamento Cronologia Iniziale ---
    cronologia_superquote = load_superquote_history()
    # Popola 'active_superquotes' con le quote marcate come 'attiva: True' nella cronologia caricata
    # Si assicura che il valore sia un dizionario e 'attiva' sia esplicitamente True (booleano)
    active_superquotes = {id_sq: info for id_sq, info in cronologia_superquote.items()
                          if isinstance(info, dict) and info.get("attiva") is True}
    print(f"ℹ️ [INIT] Stato iniziale: {len(active_superquotes)} Superquote caricate come 'attive' dalla cronologia.")

    # --- Inizializzazione Connessione Google Sheets ---
    gs_sheet = None # Oggetto Spreadsheet, inizializzato a None
    if ENABLE_GOOGLE_SHEETS:
        print("ℹ️ [GSHEETS] Tentativo di connessione a Google Sheets...")
        try:
            # Definisci gli scope necessari per leggere/scrivere su Sheets e Drive (necessario per 'open_by_key')
            scopes = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive.file']
            # Crea le credenziali dall'oggetto Service Account
            creds = Credentials.from_service_account_file(GOOGLE_SHEETS_CREDENTIALS_FILE, scopes=scopes)
            # Autorizza gspread con le credenziali
            gc = gspread.authorize(creds)
            # Apri lo spreadsheet usando il suo ID
            gs_sheet = gc.open_by_key(GOOGLE_SHEETS_SPREADSHEET_ID)
            print(f"✅ [GSHEETS] Connesso con successo allo Spreadsheet: '{gs_sheet.title}'")

            # Verifica preliminare se il worksheet specificato esiste all'avvio
            try:
                # Usa il nome del worksheet definito nella configurazione
                worksheet_name_check = GOOGLE_SHEETS_WORKSHEET_NAME
                # Tenta di accedere al worksheet per verificare che esista
                gs_sheet.worksheet(worksheet_name_check)
                print(f"✅ [GSHEETS] Worksheet '{worksheet_name_check}' trovato nello spreadsheet.")
            except gspread.exceptions.WorksheetNotFound:
                # Se il worksheet non viene trovato, logga un avviso importante ma non bloccare lo script
                print(f"🚨 ATTENZIONE [GSHEETS]: Worksheet '{worksheet_name_check}' NON trovato nello spreadsheet '{gs_sheet.title}' all'avvio!")
                print(f"   - Assicurati che il nome nel file .env (o il default 'Database ') sia ESATTO.")
                try:
                     available_sheets = [ws.title for ws in gs_sheet.worksheets()]
                     print(f"   - Fogli disponibili: {available_sheets}")
                except Exception as e_list:
                     print(f"   - Impossibile ottenere la lista dei fogli: {e_list}")
                print("   - L'aggiornamento di Google Sheets fallirà se il worksheet non viene trovato durante l'esecuzione.")
            except Exception as e_ws_check:
                 print(f"🚨 ERRORE [GSHEETS]: Errore imprevisto durante la verifica del worksheet '{GOOGLE_SHEETS_WORKSHEET_NAME}': {e_ws_check}")


        except gspread.exceptions.APIError as e:
            # Errore API durante l'autenticazione o l'apertura dello sheet
            print(f"🚨 ERRORE [GSHEETS]: Errore API durante l'inizializzazione di Google Sheets: {e}")
            print("   - L'aggiornamento di Google Sheets sarà DISABILITATO per questa sessione.")
            ENABLE_GOOGLE_SHEETS = False # Disabilita GSheets per questa run
            gs_sheet = None # Assicura che gs_sheet sia None
        except FileNotFoundError:
            # Questo errore dovrebbe essere già stato catturato dalla validazione config, ma per sicurezza...
             print(f"🚨 ERRORE [GSHEETS]: File credenziali '{GOOGLE_SHEETS_CREDENTIALS_FILE}' non trovato durante l'inizializzazione.")
             print("   - L'aggiornamento di Google Sheets sarà DISABILITATO.")
             ENABLE_GOOGLE_SHEETS = False
             gs_sheet = None
        except Exception as e:
            # Qualsiasi altro errore durante la connessione a GSheets
            print(f"🚨 ERRORE [GSHEETS]: Errore sconosciuto durante la connessione a Google Sheets: {type(e).__name__} - {e}")
            print("   - L'aggiornamento di Google Sheets sarà DISABILITATO.")
            ENABLE_GOOGLE_SHEETS = False
            gs_sheet = None
    else:
        print("ℹ️ [INIT] Integrazione Google Sheets disabilitata come da configurazione.")

    # --- Gestione Avvio Browser Playwright ---
    contatore_tentativi_browser = 0
    max_tentativi_browser = 5 # Numero massimo di tentativi di riavvio del browser
    browser = None # Oggetto Browser, inizializzato a None

    async with async_playwright() as p: # Inizializza il contesto Playwright
        # Ciclo per tentare di avviare il browser, con un massimo di tentativi
        while contatore_tentativi_browser < max_tentativi_browser:
            try:
                print(f"\n🔄 [BROWSER] Tentativo {contatore_tentativi_browser + 1}/{max_tentativi_browser} di avvio del browser Chromium...")
                # Avvia il browser Chromium. headless=False mostra la finestra (utile per debug)
                # Gli 'args' sono opzioni per Chromium, spesso usati in ambienti server/Docker per evitare problemi.
                browser = await p.chromium.launch(headless=False, args=[
                        '--no-sandbox', '--disable-setuid-sandbox', '--disable-gpu',
                        '--disable-dev-shm-usage', '--window-size=1920,1080'])
                print("✅ [BROWSER] Browser avviato.")

                # Crea un nuovo contesto del browser (simile a un profilo utente)
                # Imposta uno User-Agent comune per mascherare lo script e un viewport standard.
                context = await browser.new_context(
                     user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
                     viewport={'width': 1920, 'height': 1080})
                # Aggiunge uno script per tentare di nascondere il fatto che il browser è controllato da WebDriver
                await context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
                print("✅ [BROWSER] Contesto Browser creato e configurato.")

                # Crea una nuova pagina (scheda) nel contesto
                page = await context.new_page()
                print("✅ [BROWSER] Nuova pagina creata.")

                contatore_tentativi_browser = 0 # Resetta il contatore dopo un avvio riuscito

                # =============================================
                # === INIZIO CICLO DI CONTROLLO PRINCIPALE ===
                # =============================================
                while True: # Ciclo infinito per monitorare continuamente
                    try:
                        timestamp_inizio_controllo = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                        print(f"\n ciclo ===== [{timestamp_inizio_controllo}] Inizio ciclo di controllo Superquote =====")

                        # --- Navigazione e Caricamento Pagina ---
                        target_url = "https://www.bet365.it/#/HO/" # URL della homepage di Bet365 IT
                        print(f"🌍 [NAV] Navigazione verso: {target_url}")
                        # Naviga all'URL, con timeout esteso e attesa che il DOM sia pronto
                        await page.goto(target_url, timeout=90000, wait_until="domcontentloaded")
                        print("✅ [NAV] Pagina caricata. In attesa di elementi dinamici (breve pausa)...")
                        # Breve attesa aggiuntiva per permettere il caricamento di elementi JavaScript/dinamici
                        await asyncio.sleep(5) # Pausa di 5 secondi

                        # --- Ricerca ed Estrazione Superquote ---
                        contenitori_superquote = await find_superquota_containers(page) # Trova i box delle quote
                        superquote_correnti = {} # Dizionario per le quote trovate in *questo* ciclo

                        if contenitori_superquote:
                            print(f"📊 [PROCESS] Analisi di {len(contenitori_superquote)} potenziali contenitori Superquote...")
                            # Itera su ogni contenitore trovato
                            for i, contenitore in enumerate(contenitori_superquote):
                                print(f"   - Analisi contenitore {i+1}/{len(contenitori_superquote)}...")
                                info_superquota = await extract_superquota_info_from_container(contenitore) # Estrai dati

                                # Scarta il contenitore se mancano informazioni essenziali (partita o quota maggiorata)
                                if info_superquota.get("partita", "N/D") == "N/D" or info_superquota.get("quota_maggiorata", "N/D") == "N/D":
                                    print(f"      > Scartato: mancano dati essenziali (partita o quota maggiorata).")
                                    continue # Passa al prossimo contenitore

                                # Genera l'ID univoco per questa quota
                                id_superquota = generate_superquota_id(info_superquota)
                                # Marca la quota come attiva (poiché è stata trovata ora)
                                info_superquota["attiva"] = True
                                # Aggiungi al dizionario delle quote trovate in questo ciclo
                                superquote_correnti[id_superquota] = info_superquota
                                print(f"      > Quota valida estratta: ID {id_superquota[:8]}..., Partita: {info_superquota['partita']}")

                                # --- Logica di Confronto: Nuova vs Esistente ---
                                if id_superquota not in active_superquotes:
                                    # --- NUOVA SUPERQUOTA TROVATA ---
                                    print(f"✨✨✨ [NUOVA QUOTA] Rilevata Nuova Superquota! ID: {id_superquota}")
                                    print(f"       Dettagli: Sport={info_superquota['sport']}, Partita={info_superquota['partita']}, Quota={info_superquota['quota_maggiorata']}")
                                    # Prepara il messaggio per Telegram
                                    messaggio_tg = (
                                        f"✨ NUOVA Superquota Bet365 ✨\n\n"
                                        f"⚽ *Sport:* {info_superquota['sport']}\n"
                                        f"📝 *Dettaglio:* {info_superquota['dettagli']}\n"
                                        f"🆚 *Partita:* {info_superquota['partita']}\n"
                                        f"📊 *Mercato:* {info_superquota['tipo_scommessa']}\n"
                                        f"📉 *Quota Normale:* {info_superquota['quota_non_maggiorata']}\n"
                                        f"📈 *Quota Maggiorata:* {info_superquota['quota_maggiorata']}"
                                    )
                                    # Invia notifica Telegram
                                    await send_telegram_notification(messaggio_tg)

                                    # --- AGGIORNAMENTO GOOGLE SHEETS (se abilitato) ---
                                    if ENABLE_GOOGLE_SHEETS and gs_sheet:
                                        try:
                                            # Formatta la data nel formato DD/MM/YYYY richiesto da Sheets (o preferito)
                                            data_foglio = datetime.strptime(info_superquota['timestamp'], "%Y-%m-%d %H:%M:%S").strftime("%d/%m/%Y")
                                            # Prepara la lista dei dati nell'ordine corretto per le colonne B-H
                                            riga_dati = [
                                                data_foglio,                     # Col B: Data
                                                info_superquota['sport'],          # Col C: Sport
                                                info_superquota['tipo_scommessa'], # Col D: Tipo
                                                info_superquota['dettagli'],# Col E: Dettagli
                                                info_superquota['partita'],        # Col F: Partita
                                                info_superquota['quota_non_maggiorata'], # Col G: Quota non magg.
                                                info_superquota['quota_maggiorata']      # Col H: Quota magg.
                                            ]
                                            # Chiama la funzione per aggiungere la riga allo sheet
                                            await update_google_sheet(gs_sheet, GOOGLE_SHEETS_WORKSHEET_NAME, riga_dati)
                                        except Exception as e_sheet_prep:
                                            # Logga errori durante la preparazione dei dati o la chiamata a update_google_sheet
                                            print(f"🚨 [PROCESS] Errore durante preparazione/chiamata update Google Sheets per nuova quota {id_superquota}: {e_sheet_prep}")
                                    # --- FINE AGGIORNAMENTO GOOGLE SHEETS ---

                                    # Aggiungi la nuova quota al dizionario delle quote attive (per il prossimo ciclo)
                                    active_superquotes[id_superquota] = info_superquota
                                    # Aggiungi/Aggiorna la quota nella cronologia generale, marcandola come attiva
                                    cronologia_superquote[id_superquota] = info_superquota
                                    cronologia_superquote[id_superquota]["attiva"] = True # Assicura sia marcata attiva

                                elif id_superquota in active_superquotes:
                                    # --- SUPERQUOTA ESISTENTE ANCORA PRESENTE ---
                                    # Aggiorna solo il timestamp dell'ultima vista e assicurati che sia attiva
                                    # Non serve notificare o aggiornare Sheets di nuovo
                                    print(f"      > Quota {id_superquota[:8]}... già nota e ancora attiva.")
                                    active_superquotes[id_superquota]["timestamp"] = info_superquota["timestamp"]
                                    if id_superquota in cronologia_superquote:
                                         # Aggiorna anche nella cronologia per coerenza
                                         cronologia_superquote[id_superquota]["timestamp"] = info_superquota["timestamp"]
                                         cronologia_superquote[id_superquota]["attiva"] = True
                                    # Potremmo aggiungere un controllo qui per vedere se le quote sono cambiate
                                    # e notificare l'aggiornamento, ma per ora non è richiesto.

                        else:
                            # Se la funzione find_superquota_containers non ha trovato nulla
                            print("ℹ️ [PROCESS] Nessuna Superquota trovata sulla pagina in questo ciclo.")

                        # --- Gestione Quote Rimosse ---
                        # Identifica le quote che erano nel dizionario 'active_superquotes' (dal ciclo precedente)
                        # ma non sono state trovate in 'superquote_correnti' (in questo ciclo).
                        superquote_da_rimuovere_ids = []
                        # Itera sugli ID delle quote precedentemente attive
                        for id_sq, info_sq in list(active_superquotes.items()): # Usa list() per creare una copia delle chiavi
                            if id_sq not in superquote_correnti:
                                # Questa quota non è più presente sulla pagina
                                print(f"❌❌❌ [QUOTA RIMOSSA] Superquota non più disponibile! ID: {id_sq}")
                                print(f"       Dettagli: Sport={info_sq.get('sport', 'N/D')}, Partita={info_sq.get('partita', 'N/D')}")
                                # Prepara messaggio Telegram per la rimozione
                                messaggio_rimozione = (
                                    f"❌ *Superquota NON PIÙ DISPONIBILE*\n\n"
                                    f"⚽ *Sport:* {info_sq.get('sport', 'N/D')}\n"
                                    f"📝 *Dettaglio:* {info_sq.get('dettagli', 'N/D')}\n"
                                    f"🆚 *Partita:* {info_sq.get('partita', 'N/D')}\n"
                                    f"📊 *Mercato:* {info_sq.get('tipo_scommessa', 'N/D')}\n"
                                    f"📈 *Quota Normale:* {info_sq.get('quota_non_maggiorata', 'N/D')}\n"
                                    f"📈 *Quota Maggiorata:* {info_sq.get('quota_maggiorata', 'N/D')}"
                                )
                                # Invia notifica Telegram
                                await send_telegram_notification(messaggio_rimozione)

                                # Aggiorna la cronologia marcando la quota come non più attiva
                                if id_sq in cronologia_superquote:
                                     cronologia_superquote[id_sq]["attiva"] = False
                                     print(f"       - Marcata come 'non attiva' nella cronologia.")
                                # Aggiungi l'ID alla lista di quelle da rimuovere dal dizionario 'active_superquotes'
                                superquote_da_rimuovere_ids.append(id_sq)

                        # Rimuovi effettivamente le quote non più attive da 'active_superquotes'
                        if superquote_da_rimuovere_ids:
                            print(f"ℹ️ [PROCESS] Rimozione di {len(superquote_da_rimuovere_ids)} quote non più attive da 'active_superquotes'.")
                            for id_sq in superquote_da_rimuovere_ids:
                                # Controllo di sicurezza prima della rimozione
                                if id_sq in active_superquotes:
                                     del active_superquotes[id_sq]
                            print(f"   - Stato attuale 'active_superquotes': {len(active_superquotes)} quote.")

                        # --- Salvataggio Cronologia e Attesa ---
                        save_superquote_history(cronologia_superquote) # Salva lo stato aggiornato della cronologia
                                # --- Invio Heartbeat a Healthchecks.io ---
                        HEALTHCHECK_URL = "https://hc-ping.com/bd5f718e-6cf4-4ea6-b33a-907cb31e8812"
                        try:
                            # Usiamo requests sincrono qui per semplicità, non dovrebbe bloccare molto
                            response = requests.get(HEALTHCHECK_URL, timeout=10)
                            response.raise_for_status() # Controlla se la richiesta ha avuto successo (status code 2xx)
                            print(f"💓 [HEARTBEAT] Segnale 'sono vivo' inviato con successo a Healthchecks.io.")
                        except requests.exceptions.RequestException as e_hb:
                            print(f"⚠️ [HEARTBEAT] Impossibile inviare heartbeat: {e_hb}")
                        # --- Fine Invio Heartbeat ---
                        print(f"📊 [STATO] Controllo completato. Quote attive monitorate: {len(active_superquotes)}. Cronologia salvata.")

                        # Attendi un intervallo di tempo casuale prima del prossimo controllo
                        # Questo aiuta a evitare pattern di traffico troppo regolari
                        tempo_attesa = random.uniform(75, 115) # Secondi
                        print(f"⏳ [ATTESA] Prossimo controllo tra {tempo_attesa:.1f} secondi...")
                        await asyncio.sleep(tempo_attesa) # Pausa asincrona

                    # --- Gestione Errori all'interno del Ciclo di Controllo ---
                    except Exception as e_loop:
                        # Cattura qualsiasi eccezione avvenuta durante il ciclo (navigazione, scraping, analisi...)
                        print(f"🚨🚨🚨 ERRORE nel ciclo di controllo principale: {type(e_loop).__name__} - {e_loop}")
                        # Tenta di salvare uno screenshot per diagnosi (se la pagina è accessibile)
                        try:
                           if page and not page.is_closed():
                             timestamp_errore = datetime.now().strftime('%Y%m%d_%H%M%S')
                             screenshot_path = f"error_screenshot_{timestamp_errore}.png"
                             await page.screenshot(path=screenshot_path)
                             print(f"📸 [ERRORE] Screenshot dell'errore salvato in: {screenshot_path}")
                        except Exception as e_screen:
                            print(f"⚠️ [ERRORE] Impossibile salvare lo screenshot: {e_screen}")

                        print("🔧 [RECUPERO] Tentativo di recupero dall'errore...")
                        # Pausa prima di tentare il recupero
                        await asyncio.sleep(20)

                        # Logica di Recupero: prova a ricaricare la pagina o crearne una nuova
                        try:
                            if page and not page.is_closed():
                                print("   - Tentativo di ricaricare la pagina corrente...")
                                await page.reload(timeout=75000, wait_until="domcontentloaded")
                                print("   - Pagina ricaricata. Attesa aggiuntiva...")
                                await asyncio.sleep(15) # Pausa dopo il reload
                            elif browser and context and not browser.is_closed():
                                print("   - Pagina non accessibile o chiusa. Tentativo di creare una nuova pagina...")
                                if page and not page.is_closed():
                                    await page.close() # Chiudi la vecchia pagina se possibile
                                page = await context.new_page() # Crea una nuova pagina nello stesso contesto
                                print("   - Nuova pagina creata.")
                            else:
                                # Se anche browser o contesto non sono validi, l'unica opzione è riavviare il browser
                                print("   - Browser/Contesto non disponibili. Uscita dal ciclo di controllo per tentare riavvio browser.")
                                break # Interrompe il 'while True' interno per tornare al ciclo di avvio browser
                        except Exception as errore_recupero:
                            # Se anche il tentativo di recupero fallisce
                            print(f"🚨 [RECUPERO] Fallito anche il tentativo di recupero: {errore_recupero}")
                            # Se il browser è chiuso, esci per tentare il riavvio
                            if not browser or browser.is_closed():
                                print("   - Browser non disponibile. Uscita per riavvio.")
                                break
                            # Altrimenti, attendi un po' di più prima di riprovare il ciclo principale
                            print("   - Errore durante recupero, attesa più lunga prima del prossimo ciclo...")
                            await asyncio.sleep(45)
                            # Il ciclo 'while True' esterno continuerà...

                # ===========================================
                # === FINE CICLO DI CONTROLLO PRINCIPALE ===
                # ===========================================
                # Se si esce dal ciclo 'while True' interno (es. per riavviare il browser),
                # chiudi il browser corrente se è ancora aperto.
                print("ℹ️ [BROWSER] Uscita dal ciclo di controllo principale.")
                if browser and not browser.is_closed():
                    print("   - Chiusura browser corrente...")
                    await browser.close()
                    print("   - Browser chiuso.")
                break # Esce dal ciclo 'while contatore_tentativi_browser < max_tentativi_browser' perché il browser ha funzionato per un po'

            # --- Gestione Errori durante l'Avvio/Gestione del Browser ---
            except Exception as errore_browser:
                # Cattura errori gravi che impediscono l'avvio o la gestione base del browser
                contatore_tentativi_browser += 1
                print(f"🚨🚨🚨 ERRORE GRAVE BROWSER (Tentativo {contatore_tentativi_browser}/{max_tentativi_browser}): {type(errore_browser).__name__} - {errore_browser}")
                # Tenta di chiudere il browser se esiste e non è già chiuso
                if browser and not browser.is_closed():
                    try:
                        print("   - Tentativo chiusura browser dopo errore...")
                        await browser.close()
                        print("   - Browser chiuso.")
                    except Exception as e_close:
                        print(f"   - Errore durante la chiusura forzata del browser: {e_close}")
                browser = None # Resetta la variabile browser

                # Se non si è ancora raggiunto il massimo dei tentativi
                if contatore_tentativi_browser < max_tentativi_browser:
                    # Attendi un tempo crescente prima di riprovare
                    tempo_attesa_riavvio = 60 * contatore_tentativi_browser # 60s, 120s, 180s...
                    print(f"⏳ [RECUPERO] Attesa di {tempo_attesa_riavvio} secondi prima di ritentare l'avvio del browser...")
                    await asyncio.sleep(tempo_attesa_riavvio)
                else:
                    # Massimo tentativi raggiunto, lo script non può continuare
                    print(f"‼️ [FATALE] Numero massimo di tentativi ({max_tentativi_browser}) per l'avvio del browser raggiunto. Impossibile continuare.")
                    messaggio_errore_fatale = f"ERRORE CRITICO: Lo script non è riuscito ad avviare/mantenere il browser dopo {max_tentativi_browser} tentativi. Intervento manuale necessario."
                    # Invia notifica Telegram dell'errore fatale
                    await safe_send_notification(messaggio_errore_fatale)
                    break # Esce dal ciclo 'while contatore_tentativi_browser < max_tentativi_browser'

        # --- Fine Script ---
        print("\n======================================")
        print("🏁 Script Monitoraggio Superquote terminato.")
        # Assicurati che il browser sia chiuso all'uscita finale
        if browser and not browser.is_closed():
            print("   - Chiusura finale del browser...")
            await browser.close()
        timestamp_fine = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"⏰ Ora Termine: {timestamp_fine}")
        print("======================================\n")


# ==============================================================================
# Blocco di Esecuzione (Entry Point)
# ==============================================================================
if __name__ == "__main__":
    try:
        # Avvia l'esecuzione della funzione asincrona principale 'main'
        asyncio.run(main())
    except KeyboardInterrupt:
        # Gestisce l'interruzione manuale da tastiera (Ctrl+C)
        print("\n🛑 [INTERRUZIONE] Rilevata interruzione da tastiera (Ctrl+C).")
        print("   - Invio notifica di arresto...")
        # Invia una notifica Telegram sicura per segnalare l'arresto manuale
        asyncio.run(safe_send_notification("ℹ️ Script Superquote Interrotto Manualmente (Ctrl+C)."))
        print("   - Notifica inviata (o tentativo effettuato). Uscita pulita.")
    except Exception as e_fatal:
        # Cattura qualsiasi altra eccezione non gestita che potrebbe verificarsi
        # al di fuori del ciclo principale o durante l'inizializzazione/chiusura.
        print(f"\n‼️‼️‼️ ERRORE FATALE NON GESTITO: {type(e_fatal).__name__} - {e_fatal}")
        # Tenta di inviare una notifica Telegram sull'errore fatale
        print("   - Invio notifica errore fatale...")
        messaggio_fatale = f"🚨 ERRORE FATALE Script Superquote: {type(e_fatal).__name__} - {e_fatal}"
        asyncio.run(safe_send_notification(messaggio_fatale))
        print("   - Notifica errore fatale inviata (o tentativo effettuato). Uscita.")
    finally:
        # Codice che viene eseguito sempre alla fine, sia in caso di successo che di errore o interruzione
        print("\n👋 Esecuzione terminata.")