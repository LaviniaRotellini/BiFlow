import json
import requests
import time
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional


class OpenAlexInstitutionEnricher:
    def __init__(
        self,
        input_file: str = 'Geolocalizzazione ed Enrichment delle Istituzioni/Geoloc e enrichment finali/istituzioni_con_id.json',
        output_file: str = 'progress_geolocalizzazioni_istituzioni_senza_id.json',
        checkpoint_file: str = "institution_enrichment_checkpoint.json"
    ):
        self.input_file = input_file
        self.output_file = output_file
        self.checkpoint_file = checkpoint_file

        self.delay_between_requests = 0.11
        self.max_retries = 3
        self.retry_delay = 2

    # ---------------- CHECKPOINT ----------------

    def _new_checkpoint(self) -> Dict[str, Any]:
        return {
            "last_processed_index": -1,
            "last_processed_institution": None,
            "total_processed": 0,
            "total_errors": 0,
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

    # ---------------- OPENALEX API ----------------

    def fetch_institution_data(self, openalex_id: str) -> Optional[Dict[str, Any]]:
        inst_id = openalex_id.rstrip("/").split("/")[-1]
        url = f"https://api.openalex.org/institutions/{inst_id}"

        headers = {
            "User-Agent": "InstitutionEnricher/1.0 (mailto:lavinia.rotellini@gmail.com)",
            "Accept": "application/json"
        }

        for attempt in range(self.max_retries):
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code == 200:
                    return r.json()
                elif r.status_code == 404:
                    return None
            except requests.RequestException:
                pass

            time.sleep(self.retry_delay)

        return None

    # ---------------- EXTRACTION ----------------

    def extract_features(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "informazioni_geografiche": api_data.get("geo", None),
            "counts_by_year": api_data.get("counts_by_year", None),
            "cited_by_count": api_data.get("cited_by_count", None),
            "works_count": api_data.get("works_count", None),
            "is_super_system": api_data.get("is_super_system", None),
            "roles": api_data.get("roles", None),
            "summary_stats": api_data.get("summary_stats", None),
            "type": api_data.get("type", None)
        }

    # ---------------- MAIN PROCESS ----------------

    def enrich(self):
        print("=" * 70)
        print("OPENALEX INSTITUTION ENRICHMENT")
        print("=" * 70)

        with open(self.input_file, "r", encoding="utf-8") as f:
            institutions = json.load(f)

        checkpoint = self.load_checkpoint()

        if os.path.exists(self.output_file):
            with open(self.output_file, "r", encoding="utf-8") as f:
                enriched = json.load(f)
        else:
            enriched = {}

        items = list(institutions.items())
        start = checkpoint["last_processed_index"] + 1
        total = len(items)

        for idx in range(start, total):
            name, data = items[idx]
            openalex_id = data.get("openalex_id")

            print(f"\n[{idx+1}/{total}] {name}")

            if not openalex_id:
                print("  ⚠ ID mancante")
                checkpoint["total_errors"] += 1
                continue

            api_data = self.fetch_institution_data(openalex_id)

            enriched_inst = data.copy()

            if api_data:
                enriched_inst.update(self.extract_features(api_data))
                print("  ✓ Arricchita")
            else:
                enriched_inst.update({
                    "informazioni_geografiche": None,
                    "counts_by_year": None,
                    "cited_by_count": None,
                    "works_count": None,
                    "is_super_system": None,
                    "roles": None,
                    "summary_stats": None,
                    "type": None
                })
                checkpoint["total_errors"] += 1
                print("  ✗ API fallita")

            enriched[name] = enriched_inst

            checkpoint.update({
                "last_processed_index": idx,
                "last_processed_institution": name,
                "total_processed": checkpoint["total_processed"] + 1,
                "last_update": datetime.now().isoformat()
            })

            self.safe_save_json(enriched, self.output_file)
            self.safe_save_json(checkpoint, self.checkpoint_file)

            time.sleep(self.delay_between_requests)

        print("\n✓ COMPLETATO")
        print(f"Totale processate: {checkpoint['total_processed']}")
        print(f"Errori: {checkpoint['total_errors']}")

# queste righe di codice sotto non funzionano perché stiamo chiamando un metodo della classe senza averne creata un'istanza prima
#if __name__ == "__main__":
#    OpenAlexInstitutionEnricher.enrich(self)
def main():
        enricher = OpenAlexInstitutionEnricher()
        try:
            enricher.enrich()

        except KeyboardInterrupt:
            print("\n\n⚠ Interruzione manuale rilevata")
            print("✓ Il progresso è stato salvato, puoi riprendere in qualsiasi momento")

        except Exception as e:
            print(f"\n\n✗ Errore critico: {e}")
            print("✓ Il progresso dovrebbe essere salvato, controlla i file")


if __name__ == '__main__':
    main()