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

Host, account e percorsi vengono letti da `site_config.json`, escluso da Git e conservato accanto ai file Python reali nella cartella privata delle versioni, fuori dalla directory web. Il file di esempio contiene soltanto valori illustrativi. Senza configurazione, la gestione resta disabilitata.

Pubblicare soltanto i file applicativi previsti, dopo i test e con backup esterno alla directory web. Sul NAS i file CGI devono essere eseguibili: `chmod 755 aggiorna_indice.cgi gestisci_attivita.cgi sessione.cgi`. Il caricamento dal browser GitHub conserva il contenuto, ma può non conservare il permesso di esecuzione. Non sincronizzare l’intera cartella del NAS e non usare cancellazioni automatiche sulla cartella delle tracce.

Nome e tipo sono visibili nella raccolta pubblica. Sessioni e cestino sono conservati fuori dal sito. Gli obiettivi mensili sono salvati nel browser.

## Limiti delle analisi

I tempi sono stime GPS con interpolazione lineare, comprensive delle soste. Si interrompono in presenza di segmenti separati, punti senza orario, orari non crescenti, intervalli oltre 120 secondi o velocità oltre 200 km/h. La soglia sui salti elimina soltanto gli errori più evidenti; non certifica un primato. Si confronta una disciplina alla volta e si escludono date mancanti o future. Aprendo un tempo viene evidenziato il tratto nel visualizzatore, con gli estremi arrotondati ai punti registrati più vicini.

I percorsi simili devono avere un solo segmento, almeno 500 m, lunghezze entro l’8%, estremi entro 160 m e punti ricampionati con distanza media entro 65 m e 95° percentile entro 120 m. Il confronto conserva il verso e la disciplina; i risultati richiedono verifica visiva.

I duplicati certi hanno SHA-256 identico. Le possibili doppie registrazioni hanno inizio entro 30 secondi, durata e distanza entro il 5%, discipline compatibili. Nessuna eliminazione automatica.

Preferiti, note ed etichette sono in `journal.json` nella cartella privata già usata dalla gestione, fuori dal web. Sono letti solo dalle azioni autenticate, non entrano nell’indice o nei CSV e restano associati al file anche dopo cestino/ripristino. Non vengono salvati nel browser. Il visualizzatore non incorpora attività di esempio personali.

Il primo aggiornamento aggiunge gli approfondimenti alle voci già indicizzate, senza ricalcolare dislivello e altre statistiche precedenti. Le esecuzioni successive riutilizzano la cache: nessuna rilettura dei file invariati.

Se un GPX già indicizzato ha XML non valido, le statistiche esistenti restano disponibili; il controllo viene segnalato e memorizzato. Non si ripete la lettura finché il file non cambia.


## Aggiornamento del sito da GitHub

“Aggiorna sito” compare durante la gestione autenticata sulla rete locale. “Controlla aggiornamenti” legge il ramo `main` del repository pubblico configurato e ammette soltanto un commit con workflow `.github/workflows/tests.yml` riuscito per quel commit, ramo ed evento push. Il pulsante mostra la versione prima di installarla. Nessuna credenziale GitHub viene conservata.

L’archivio viene scaricato per SHA preciso da codeload.github.com, con verifica TLS, limiti di dimensione e rifiuto di percorsi pericolosi, collegamenti simbolici e file applicativi duplicati. Viene installata soltanto la lista di file applicativi prevista in `website_update.py`. Si controllano hash, sintassi Python e import del generatore con il Python del NAS, senza elaborare attività.

Il NAS conserva le versioni in una sottocartella privata `site-updates/releases/` e cambia il collegamento `current` con un’operazione atomica. Il sito pubblico contiene collegamenti ai singoli file applicativi; **nessun collegamento pubblico a una directory privata**. La configurazione, le sessioni, i metadati e gli archivi restano fuori dalla directory web. Tracce e indice restano nella directory originale. La versione precedente è conservata e verificata prima del ripristino. Le versioni più vecchie non vengono eliminate automaticamente: occupano spazio finché il proprietario non le rimuove manualmente.

Il servizio web può modificare le versioni applicative nella cartella privata già autorizzata. Questo permette gli aggiornamenti, ma un servizio web compromesso potrebbe anche alterare il codice del sito. Non ottiene permessi di amministrazione DSM. Il blocco condiviso impedisce aggiornamenti durante generazione dell’indice o gestione dei file.

Il bootstrap di recupero (`aggiorna_sito.cgi`, `website_update.py` e le copie dei moduli di autenticazione/configurazione necessari) è installato in una cartella separata, leggibile dal servizio web e scrivibile soltanto dal proprietario. **Non viene aggiornato dal pulsante**: le correzioni a questi componenti richiedono installazione manuale del proprietario. Così il ripristino resta disponibile anche se una versione applicativa è difettosa. I test automatici riducono gli errori, ma non garantiscono l’assenza di difetti: verificare il sito dopo ogni aggiornamento e usare il ripristino se necessario.

Per una prima installazione mantenere un backup esterno del sito, creare la configurazione privata, copiare una versione completa nella cartella privata e predisporre i collegamenti pubblici ai soli file applicativi. La proprietà del bootstrap e della directory web deve impedire al servizio web di sostituirli. Non usare copie ricorsive della cartella del NAS verso GitHub.
