import requests
import json
import os
import time
from requests.exceptions import RequestException

BASE_URL = "https://api.openalex.org/works"
CHECKPOINT_FILE = "macroaree_by_institution_per_anno.json"
REQUEST_DELAY = 0.15
MAX_RETRIES = 5
TIMEOUT = 30
MAILTO = "lavinia.rotellini@gmail.com"

with open('/Users/laviniarotellini/Desktop/Tesi/Recupero paper/enriched_institutions_final.json', 'r') as outfile:
    institutions_dict = json.load(outfile)

def atomic_write_json(data, filepath):
    temp_path = filepath + ".tmp"
    with open(temp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(temp_path, filepath)

def load_checkpoint(filepath):
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def get_articles_by_macroarea_and_year(institution_id_full, year):
    """Query OpenAlex per una singola istituzione e anno"""
    params = {
        "filter": (
            f"institutions.id:{institution_id_full},"
            f"from_publication_date:{year}-01-01,"
            f"to_publication_date:{year}-12-31"
        ),
        "group_by": "primary_topic.domain.id",
        "mailto": MAILTO
    }
    
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            response = requests.get(BASE_URL, params=params, timeout=TIMEOUT)
            
            if response.status_code == 429:
                print(f"⏳ Rate limit, attendo {2 ** attempt}s...")
                time.sleep(2 ** attempt)
                continue
                
            if response.status_code >= 400:
                print(f"❌ Errore {response.status_code} per {institution_id_full} ({year})")
                print(response.url)
                print(response.text)
                response.raise_for_status()
            
            data = response.json()
            result = {}
            
            for group in data.get("group_by", []):
                result[group["key"]] = {
                    "macroarea": group["key_display_name"],
                    "count": group["count"]
                }
            
            return result
            
        except RequestException as e:
            if attempt == MAX_RETRIES:
                print(f"❌ Fallito dopo {MAX_RETRIES} tentativi: {e}")
                raise
            time.sleep(2 ** attempt)
    
    return {}

def build_macroarea_dictionary(institutions_dict):
    final_dict = load_checkpoint(CHECKPOINT_FILE)
    years = [2020, 2021, 2022, 2023, 2024]
    
    total_institutions = len(institutions_dict)
    processed = 0
    
    for inst_name, inst_data in institutions_dict.items():
        processed += 1
        inst_id_full = inst_data.get("id") or inst_data.get("openalex_id")
        
        if not inst_id_full:
            print(f"⚠️ ID OpenAlex mancante per {inst_name}, salto.")
            continue
        
        # Inizializza la struttura se non esiste
        if inst_id_full not in final_dict:
            final_dict[inst_id_full] = {
                "institution_name": inst_name,
                "years": {}
            }
        
        # Skip anni già elaborati
        for year in years:
            if str(year) in final_dict[inst_id_full]["years"]:
                continue
            
            print(f"📊 [{processed}/{total_institutions}] {inst_name} - Anno {year}")
            
            # Query per singolo anno
            macroareas = get_articles_by_macroarea_and_year(inst_id_full, year)
            
            # Salva risultato
            final_dict[inst_id_full]["years"][str(year)] = macroareas
            
            # Salvataggio incrementale
            atomic_write_json(final_dict, CHECKPOINT_FILE)
            time.sleep(REQUEST_DELAY)
    
    return final_dict

# Esegui
print("🚀 Inizio elaborazione...")
final_dict = build_macroarea_dictionary(institutions_dict)
print(f"\n✅ Completato! {len(final_dict)} istituzioni elaborate")

# Stampa statistiche finali
total_papers = 0
for inst_id, inst_data in final_dict.items():
    for year, macroareas in inst_data["years"].items():
        for domain_id, domain_data in macroareas.items():
            total_papers += domain_data["count"]

print(f"📈 Totale paper raccolti: {total_papers}")