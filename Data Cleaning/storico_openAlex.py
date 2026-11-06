
import requests
import time
import json
import os

BASE = "https://api.openalex.org"
CURSOR_FILE = "cursor.json"                    #indice
PROGRESS_FILE = "progress_anni.json"           #per salvare i dati parziali

BASE_DIR = os.path.dirname(os.path.dirname(__file__))                 #cartella generale
INPUT_JSON = os.path.join(BASE_DIR, "Data", "merged_authors.json")    #file di input
OUTPUT_JSON = "merged_authors_updated.json"                           #file di output

SLEEP_TIME = 0.3     #per non stressare l'api

# Salvataggio cursore
def save_cursor(index):
    with open(CURSOR_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_index": index}, f, ensure_ascii=False, indent=2)
    print(f"Cursore salvato (index={index}) in {CURSOR_FILE}")

# Caricamento cursore
def load_cursor():
    if os.path.exists(CURSOR_FILE):
        with open(CURSOR_FILE, "r", encoding="utf-8") as f:
            return json.load(f).get("last_index", -1)
    return -1

# Reset del cursore e del progresso per quando il download è terminato
def reset_cursor_and_progress():
    if os.path.exists(CURSOR_FILE):
        os.remove(CURSOR_FILE)
    if os.path.exists(PROGRESS_FILE):
        os.remove(PROGRESS_FILE)
    print("Cursore e progresso resettati: lavoro completato.")

# Salvataggio del progresso
def save_progress(data):
    tmp_file = PROGRESS_FILE + ".tmp"
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp_file, PROGRESS_FILE)  # scrittura atomica
    print(f"Dati parziali salvati in {PROGRESS_FILE}")


# Caricamento del progresso
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return None

# Controllo e caricamento del file di input
def load_input_json():
    if not os.path.exists(INPUT_JSON):
        raise FileNotFoundError(f"{INPUT_JSON} non trovato")
    with open(INPUT_JSON, "r", encoding="utf-8") as f:
        return json.load(f)

### FUNZIONI PER LA PREPARAZIONE E DOWNLOAD DEI DATI ###

# Controllo dell'origine dell'istituzione
def is_italian_institution(inst_obj):
    """Controlla se un'istituzione è italiana."""
    if not inst_obj:
        return False
    country_code = inst_obj.get("country_code", "")
    if country_code == "IT":
        return True
    return False

# Ricerca autore su OpenAlex con la stringa del nome-> migliorabile inserendo id
def search_author_id(nome_cognome, known_insts):
    """Cerca un autore su OpenAlex e disambigua con overlap di istituzioni."""
    time.sleep(SLEEP_TIME)
    resp = requests.get(f"{BASE}/authors", params={"search": nome_cognome})
    data = resp.json()

    if resp.status_code != 200:
        print(f"⚠️ Errore {resp.status_code} per autore '{nome_cognome}'")
        print(f"Risposta: {resp.text[:200]}")  # primi 200 caratteri
        return None

    if not data.get("results"):
        return None

    known_insts_lower = {i.lower() for i in known_insts} #prendiamo le istituzioni già conosciute e le mettiamo in minuscolo per controllare l'overlap successivamente-> set per usare intersection dopo
    candidates = []


    for a in data["results"]:
        author_id = a.get("id")
        insts_data = []

        for aff in a.get("affiliations", []):
            inst_info = aff.get("institution", {})
            nome = inst_info.get("display_name")
            
            if nome: # Per sicurezza, si controlla che il nome esista
                insts_data.append(nome)
        
        name_insts_lower = {i.lower() for i in insts_data}
        overlap = known_insts_lower.intersection(name_insts_lower)
        score = len(overlap)
        
        candidates.append({'score': score, 
                           'nome_autore' : a.get("display_name", "").lower(), 
                           'id_autore' : author_id})

    best = max(candidates, key=lambda x: x['score'])
    
    # Si ritorna un dizionario con le informazioni principali recuperate: id autore, il suo nome e le info scaricate sulle istituzioni che presenta
    return {
        'id_autore' : best['id_autore'],
        'nome_autore' : best['nome_autore']
    }

# Prende i lavori dell'autore ritornandoli in oggetto json
def get_author_works(author_id, per_page=200, cursor=None, retries=3):
    """Scarica i works di un autore da OpenAlex, con retry in caso di errore 500."""
    for attempt in range(retries):
        try:
            time.sleep(SLEEP_TIME)
            params = {
                "filter": f"authorships.author.id:{author_id}",
                "per-page": per_page
            }
            if cursor:
                params["cursor"] = cursor

            resp = requests.get(f"{BASE}/works", params=params, timeout=30)
            resp.raise_for_status()
            return resp.json()

        except requests.exceptions.HTTPError as e:
            status = resp.status_code if 'resp' in locals() else 'N/A'
            if status == 500:
                print(f"Errore 500 (Internal Server Error) per autore {author_id} "
                      f"(tentativo {attempt+1}/{retries}) — ritento fra 5s")
                time.sleep(5)
                continue
            else:
                print(f"HTTPError {status} per autore {author_id}: {e}")
                break  # esce senza retry se non è un errore 500

        except requests.exceptions.RequestException as e:
            print(f"⚠️ Errore di rete per autore {author_id}: {e} "
                  f"(tentativo {attempt+1}/{retries})")
            time.sleep(5)
            continue

    print(f"Skip autore {author_id}: troppi errori consecutivi (max {retries})")
    return {"results": [], "meta": {}}


# Prende anche le sue affiliazioni
def get_author_affiliations(author_id):
    time.sleep(SLEEP_TIME)
    """Scarica le affiliazioni aggregate dell'autore (campo affiliations)."""
    resp = requests.get(f"{BASE}/authors/{author_id}")
    resp.raise_for_status()
    data = resp.json()
    return data.get("affiliations", [])

# Funzione da chiamare nella prossima per per aggiornare o aggiungere le istituzioni al dizionario
def merge_institution(list, new_inst):
    """
    Merge istituzione evitando duplicati.
    Se trova la stessa istituzione (per nome o ID), aggiorna i campi mancanti.
    Rimuove istituzioni con id=None se esiste la versione con ID.
    """
    new_id = new_inst.get('id')
    new_nome = new_inst.get('nome_istituzione')
    
    # Si controlla se l'istituzione esiste già sia per id che per nome
    for i, e in enumerate(list):
        existing_id = e.get('id')
        existing_nome = e.get('nome_istituzione')
        
        # Se è presente l'id
        if new_id and existing_id and existing_id == new_id:
            for k, v in new_inst.items():
                if v and not e.get(k):
                    e[k] = v
            return
        
        # Se si ha solo il nome
        if existing_nome == new_nome:
            # Se il nuovo ha ID e il vecchio no, sostituisci completamente
            if new_id and not existing_id:
                list[i] = new_inst
                return
            # Altrimenti si aggiornano solo i campi mancanti
            for k, v in new_inst.items():
                if v and not e.get(k):
                    e[k] = v
            return
    list.append(new_inst) #se l'istituzione non è stata trovata, viene aggiunta

# Funzione per aggiornare gli id delle istituzioni che erano già presenti nel dizionario per anni che non sono ricontrollati dalla funzione sopra
def update_missing_institutions(nome_autore, diz):
    """ Cerca e aggiorna gli id mancanti"""
    print("Inizio del controllo sugli id istituzionali mancanti")

    # La cache è utile per evitare chiamate inutili all'api non ricontrollando più volte la stessa istituzione
    resolved_cache = {}

    anni = diz[nome_autore].get("anno", {})

    for anno, istituzioni in anni.items():
        for istituzione in istituzioni:

                nome_istituzione = istituzione.get('nome_istituzione')
                if nome_istituzione and (istituzione.get('id') is None or istituzione.get('id') == 'null'): # si prendono solo le istituzioni con id nulla per sostituirlo
                    
                    if nome_istituzione in resolved_cache: 
                        istituzione["id"] = resolved_cache[nome_istituzione]
                        continue
                    time.sleep(SLEEP_TIME)
                    resp = requests.get(f"{BASE}/institutions", params={"search": nome_istituzione})
                    resp.raise_for_status()
                    data = resp.json()
                    results = data.get("results", [])
                    
                    if not results:
                        continue

                    best_match = None
                    for r in results:
                        if r.get("display_name", "").lower() == nome_istituzione.lower():
                            best_match = r
                            break
                    if not best_match:
                        best_match = results[0]  # fallback: primo risultato

                    inst_id = best_match.get("id")
                    if inst_id:
                        istituzione["id"] = inst_id
                        resolved_cache[nome_istituzione] = inst_id
                        print(f"ID aggiornato per '{nome_istituzione}' → {inst_id}")

# Aggiorna il dizionario originale aggiungendo gli anni mancanti e chiamando le funzioni precedenti utili allo scopo
def process_author(nome, diz):
    """Aggiorna diz[nome]['anno'] con gli anni mancanti (2000-2025) e solo istituzioni italiane."""
    tutti_anni = set(str(y) for y in range(2000, 2026))
    known_insts = []
    
    for lst in diz[nome].get("anno", {}).values():
        if lst and isinstance(lst[0], dict):
            nome_ist = lst[0].get("nome_istituzione")
            if nome_ist:
                known_insts.append(nome_ist)

    author_dict = search_author_id(nome, known_insts)
    if not author_dict or not author_dict.get('id_autore'):
        print(f"Autore non trovato o non disambiguato: {nome}")
        return

    author_id = author_dict['id_autore']
    print(f"\n🔍 Analizzo {nome} (OpenAlex ID: {author_id})")

    cursor = None
    while True:
        try:
            works_page = get_author_works(author_id, per_page=200, cursor=cursor)
        except Exception as e:
            print(f"Errore imprevisto nel recupero works per {nome} ({author_id}): {e}")
            break

        results = works_page.get("results", [])
        if not results:
            print(f"Nessun risultato per {nome} ({author_id})")
            break

        for w in results:
            pub_date = w.get("publication_date", "")
            if not pub_date:
                continue
            year = pub_date.split("-")[0]

            if year in tutti_anni:
                for au in w.get("authorships", []):
                    if au.get("author", {}).get("id") == author_id:
                        insts = []
                        for inst in au.get("institutions", []):
                            if inst.get("display_name") and is_italian_institution(inst):                        
                                insts.append({
                                    'nome_istituzione': inst.get("display_name"),
                                    'id': inst.get("id")
                                })
                        if insts:
                            existing = diz[nome].setdefault("anno", {}).get(year, [])
                            for new_inst in insts:
                                merge_institution(existing, new_inst)
                            diz[nome]['anno'][year] = existing
                            print(f"{nome} → {year}: {existing}")
                        break

        meta = works_page.get("meta", {})
        cursor = meta.get("next_cursor")
        if not cursor:
            break

    # --- Fallback sulle affiliazioni ---
    try:
        affs = get_author_affiliations(author_id)
        for aff in affs:
            inst_obj = aff.get("institution", {})
            if not inst_obj or not is_italian_institution(inst_obj):
                continue
            inst_entry = {
                'nome_istituzione': inst_obj.get("display_name"),
                'id': inst_obj.get('id')
            }
            for y in aff.get("years", []):
                y_str = str(y)
                if y_str not in tutti_anni:
                    continue
                existing = diz[nome].setdefault("anno", {}).get(y_str, [])
                merge_institution(existing, inst_entry)
                diz[nome]['anno'][y_str] = existing
                print(f"(fallback) {nome} → {y_str}: {existing}")
    except Exception as e:
        print(f"Errore nel recupero affiliazioni per {nome}: {e}")

# Funzione di recap che chiama tutte le altre
def fill_missing_years(merged_author, start_index=0):
    nomi = list(merged_author.keys())
    for i in range(start_index, len(nomi)):
        nome = nomi[i]
        print(f"\n [{i+1}/{len(nomi)}] Elaboro: {nome}")
        process_author(nome, merged_author)
    
        save_progress(merged_author)
        save_cursor(i)
    
    for nome in nomi:
        update_missing_institutions(nome, merged_author)

        # salvo progresso e cursore dopo ogni autore
        save_progress(merged_author)
        save_cursor(i)

# Funzione per la normalizzazione del dizionario precedente
def normalize_diz(diz):
    for nome, autore in diz.items():
        anni = autore.get("anno", {})
        for year, insts in anni.items():
            new_insts = []
            for inst in insts:
                if isinstance(inst, str):
                    new_insts.append({
                        'nome_istituzione': inst,
                        'id': None
                    })
                else:
                    new_insts.append(inst)
            diz[nome]["anno"][year] = new_insts


### MAIN ###
# Carica SEMPRE il file completo
merged_author = load_input_json()  # 49454 autori

progress = load_progress()
if progress:
    print(f"Trovato progresso: {len(progress)} autori già elaborati")
    # Aggiorna merged_author con i dati già scaricati
    for nome, dati in progress.items():
        if nome in merged_author:
            merged_author[nome] = dati
    start_index = load_cursor() + 1
    print(f"Riprendo da indice {start_index}")
else:
    normalize_diz(merged_author)  # Normalizza SOLO la prima volta
    start_index = 0
    print("Nessun progresso trovato, parto da zero.")

fill_missing_years(merged_author, start_index)

# Salvataggio finale
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(merged_author, f, ensure_ascii=False, indent=2)
print(f"Dizionario aggiornato salvato in {OUTPUT_JSON}")
