# 🏥 SmartScheduler — Hospital Shift Scheduling System

**SmartScheduler** è un sistema "Agentic" multi-stadio avanzato, sviluppato per affrontare il complesso problema della turnazione del personale ospedaliero. L'obiettivo primario è generare calendari dei turni che soddisfino non solo le stringenti normative legali e di copertura clinica (Vincoli Hard), ma che massimizzino anche l'equità e il benessere del personale, tenendo conto delle loro preferenze espresse in linguaggio naturale.

Il progetto integra tecniche di **Natural Language Understanding (NLU)** tramite Large Language Models (LLM) con avanzati paradigmi di **Operations Research (OR) e Constraint Programming (CP-SAT)**.

---

## 🏗️ 1. L'Architettura a Grafo (The Workflow)

Il ciclo di vita dell'applicazione è orchestrato utilizzando **LangGraph**, che modella l'intero processo in un Automa a Stati Finiti (StateGraph) composto da 4 Stage sequenziali e iterativi.

* **Stage 1: Preferences Definition**
  Vengono raccolti i profili testuali dei dipendenti. L'Agente LLM estrae dal testo le tolleranze verso i turni notturni/festivi, i giorni di riposo preferiti e le indisponibilità assolute.
* **Stage 2: Schedule Drafting**
  I dati estratti alimentano un builder deterministico che istanzia un modello CP-SAT di Google OR-Tools. Il solver cerca il primo incastro matematico valido che rispetti le coperture richieste, restituendo uno schedule provvisorio.
* **Stage 3: Verification & Fairness Evaluation**
  * **3a (Hard Verification):** Un agente simbolico verifica rigidamente l'assenza di infrazioni normative (es. massimo di 36 ore a settimana, obbligo di 2 giorni di riposo post-notte). Se un vincolo è rotto, l'esecuzione torna allo Stage 2 con il log dell'errore (Drafting Callback).
  * **3b (Fairness):** Se lo schedule è legale, viene calcolato un "Satisfaction Score" (da 0 a 1) per ogni lavoratore, identificando matematicamente il lavoratore più penalizzato dal tabellone corrente.
* **Stage 4: Fairness Refinement (LNS Loop)**
  Qualora lo scarto di soddisfazione tra i dipendenti sia eccessivo, si avvia il loop di miglioramento continuo. Il nodo di Refinement cerca di ritoccare le assegnazioni per alzare il punteggio del dipendente peggiore, iterando gli Stage 2, 3 e 4 fino al raggiungimento di un ottimo matematico in cui la Fairness non è più migliorabile.

---

## 🚀 2. Scelte Architetturali Chiave (Design Decisions)

Durante lo sviluppo sono state prese decisioni architetturali cruciali per trasformare il progetto da un prototipo teorico a un software di grado "Enterprise".

### A. Ibridazione LLM / OR-Tools (No Code-Generation)
Inizialmente, la traccia suggeriva che l'LLM generasse letteralmente il codice Python per configurare il solver. I test hanno rivelato che gli LLM, su task combinatori così lunghi, soffrono di "allucinazioni sintattiche" (nomi di variabili errati, indentazioni perse) rompendo l'esecuzione del solver in modo fatale.
**La Scelta:** Abbiamo implementato un approccio **Ibrido**. L'LLM agisce *esclusivamente* come motore di decodifica semantica per parsare il testo in linguaggio naturale ed estrarre pesi numerici Pydantic. Lo Stage di "Drafting" inietta queste variabili pulite all'interno di un builder Python deterministico e rigoroso. Zero crash sintattici, pura affidabilità matematica.

### B. Algoritmo LNS (Large Neighborhood Search) per la Fairness
Per il Refinement (Stage 4), tentare di ricalcolare l'intero mese con pesi leggermente modificati portava all'instabilità (l'Effetto Farfalla: aiutare un lavoratore distruggeva i turni perfetti di un altro).
**La Scelta:** Abbiamo implementato l'approccio **Fix-and-Optimize (LNS)**. Il nodo di Refinement identifica il 50% dei lavoratori più felici e **"congela" (Fix)** i loro turni inserendoli come vincoli rigidi in OR-Tools. Successivamente, **"lascia liberi" (Optimize)** il lavoratore peggiore e il restante gruppo di donatori. In questo spazio di ricerca circoscritto, il solver scambia i turni miratamente per sollevare il lavoratore più sofferente. Se il solver va in errore (`INFEASIBLE`), sappiamo per induzione matematica di aver raggiunto un Ottimo Locale perfetto e interrompiamo il loop in modo sicuro.

### C. Accelerazione Hardware (ROCm) e Inferenza Locale
L'estrazione iniziale delle preferenze avviene tramite **Qwen2.5-Coder 7B** (in esecuzione tramite Ollama). Per supportare la scalabilità su grossi ospedali, è stata attivata la variabile `HSA_OVERRIDE_GFX_VERSION=10.3.0`. Questo delega interamente i tensor-core dell'LLM all'architettura AMD RDNA2 della GPU, portando l'elaborazione NLP di 20 dipendenti a soli pochissimi secondi di esecuzione locale.

---

## 📁 3. Struttura Dettagliata del Progetto

Il codice è diviso semanticamente per pattern architetturali:

### 🔹 Root Directory
* `main.py`: Entry point CLI. Gestisce il setup del logger, l'inizializzazione del Grafo, e la renderizzazione estetica finale in file testo.
* `config.py`: File di configurazione globale. Mantiene variabili d'ambiente cruciali: l'orizzonte mensile (Dicembre/Gennaio), la durata dei turni e i flag di configurazione dell'Use Case.
* `requirements.txt`: Dipendenze Python (`langgraph`, `ortools`, `pydantic`, ecc.).

### 🔹 `agents/` (Logica dei Nodi LangGraph)
Contiene le singole "intelligenze" responsabili dei 4 step del grafo:
* `base_llm.py`: Astrazione della chiamata HTTP ad API locali Ollama, con gestione di retry, backoff e robustezza di rete.
* `preferences_agent.py`: Implementa il Prompter. Invoca l'LLM passando le biografie e raccoglie stringhe formattate JSON tramite RegEx parsing.
* `drafting_agent.py`: Il cuore operativo. Nel primo ciclo crea l'oggetto base; nei cicli di Refinement calcola l'array di LNS, seleziona i donatori e definisce le porzioni di tabellone da congelare, passandole come Injection-String al Solver.
* `verification_agent.py`: Motore di regole (Rule Engine) a cicli for iterativi. Verifica rigidamente se le assegnazioni prodotte rompono una qualsiasi delle 7 leggi dell'ospedale, sollevando violazioni.
* `fairness_agent.py`: Calcolatore statistico. Ritorna score basati sull'estrazione dei giorni lavorati di notte e le penalità sopportate. Modella anche i router condizionali (Edges) per il loop `while non migliorabile`.

### 🔹 `solver/` (Motore di Constraint Programming)
* `ortools_builder.py`: Traduttore che modella matematicamente i constraint. Configura le equazioni booleane booleane (e.g., `notte + mattina_dopo <= 1`) e inserisce gli `Add` statement all'interno di uno scope generativo.
* `ortools_runner.py`: Modulo che wrappa in modo sicuro (`subprocess.run` con timeout o diretti bind Python) la vera e propria chiamata al kernel CP-SAT C++ in backend.

### 🔹 `models/` (Data Typing)
Sfrutta la validazione rigorosa Pydantic per impedire Type Error.
* `state.py`: Definisce il super-state (Dizionario) iniettato e mutato dinamicamente lungo i bordi del LangGraph.
* `worker.py`: Classi `Worker`, `WorkerType` e struct delle Preferenze.
* `schedule.py`: Classi `DaySchedule` e `ShiftAssignment` con getter custom per calcolare statistiche orarie "On the Fly".

### 🔹 `graph/`
* `smartscheduler_graph.py`: La mappa stradale. Istanzia la classe `StateGraph` di LangChain. Aggiunge i Nodi e definisce esplicitamente la topologia degli Edges lineari e dei Router Condizionali (If/Else sul fallback dei draft).

### 🔹 `data/` & `output_runX/`
* `data/scenarios/`: File yaml/txt sorgenti con l'anagrafica dei medici (Scenari A e B).
* `output_runX/`: Artefatti finali. Contiene un `report_ucX.txt` ad alta leggibilità visuale (con istogrammi e alert domenicali in unicode) e l'equivalente formato `.json` serializzato, pronto per essere consumato da front-end o database aziendali.

---

## 🛠️ 4. Dominio dei Vincoli (Constraints Overview)
SmartScheduler garantisce **sempre** il rispetto dei seguenti vincoli hard:
1. **Orizzonte:** 31 giorni, dal 07-12-2026 al 06-01-2027.
2. **Monte Ore (36h/Settimana):** Massimo 36 ore aggregate ogni finestra scorrevole di 7 giorni.
3. **Turnazione Continua:** Esattamente 25 Shift-Units mensili garantite per dipendente, con la notte (12h) che pesa come due turni normali (6h).
4. **Riposi Obbligatori:** Un lavoratore assegnato alla notte deve ricevere un "freeze" obbligatorio di 2 giorni solari post-turno.
5. **Esclusione Consecutiva:** Divieto assoluto di doppiare turni nello stesso giorno, o coprire consecutivamente Notte e poi Mattina.

**Use Case Implementati:**
* **Use Case A (Omogeneo):** 13 Infermieri con mansioni identiche. Minimo 2 lavoratori fisici in ogni stanza.
* **Use Case B (Eterogeneo):** 13 Standard + 7 Specializzati. Minimo 3 lavoratori in stanza in ogni turno, ma con la rigorosa costrizione che almeno uno sia uno specialista (che ha facoltà di sostituire o fungere da Standard in caso di surplus).

---

## 🖥️ 5. Istruzioni d'Uso (Quickstart)

Il progetto richiede **Python 3.10+**.
Per inizializzare l'ambiente:

```bash
pip install -r requirements.txt
```

Assicurati di aver scaricato e avviato in background il daemon di `ollama`, avendo scaricato preventivamente il modello:
```bash
ollama run qwen2.5-coder:7b
```

Per lanciare la pipeline e generare l'orario completo sul terminale (e all'interno della cartella `output_*/`):

```bash
# Esecuzione dello Use Case A
python main.py --use-case A --model qwen2.5-coder:7b

# Esecuzione dello Use Case B
python main.py --use-case B --model qwen2.5-coder:7b
```
