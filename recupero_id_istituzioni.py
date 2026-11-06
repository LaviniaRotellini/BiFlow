import json
import requests
import time
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

SLEEP_TIME = 0.3
BASE_URL = "https://api.openalex.org"


class OpenAlexInstitutionEnricher:
    def __init__(
        self,
        input_file: str = 'Costruzione e Analisi DF/Recupero id istituzioni/istituzioni_senza_id.json',
        output_file: str = 'istituzioni_con_id.json',
        checkpoint_file: str = "istituzioni_senza_id_checkpoint.json"
    ):
        self.input_file = input_file
        self.output_file = output_file
        self.checkpoint_file = checkpoint_file

        self.delay_between_requests = 0.3
        self.max_retries = 3
        self.retry_delay = 2

    # ---------------- CHECKPOINT ----------------

    def _new_checkpoint(self) -> Dict[str, Any]:
        return {
            "last_processed_index": -1,
            "last_processed_institution": None,
            "total_processed": 0,
            "total_found": 0,
            "total_not_found": 0,
            "started_at": datetime.now().isoformat(),
            "last_update": datetime.now().isoformat()
        }

    def load_checkpoint(self) -> Dict[str, Any]:
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, "r", encoding="utf-8") as f:
                    ck = json.load(f)
                print(f"✓ Checkpoint caricato (ultimo indice: {ck['last_processed_index']})")
                return ck
            except Exception as e:
                print(f"⚠ Checkpoint corrotto: {e}")
        return self._new_checkpoint()

    # ---------------- SAFE SAVE ----------------

    def safe_save_json(self, data: Dict, filepath: str):
        tmp = filepath + ".tmp"
        bak = filepath + ".backup"

        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if os.path.exists(filepath):
            shutil.copy2(filepath, bak)

        shutil.move(tmp, filepath)

        if os.path.exists(bak):
            os.remove(bak)

    # ---------------- OPENALEX API - SEARCH ----------------

    def search_institution_by_name(self, institution_name: str) -> Optional[str]:
        """Cerca un'istituzione per nome e restituisce il suo OpenAlex ID"""
        url = f"{BASE_URL}/institutions"
        
        headers = {
            "User-Agent": "InstitutionEnricher/1.0 (mailto:lavinia.rotellini@gmail.com)",
            "Accept": "application/json"
        }
        
        params = {
            "search": institution_name
        }

        for attempt in range(self.max_retries):
            try:
                r = requests.get(url, headers=headers, params=params, timeout=10)
                
                if r.status_code == 200:
                    data = r.json()
                    results = data.get("results", [])
                    
                    if not results:
                        print(f"  ⚠ Nessun risultato trovato")
                        return None
                    
                    # Cerca un match esatto
                    best_match = None
                    for result in results:
                        display_name = result.get("display_name", "")
                        if display_name.lower() == institution_name.lower():
                            best_match = result
                            print(f"  ✓ Match esatto trovato: {display_name}")
                            break
                    
                    # Se non c'è match esatto, usa il primo risultato
                    if not best_match:
                        best_match = results[0]
                        print(f"  ~ Usando primo risultato: {best_match.get('display_name')}")
                    
                    return best_match.get("id")
                
                elif r.status_code == 429:
                    print(f"  ⚠ Rate limit raggiunto, attendo {self.retry_delay * 2}s...")
                    time.sleep(self.retry_delay * 2)
                    continue
                    
            except requests.RequestException as e:
                print(f"  ✗ Errore richiesta (tentativo {attempt + 1}/{self.max_retries}): {e}")
                
            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        return None

    # ---------------- MAIN PROCESS ----------------

    def enrich_with_ids(self):
        """Cerca e aggiunge gli ID OpenAlex per ogni istituzione"""
        print("=" * 70)
        print("RICERCA ID OPENALEX PER ISTITUZIONI")
        print("=" * 70)

        # Carica il dizionario delle istituzioni
        with open(self.input_file, "r", encoding="utf-8") as f:
            institutions = json.load(f)

        checkpoint = self.load_checkpoint()

        # Carica output esistente se presente
        if os.path.exists(self.output_file):
            with open(self.output_file, "r", encoding="utf-8") as f:
                enriched = json.load(f)
        else:
            enriched = {}

        # Cache per evitare ricerche duplicate
        resolved_cache = {}

        items = list(institutions.items())
        start = checkpoint["last_processed_index"] + 1
        total = len(items)

        print(f"\nTrovate {total} istituzioni da processare")
        print(f"Riprendo dall'indice {start}\n")

        for idx in range(start, total):
            institution_name, institution_data = items[idx]
            
            print(f"[{idx+1}/{total}] {institution_name}")

            # Controlla se già presente nella cache
            if institution_name in resolved_cache:
                openalex_id = resolved_cache[institution_name]
                print(f"  ✓ ID dalla cache: {openalex_id}")
            else:
                # Cerca l'ID su OpenAlex
                openalex_id = self.search_institution_by_name(institution_name)
                
                if openalex_id:
                    resolved_cache[institution_name] = openalex_id
                    checkpoint["total_found"] += 1
                else:
                    checkpoint["total_not_found"] += 1

            # Crea la struttura arricchita
            enriched_inst = institution_data.copy()
            enriched_inst["openalex_id"] = openalex_id
            enriched_inst["original_name"] = institution_name
            
            enriched[institution_name] = enriched_inst

            # Aggiorna checkpoint
            checkpoint.update({
                "last_processed_index": idx,
                "last_processed_institution": institution_name,
                "total_processed": checkpoint["total_processed"] + 1,
                "last_update": datetime.now().isoformat()
            })

            # Salva progresso
            self.safe_save_json(enriched, self.output_file)
            self.safe_save_json(checkpoint, self.checkpoint_file)

            # Rispetta i rate limits
            time.sleep(self.delay_between_requests)

        print("\n" + "=" * 70)
        print("✓ COMPLETATO")
        print("=" * 70)
        print(f"Totale processate: {checkpoint['total_processed']}")
        print(f"ID trovati: {checkpoint['total_found']}")
        print(f"ID non trovati: {checkpoint['total_not_found']}")


def main():
    enricher = OpenAlexInstitutionEnricher()
    try:
        enricher.enrich_with_ids()

    except KeyboardInterrupt:
        print("\n\n⚠ Interruzione manuale rilevata")
        print("✓ Il progresso è stato salvato, puoi riprendere in qualsiasi momento")

    except Exception as e:
        print(f"\n\n✗ Errore critico: {e}")
        import traceback
        traceback.print_exc()
        print("✓ Il progresso dovrebbe essere salvato, controlla i file")


if __name__ == '__main__':
    main()