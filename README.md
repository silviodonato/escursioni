# Diario delle attività

Raccolta di attività GPX e TCX con mappa, visualizzatore, statistiche, calendario e confronto. Include mappa delle uscite e frequenza per zona, tempi GPS su 1/5/10 km, percorsi ripetuti e controlli sui dati. HTML/JavaScript e generatore Python per Synology DSM.

Il repository contiene solo codice e test con dati sintetici. Tracce, indice, sessioni e metadati personali restano fuori da Git.

## Test e anteprima

Python 3.8 o successivo, libreria standard. Node.js serve per i test JavaScript.

```sh
python3 -m unittest discover -p 'verify*.py'
for check in verify_*.cjs; do node "$check"; done
```

Copiare i propri GPX/TCX in `tracce/`, eseguire `python3 genera_indice.py` e avviare `python3 -m http.server`. Convertire i FIT in GPX; gli originali possono essere conservati accanto al file convertito. L’anteprima http.server mostra il sito in lettura; la gestione richiede CGI Python su DSM.

## Struttura

- `index.html`, `library.js`, `library.css`: raccolta, filtri e gestione.
- `activity.html`: visualizzatore di una singola attività.
- `progress*.js`, `analysis-tools.js`, `comparison.js`: statistiche e confronti.
- `atlas*.js`: mappa della raccolta e frequenza delle uscite per zona.
- `genera_indice.py`: indice incrementale con geometrie semplificate.
- `activity_metrics.py`, `efforts.js`: tempi GPS stimati su segmenti continui.
- `route-tools.js`, `route-worker.js`, `routes.js`: gruppi prudenti di percorsi simili.
- `journal.js`: preferiti, etichette e note private.
- `quality*.js`: date, GPS, orari e possibili duplicati.
- `activity_store.py`: metadati e cestino recuperabile.
- `activity_auth.py`, `sessione.cgi`: accesso DSM con sessione limitata alla raccolta.
- `aggiorna_indice.cgi`, `gestisci_attivita.cgi`: azioni protette su rete locale.

## Pubblicazione sul NAS

La configurazione attuale usa host, account e percorsi locali presenti nel codice. Per un’altra installazione adeguarli prima di abilitare la gestione.

Pubblicare soltanto i file applicativi previsti, dopo i test e con backup esterno alla directory web. Non sincronizzare l’intera cartella del NAS e non usare cancellazioni automatiche sulla cartella delle tracce.

Nome e tipo sono visibili nella raccolta pubblica. Sessioni e cestino sono conservati fuori dal sito. Gli obiettivi mensili sono salvati nel browser.

## Limiti delle analisi

I tempi sono stime GPS con interpolazione lineare, comprensive delle soste. Si interrompono in presenza di segmenti separati, punti senza orario, orari non crescenti, intervalli oltre 120 secondi o velocità oltre 200 km/h. La soglia sui salti elimina soltanto gli errori più evidenti; non certifica un primato. Si confronta una disciplina alla volta e si escludono date mancanti o future. Aprendo un tempo viene evidenziato il tratto nel visualizzatore, con gli estremi arrotondati ai punti registrati più vicini.

I percorsi simili devono avere un solo segmento, almeno 500 m, lunghezze entro l’8%, estremi entro 160 m e punti ricampionati con distanza media entro 65 m e 95° percentile entro 120 m. Il confronto conserva il verso e la disciplina; i risultati richiedono verifica visiva.

I duplicati certi hanno SHA-256 identico. Le possibili doppie registrazioni hanno inizio entro 30 secondi, durata e distanza entro il 5%, discipline compatibili. Nessuna eliminazione automatica.

Preferiti, note ed etichette sono in `journal.json` nella cartella privata già usata dalla gestione, fuori dal web. Sono letti solo dalle azioni autenticate, non entrano nell’indice o nei CSV e restano associati al file anche dopo cestino/ripristino. Non vengono salvati nel browser. Il visualizzatore non incorpora attività di esempio personali.

Il primo aggiornamento aggiunge gli approfondimenti alle voci già indicizzate, senza ricalcolare dislivello e altre statistiche precedenti. Le esecuzioni successive riutilizzano la cache: nessuna rilettura dei file invariati.

Se un GPX già indicizzato ha XML non valido, le statistiche esistenti restano disponibili; il controllo viene segnalato e memorizzato. Non si ripete la lettura finché il file non cambia.
