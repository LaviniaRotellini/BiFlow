import requests
import json
import time
import os
import urllib.parse

BASE_URL = "https://api.openalex.org/works"
FILTER = "institutions.country_code:IT,from_publication_date:2000-01-01,to_publication_date:2025-12-31"
PER_PAGE = 200
CURSOR_FILE = "cursor.txt"
PROGRESS_FILE = "progress.json"
OUTPUT_DIR = "openalex_macroareas_json"

os.makedirs(OUTPUT_DIR, exist_ok=True)

def load_progress():
    """
    Carica lo stato di avanzamento da progress.json.
    """
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            try:
                progress = json.load(f)
                return progress.get("total_downloaded", 0)
            except json.JSONDecodeError:
                return 0
    return 0

def save_progress(total_downloaded):
    """
    Salva lo stato di avanzamento su progress.json.
    """
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump({"total_downloaded": total_downloaded}, f, ensure_ascii=False, indent=2)

def fetch_openalex_with_cursor(filter_query, per_page=200):
    """
    Generator che scarica i dati da OpenAlex pagina per pagina usando il cursore.
    Salva il cursore in cursor.txt per riprendere dopo un'interruzione.
    """
    try:
        with open(CURSOR_FILE, "r") as f:
            cursor = f.read().strip()
        if cursor:
            print(f"🔄 Ripartendo dal cursore salvato: {cursor}")
        else:
            cursor = "*"
            print("🚀 Parto dall'inizio (cursore vuoto).")
    except FileNotFoundError:
        cursor = "*"
        print("🚀 Parto dall'inizio (nessun cursore trovato).")

    total_count = None

    while True:
        url = f"{BASE_URL}?filter={filter_query}&per-page={per_page}&cursor={urllib.parse.quote(cursor)}"
        response = requests.get(url)
        if response.status_code != 200:
            print(f"❌ Errore {response.status_code}: {response.text}")
            break

        data = response.json()

        if total_count is None:
            total_count = data.get("meta", {}).get("count", 0)
            print(f"📊 Numero totale di lavori previsti: {total_count}")

        results = data.get("results", [])
        if not results:
            print("✅ Nessun altro risultato.")
            break

        # Aggiorna cursore
        next_cursor = data.get("meta", {}).get("next_cursor")
        if next_cursor and next_cursor != "null":
            with open(CURSOR_FILE, "w") as f:
                f.write(next_cursor)
        else:
            print("✅ Tutti i dati scaricati. Cursore finale raggiunto.")
            cursor = None

        yield results, total_count

        if not next_cursor or next_cursor == "null":
            break

        cursor = next_cursor
        time.sleep(1)

def append_to_json(filename, new_data):
    """
    Aggiunge nuove opere al file JSON corrispondente.
    """
    if os.path.exists(filename):
        with open(filename, "r", encoding="utf-8") as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                data = {}
    else:
        data = {}

    data.update(new_data)

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def process_and_save_batch(batch):
    """
    Processa un lotto di risultati e li salva nei JSON divisi per la PRIMA macroarea trovata.
    """
    for work in batch:
        title = work.get("title", "Untitled")
        year = work.get("publication_year", "")
        concepts = work.get("concepts", [])

        # Prende solo le discipline di livello 0
        macroareas = [c.get("display_name") for c in concepts if c.get("level", 0) == 0]
        if not macroareas:
            macroareas = ["Unknown"]

        # Usa solo la prima disciplina
        primary_macroarea = macroareas[0]

        authors_list = []
        for auth in work.get("authorships", []):
            for inst in auth.get("institutions", []):
                if inst.get("country_code") == "IT":
                    authors_list.append((auth["author"].get("display_name", ""),
                                         inst.get("display_name", "")))

        if not authors_list:
            continue  # Salta se non ci sono autori italiani

        record = {
            title: {
                "publication_year": year,
                "macroareas": macroareas,  # manteniamo comunque tutte le macroaree in metadati
                "authors": authors_list
            }
        }

        # Salva solo nel file della prima disciplina
        filename = os.path.join(OUTPUT_DIR, f"{primary_macroarea.replace(' ', '_')}.json")
        append_to_json(filename, record)


if __name__ == "__main__":
    total_downloaded = load_progress()
    print(f"🔹 Record già scaricati: {total_downloaded}")

    for batch, total_count in fetch_openalex_with_cursor(FILTER, per_page=PER_PAGE):
        process_and_save_batch(batch)
        total_downloaded += len(batch)
        save_progress(total_downloaded)

        percent = (total_downloaded / total_count) * 100 if total_count else 0
        print(f"📥 Salvati {total_downloaded}/{total_count} lavori ({percent:.2f}%) finora...")

    print(f"✅ Download completato. Dati salvati in: {OUTPUT_DIR}")
