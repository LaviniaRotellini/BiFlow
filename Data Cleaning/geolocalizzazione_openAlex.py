import requests
import json
import time
import os

BASE = "https://api.openalex.org"
CURSOR_FILE = "cursor_geo_oa.json"
PROGRESS_FILE = "progress_geolocalizzazioni.json"

BASE_DIR = os.path.dirname(os.path.dirname(__file__))    
INPUT_JSON = os.path.join(BASE_DIR, "progress_anni.json")
OUTPUT_JSON = "istituzioni_localizzate.json"

SLEEP_TIME = 0.3
EMAIL = "l.rotellini@studenti.unipi.it"

# Salvataggio cursore
def save_cursor(index):
    with open(CURSOR_FILE, "w") as f:
        json.dump({'ultimo_indice': index}, f, indent=2)
    print(f"Cursore salvato ad indice: {index} in {CURSOR_FILE}")

# Caricamento cursore
def load_cursor():
    if os.path.exists(CURSOR_FILE):
        with open(CURSOR_FILE, "r") as f:
            return json.load(f).get('ultimo_indice', -1)
    return -1
    
# Salvataggio del progresso
def save_progress(data):
    with open(PROGRESS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    print(f'Dati parziali salvati in {PROGRESS_FILE}')

# Caricamento del progresso
def load_progress():
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r") as f:
            return json.load(f)
    return None

# Controllo e caricamento del file di input
def load_input_file():
    if not os.path.exists(INPUT_JSON):
        raise FileNotFoundError(f"{INPUT_JSON} non trovato")
    with open(INPUT_JSON, 'r') as f:
        dictionary = json.load(f)
    return dictionary
    
### FUNZIONI PER IL RECUPERO DELLE INFO E IL DOWNLOAD DEI DATI ####

# Funzione per la chiamata API
def get_geo_infos(id):
    time.sleep(SLEEP_TIME)

    if id.startswith("https://openalex.org/"):
        id = id.replace("https://openalex.org/", "")

    url = f"{BASE}/institutions/{id}"
    params = {
        "mailto": "l.rotellini@studenti.unipi.it"
    }

    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        geo = data.get('geo', None)
        return geo
    
    except requests.exceptions.RequestException as e:
        print(f"Errore nella richiesta per {id}: {e}")
        return None

# Funzione che prende l'id di una istituzione, chiama get_geo_infos e inserisce ogni risultato in un dizionario
def get_infos(dictionary, start_index = 0):
    cached_institutions = {}
    localized_institutions = {}
    index = 0

    for author, information in dictionary.items():
        istituzioni_per_anno = information.get('anno', {})

        for anno, istituzioni in istituzioni_per_anno.items():
            for istituzione in istituzioni:
                if index < start_index:
                    index += 1
                    continue
                
                print(f'Inizio processing {istituzione}')
                id_istituzione = istituzione.get('id')
                if not id_istituzione:
                    index += 1
                    continue
            
                if id_istituzione in cached_institutions:
                    results = cached_institutions[id_istituzione] 

                else:
                    results = get_geo_infos(id_istituzione)
                    if results:
                        localized_institutions[id_istituzione] = {
                            'informazioni_geografiche': results,
                            'nome': istituzione.get('nome_istituzione')} 
                        cached_institutions[id_istituzione] = results

                if index % 10 == 0:
                    save_cursor(index)
                    save_progress(localized_institutions)

                index += 1
                print(f"Lavoro completato per {istituzione}")
    return localized_institutions
        



### MAIN ###
progress = load_progress()
if progress:
    progress_anni = progress
    start_index = load_cursor() + 1
    print(f"Ripresa del codice da indice {start_index}")
else:
    progress_anni = load_input_file()
    start_index = 0
    print("Nessun progresso trovato, parto da zero")

localized_institutions = get_infos(progress_anni, start_index)

with open('localized_institutions.json', 'w') as f:
    json.dump(localized_institutions, f, indent=2)

print("Esecuzione terminata")