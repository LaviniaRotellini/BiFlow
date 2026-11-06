import json
import requests
import time
import os
import shutil
from datetime import datetime
from typing import Dict, Any, Optional

class OpenAlexEnricher:
    def __init__(self, 
                 input_file: str = "Geolocalizzazione delle Istituzioni/Download nuove features/progress_geolocalizzazioni.json",
                 output_file: str = "progress_geolocalizzazioni_enriched.json",
                 checkpoint_file: str = "enrichment_checkpoint.json"):
        
        self.input_file = input_file
        self.output_file = output_file
        self.checkpoint_file = checkpoint_file
        self.delay_between_requests = 0.11  # ~9 richieste/secondo per sicurezza
        self.max_retries = 3
        self.retry_delay = 2  # secondi tra i retry
        
    def load_checkpoint(self) -> Dict[str, Any]:
        """Carica il checkpoint se esistente"""
        if os.path.exists(self.checkpoint_file):
            try:
                with open(self.checkpoint_file, 'r', encoding='utf-8') as f:
                    checkpoint = json.load(f)
                print(f"✓ Checkpoint trovato: riprendo dalla posizione {checkpoint.get('last_processed_index', 0)}")
                return checkpoint
            except Exception as e:
                print(f"⚠ Errore nel caricare il checkpoint: {e}")
                return self._create_new_checkpoint()
        else:
            print("✓ Nessun checkpoint trovato, inizio da zero")
            return self._create_new_checkpoint()
    
    def _create_new_checkpoint(self) -> Dict[str, Any]:
        """Crea un nuovo checkpoint"""
        return {
            'last_processed_index': -1,
            'last_processed_id': None,
            'total_processed': 0,
            'total_errors': 0,
            'started_at': datetime.now().isoformat(),
            'last_update': datetime.now().isoformat()
        }
    
    def safe_save_json(self, data: Dict, filepath: str):
        """Salvataggio atomico per evitare corruzione del file"""
        temp_file = f"{filepath}.tmp"
        backup_file = f"{filepath}.backup"
        
        try:
            # Scrivi su file temporaneo
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            # Se esiste già il file, creane un backup
            if os.path.exists(filepath):
                shutil.copy2(filepath, backup_file)
            
            # Sostituisci il file originale (operazione atomica su POSIX)
            shutil.move(temp_file, filepath)
            
            # Rimuovi il backup se tutto è andato bene
            if os.path.exists(backup_file):
                os.remove(backup_file)
                
        except Exception as e:
            print(f"✗ Errore nel salvataggio di {filepath}: {e}")
            # In caso di errore, ripristina dal backup se esiste
            if os.path.exists(backup_file) and not os.path.exists(filepath):
                shutil.move(backup_file, filepath)
                print(f"✓ File ripristinato dal backup")
            raise
        finally:
            # Pulizia file temporanei
            if os.path.exists(temp_file):
                os.remove(temp_file)
    
    def fetch_institution_data(self, openalex_id: str) -> Optional[Dict[str, Any]]:
    # Estrai l'ID OpenAlex (es. I19630809)
        institution_id = openalex_id.rstrip("/").split("/")[-1]

        url = f"https://api.openalex.org/institutions/{institution_id}"

        headers = {
            'User-Agent': 'OpenAlexEnricher/1.0 (mailto:your@email.com)',
            'Accept': 'application/json'
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    return response.json()
                elif response.status_code == 404:
                    print(f"  ⚠ Istituzione non trovata (404)")
                    return None
                else:
                    print(f"  ⚠ Errore HTTP {response.status_code} (tentativo {attempt + 1}/{self.max_retries})")

            except requests.exceptions.Timeout:
                print(f"  ⚠ Timeout (tentativo {attempt + 1}/{self.max_retries})")
            except requests.exceptions.RequestException as e:
                print(f"  ⚠ Errore di rete: {e} (tentativo {attempt + 1}/{self.max_retries})")

            if attempt < self.max_retries - 1:
                time.sleep(self.retry_delay)

        print(f"  ✗ Fallito dopo {self.max_retries} tentativi")
        return None

    
    def extract_enrichment_data(self, api_data: Dict[str, Any]) -> Dict[str, Any]:
        """Estrae i dati richiesti dalla risposta API"""
        enrichment = {}
        
        # counts_by_year - ultimi 10 anni
        if 'counts_by_year' in api_data:
            counts = api_data['counts_by_year'][:10]  # Prendi i primi 10 (più recenti)
            enrichment['counts_by_year'] = counts
        else:
            enrichment['counts_by_year'] = 'null'
        
        # cited_by_count totale
        enrichment['cited_by_count'] = api_data.get('cited_by_count', 'null')

        # works_count totale
        enrichment['works_count'] = api_data.get('works_count', 'null')
        
        # is_super_system
        enrichment['is_super_system'] = api_data.get('is_super_system', 'null')
        
        # roles
        enrichment['roles'] = api_data.get('roles', 'null')
        
        # summary_stats
        enrichment['summary_stats'] = api_data.get('summary_stats', 'null')
        
        # type
        enrichment['type'] = api_data.get('type', 'null')
        
        return enrichment
    
    def enrich_institutions(self):
        """Processo principale di arricchimento"""
        print("=" * 60)
        print("OpenAlex Institution Enricher")
        print("=" * 60)
        
        # Carica il file di input
        print(f"\n1. Caricamento file {self.input_file}...")
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                institutions = json.load(f)
            print(f"✓ Caricate {len(institutions)} istituzioni")
        except FileNotFoundError:
            print(f"✗ File {self.input_file} non trovato!")
            return
        except json.JSONDecodeError as e:
            print(f"✗ Errore nel parsing del JSON: {e}")
            return
        
        # Carica il checkpoint
        print(f"\n2. Caricamento checkpoint...")
        checkpoint = self.load_checkpoint()
        
        # Carica i dati già arricchiti se esistono
        if os.path.exists(self.output_file):
            try:
                with open(self.output_file, 'r', encoding='utf-8') as f:
                    enriched_data = json.load(f)
                print(f"✓ Caricati dati esistenti da {self.output_file}")
            except:
                enriched_data = {}
                print(f"⚠ Impossibile caricare {self.output_file}, ricreo da zero")
        else:
            enriched_data = {}
        
        # Converti in lista per gestire l'indice
        institution_items = list(institutions.items())
        total = len(institution_items)
        start_index = checkpoint['last_processed_index'] + 1
        
        print(f"\n3. Inizio arricchimento...")
        print(f"   Totale istituzioni: {total}")
        print(f"   Già processate: {checkpoint['total_processed']}")
        print(f"   Da processare: {total - start_index}")
        print(f"   Errori precedenti: {checkpoint['total_errors']}")
        print("\n" + "-" * 60)
        
        # Processa ogni istituzione
        for idx in range(start_index, total):
            openalex_id, institution_data = institution_items[idx]
            
            print(f"\n[{idx + 1}/{total}] {institution_data.get('nome', 'N/A')}")
            print(f"  ID: {openalex_id}")
            
            # Copia i dati esistenti
            enriched_institution = institution_data.copy()
            
            # Recupera dati da OpenAlex
            api_data = self.fetch_institution_data(openalex_id)
            
            if api_data:
                # Estrai e aggiungi i nuovi dati
                enrichment = self.extract_enrichment_data(api_data)
                enriched_institution.update(enrichment)
                print(f"  ✓ Dati arricchiti con successo")
            else:
                # Aggiungi campi null se non recuperati
                enriched_institution.update({
                    'counts_by_year': 'null',
                    'cited_by_count': 'null',
                    'works_count': 'null',
                    'is_super_system': 'null',
                    'roles': 'null',
                    'summary_stats': 'null',
                    'type': 'null'
                })
                checkpoint['total_errors'] += 1
                print(f"  ✗ Impossibile recuperare dati, inseriti valori null")
            
            # Salva nel dizionario arricchito
            enriched_data[openalex_id] = enriched_institution
            
            # Aggiorna checkpoint
            checkpoint['last_processed_index'] = idx
            checkpoint['last_processed_id'] = openalex_id
            checkpoint['total_processed'] += 1
            checkpoint['last_update'] = datetime.now().isoformat()
            
            # Salva progresso (dopo ogni istituzione)
            try:
                self.safe_save_json(enriched_data, self.output_file)
                self.safe_save_json(checkpoint, self.checkpoint_file)
                print(f"  ✓ Progresso salvato")
            except Exception as e:
                print(f"  ✗ Errore nel salvataggio: {e}")
                print(f"  ⚠ ATTENZIONE: Progresso potrebbe essere perso!")
            
            # Rate limiting
            if idx < total - 1:  # Non aspettare dopo l'ultima
                time.sleep(self.delay_between_requests)
        
        # Riepilogo finale
        print("\n" + "=" * 60)
        print("COMPLETATO!")
        print("=" * 60)
        print(f"Totale processate: {checkpoint['total_processed']}")
        print(f"Totale errori: {checkpoint['total_errors']}")
        print(f"File output: {self.output_file}")
        print(f"Checkpoint: {self.checkpoint_file}")
        print("=" * 60)

def main():
    enricher = OpenAlexEnricher()
    
    try:
        enricher.enrich_institutions()
    except KeyboardInterrupt:
        print("\n\n⚠ Interruzione manuale rilevata")
        print("✓ Il progresso è stato salvato, puoi riprendere in qualsiasi momento")
    except Exception as e:
        print(f"\n\n✗ Errore critico: {e}")
        print("✓ Il progresso dovrebbe essere salvato, controlla i file")

if __name__ == "__main__":
    main()