import matplotlib.pyplot as plt
import math
import statistics

# FUNZIONE PER CALCOLO NUMERO MEDIO DI COLLABORATORI E NUMERO MEDIO DI PAPER PER AUTORE
def avg_num_collaborators(data):
    author_means = []
    all_papers = 0

    for author, information in data.items():
        collaborators_by_paper = information.get("collaborators_by_paper", {})
        
        tot_collaborators = 0
        tot_papers = 0
        
        for paper, collaborators in collaborators_by_paper.items():
            tot_collaborators += len(collaborators[0])
            tot_papers += 1
        
        if tot_papers > 0:
            author_means.append(tot_collaborators / tot_papers)
            all_papers+= tot_papers
        else:
            author_means.append(0)  
    
    if not author_means:
        return 0
    
    avg_collaborators = sum(author_means) / len(author_means)
    std_dev_collabs = statistics.stdev(author_means)
    mediana_collabs = statistics.median(author_means)
    avg_papers = all_papers/len(author_means)
    
    return avg_collaborators, std_dev_collabs, mediana_collabs, avg_papers



# FUNZIONE PER IL CALCOLO DEL NUMERO MEDIO DI AFFILIAZIONI PER AUTORE
def avg_num_affiliations(data):
    author_aff_counts = []

    for author, information in data.items():
        anni_affiliazioni = information.get("anno", {})

        # raccogli tutte le affiliazioni uniche di questo autore
        affiliations = set()
        for year, aff_list in anni_affiliazioni.items():
            affiliations.update(aff_list)
        
        author_aff_counts.append(len(affiliations))

    if not author_aff_counts:
        return 0
    return sum(author_aff_counts) / len(author_aff_counts)



# FUNZIONE PER IL CALCOLO DEL NUMERO MEDIO DI AUTORI PER PAPER
def avg_authors_by_paper(data):

    tot_papers = 0
    tot_authors = 0

    for author, info in data.items():
        collaborators_by_paper = info.get("collaborators_by_paper", {})

        for paper, collaborators in collaborators_by_paper.items():
            tot_papers += 1
            tot_authors += (len(collaborators)+1)

    return tot_authors/tot_papers



# FUNZIONE PER IL CALCOLO DEL NUMERO MEDIO DI AUTORI PER PAPER
def avg_authors_per_paper(data):
    """
    Calcola il numero medio di autori per paper evitando di contare duplicati.
    
    Args:
        authors_data: Dizionario con struttura {autore: {'collaborators_by_paper': {...}, 'anno': {...}}}
    
    Returns:
        tuple: (media_autori_per_paper, dizionario_paper_con_conteggi)
    """
    # Dizionario per tracciare tutti i paper unici e i loro autori
    papers_authors = {}
    
    # Scansiona tutti gli autori
    for author_name, author_info in data.items():
        # Per ogni paper di questo autore
        for paper_title, paper_data in author_info['collaborators_by_paper'].items():
            collaborators, macroarea = paper_data
            
            # Se il paper non è ancora stato visto, inizializzalo
            if paper_title not in papers_authors:
                papers_authors[paper_title] = {
                    'authors': set(),
                    'macroarea': macroarea
                }
            
            # Aggiungi l'autore corrente
            papers_authors[paper_title]['authors'].add(author_name)
            
            # Aggiungi tutti i collaboratori
            for collaborator in collaborators:
                papers_authors[paper_title]['authors'].add(collaborator)
    
    # Calcola il numero di autori per ogni paper
    authors_per_paper = []
    paper_details = {}
    
    for paper_title, paper_info in papers_authors.items():
        num_authors = len(paper_info['authors'])
        authors_per_paper.append(num_authors)
        
        paper_details[paper_title] = {
            'num_authors': num_authors,
            'authors_list': list(paper_info['authors']),
            'macroarea': paper_info['macroarea']
        }
    
    # Calcola la media
    if authors_per_paper:
        average = statistics.mean(authors_per_paper)
        std_dev = statistics.stdev(authors_per_paper) if len(authors_per_paper) > 1 else 0
        mediana = statistics.median(authors_per_paper)

    else:
        average = 0
        std_dev = 0
        mediana = 0
    
    return average, std_dev, mediana, paper_details


# FUNZIONE PER STAMPARE LE STATISTICHE PIÙ INTERESSANTI PER PAPER
def print_paper_statistics(data):
    """
    Stampa statistiche dettagliate sui paper e autori
    """
    average, std_dev, mediana, paper_details = avg_authors_per_paper(data)
    
    print(f"Numero totale di paper unici: {len(paper_details)}")
    print(f"Numero medio di autori per paper: {average:.2f}")
    print(f'Deviazione standard del numero medio di autori per paper: {std_dev}')
    print(f'Mediana del numero di autori per paper: {mediana}')
    print(f"Numero minimo di autori: {min(pd['num_authors'] for pd in paper_details.values()) if paper_details else 0}")
    print(f"Numero massimo di autori: {max(pd['num_authors'] for pd in paper_details.values()) if paper_details else 0}")
    print()

    return paper_details


# FUNZIONE PER L'ANALISI DELLA DISTRIBUZIONE DI AUTORI PER PAPER
def analyze_authorship_patterns(data):
    """
    Analizza i pattern di authorship (distribuzione del numero di autori)
    """
    average, std_dev, mediana, paper_details = avg_authors_per_paper(data)
    
    # Conta la distribuzione del numero di autori
    author_count_distribution = {}
    for paper_info in paper_details.values():
        num_authors = paper_info['num_authors']
        if num_authors not in author_count_distribution:
            author_count_distribution[num_authors] = 0
        author_count_distribution[num_authors] += 1
    
    counts = []
    count_authors = []

    print("Distribuzione numero autori per paper:")
    for num_authors in sorted(author_count_distribution.keys()):
        count = author_count_distribution[num_authors]
        counts.append(count)
        count_authors.append(num_authors)
        percentage = (count / len(paper_details)) * 100
        print(f"  {num_authors} autori: {count} paper ({percentage:.1f}%)")

    plt.figure()
    plt.plot(count_authors, counts)
    plt.xlabel('Numero di autori')
    plt.ylabel('Numero di paper')
    plt.show()
    
    return author_count_distribution


##### FUNZIONI PER DISCIPLINA #####

# FUNZIONE CHE CALCOLA IL TOTALE DI AUTORI E PAPERS PER DISCIPLINA
def tot_authors_and_papers_by_area(data):
    macroareas = {}

    for author, information in data.items():
        collaborators_by_paper = information.get("collaborators_by_paper", {})
        
        for paper, collaborators in collaborators_by_paper.items():
            discipline = collaborators[1]

            if discipline not in macroareas:
                macroareas[discipline] = {'Authors': set(), 'Papers': set()}
            
            macroareas[discipline]['Authors'].add(author)
            macroareas[discipline]['Papers'].add(paper)
            
            for collaborator in collaborators[0]:
                macroareas[discipline]['Authors'].add(collaborator)

    disciplines = list(macroareas.keys())
    num_authors = [len(macroareas[disc]['Authors']) for disc in disciplines]
    num_papers = [len(macroareas[disc]['Papers']) for disc in disciplines]

    for area, infos in macroareas.items():
        print(f"Per il campo {area} il totale degli autori estratti è di {len(infos['Authors'])}")
        print(f"Il totale dei paper è di {len(infos['Papers'])}\n")

    # Creazione del plot
    x = range(len(disciplines))
    width = 0.35  # larghezza delle barre

    fig, ax = plt.subplots(figsize=(10,6))
    bars1 = ax.bar([i - width/2 for i in x], num_papers, width, label='Papers', color='skyblue')
    bars2 = ax.bar([i + width/2 for i in x], num_authors, width, label='Autori', color='salmon')

    ax.set_xlabel('Disciplina')
    ax.set_ylabel('Conteggio')
    ax.set_title('Numero di paper e autori per disciplina')
    ax.set_xticks(x)
    ax.set_xticklabels(disciplines, rotation=45, ha='right')
    ax.legend()

    plt.tight_layout()
    plt.show()
    return macroareas


# FUNZIONE PER IL CALCOLO DEL NUMERO MEDIO DI PAPER PER AUTORE PER DISCIPLINA
def avg_papers_by_area(data):
    area_author_papers = {}

    for author, information in data.items():
        collaborators_by_paper = information.get("collaborators_by_paper", {})
        
        for paper, collaborators in collaborators_by_paper.items():
            discipline = collaborators[1]

            if discipline not in area_author_papers:
                area_author_papers[discipline] = {}

            # Autore principale
            area_author_papers[discipline].setdefault(author, set()).add(paper)

            # Collaboratori
            for collaborator in collaborators[0]:
                area_author_papers[discipline].setdefault(collaborator, set()).add(paper)

    results = {}
    avg_by_area = {} 
    std_by_area = {}

    for discipline, authors_dict in area_author_papers.items():
        # numero di paper per autore
        papers_count = {author: len(papers) for author, papers in authors_dict.items()}
        values = list(papers_count.values())
        n = len(values)

        avg = sum(papers_count.values()) / len(papers_count) if papers_count else 0
        var = sum((x - avg) ** 2 for x in values) / n if n > 0 else 0
        std = math.sqrt(var)

        results[discipline] = {
            "average_papers_per_author": avg,
            "variance": var,
            "std_dev": std,
            "papers_per_author": papers_count
        }

        avg_by_area[discipline] = avg
        std_by_area[discipline] = std

        print(f'Il numero medio di paper per autore nell\'ambito {discipline} è {avg} con deviazione standard uguale a {std}')

    plt.figure(figsize=(8, 5))
    plt.bar(avg_by_area.keys(), avg_by_area.values(), yerr=std_by_area.values(), 
            capsize=5, color="skyblue", alpha=0.8)
    plt.title("Media di paper per autore per disciplina (con deviazione standard)")
    plt.xlabel("Disciplina")
    plt.ylabel("Media ± Dev.Std")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.show()


    return results



# FUNZIONE PER IL CALCOLO DEL NUMERO MEDIO DI COLLABORATORI PER DISCIPLINA
def avg_collaborators_by_area(data):
    # Dizionario che accumula la distribuzione dei collaboratori per paper per disciplina
    collaborators_dict = {}

    for author, information in data.items():
        collaborators_by_paper = information.get("collaborators_by_paper", {})
        
        for paper, collaborators in collaborators_by_paper.items():
            discipline = collaborators[1]
            collabs = collaborators[0]  # lista dei collaboratori di quel paper

            if discipline not in collaborators_dict:
                collaborators_dict[discipline] = {"collaborators_per_paper": []}

            collaborators_dict[discipline]["collaborators_per_paper"].append(len(collabs))

    # Calcolo delle statistiche
    results = {}
    for discipline, stats in collaborators_dict.items():
        values = stats["collaborators_per_paper"]
        n = len(values)

        avg = sum(values) / n if n > 0 else 0
        var = sum((x - avg) ** 2 for x in values) / n if n > 0 else 0
        std = math.sqrt(var)

        results[discipline] = {
            "average_collaborators_per_paper": avg,
            "variance": var,
            "std_dev": std,
            "distribution": values
        }

        print(f"Disciplina: {discipline}")
        print(f"  Media dei collaboratori per paper: {avg:.2f}")
        print(f"  Varianza: {var:.2f}, Dev.Std: {std:.2f}")
        print(f"  Totale paper: {n}, Range: {min(values)}–{max(values)}\n")

    # --- Visualizzazione boxplot ---
    plt.figure(figsize=(10, 6))
    disciplines = list(collaborators_dict.keys())
    data_to_plot = [collaborators_dict[d]["collaborators_per_paper"] for d in disciplines]

    plt.boxplot(data_to_plot, labels=disciplines, patch_artist=True)
    plt.title("Distribuzione collaboratori per paper per disciplina")
    plt.xlabel("Disciplina")
    plt.ylabel("Numero di collaboratori per paper")
    plt.xticks(rotation=30, ha="right")
    plt.tight_layout()
    plt.show()

    return results


# FUNZIONE PER IL CALCOLO DEL NUMERO MEDIO DI AFFILIAZIONI PER AUTORE PER DISCIPLINA + TRE AFFILIAZIONI CHE APPAIONO MAGGIORMENTE PER DISCIPLINA

def avg_affiliations_by_area(data):
    return 