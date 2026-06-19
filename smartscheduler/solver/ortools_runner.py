"""
solver/ortools_runner.py — Esecuzione sicura di codice OR-Tools generato dall'LLM.

Il codice generato viene scritto in un file temporaneo ed eseguito in un
subprocess con timeout. L'output atteso è un JSON su stdout.
"""

import json
import logging
import os
import subprocess
import sys
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


def run_ortools_code(code: str, timeout: int = 60) -> dict[str, Any]:
    """
    Esegue un file Python contenente un modello OR-Tools CP-SAT.

    Args:
        code: Codice Python completo da eseguire.
        timeout: Secondi massimi prima di terminare il processo.

    Returns:
        Dict con il risultato JSON parsato, o {"error": "<messaggio>"} in caso di errore.
    """
    tmp_path = None
    try:
        # Scrive il codice in un file temporaneo
        with tempfile.NamedTemporaryFile(
            suffix=".py", mode="w", delete=False, encoding="utf-8"
        ) as f:
            f.write(code)
            tmp_path = f.name

        logger.debug(f"Eseguo codice OR-Tools da: {tmp_path}")

        result = subprocess.run(
            [sys.executable, tmp_path],
            capture_output=True,
            text=True,
            timeout=timeout,
        )

        if result.returncode != 0:
            logger.error(f"OR-Tools subprocess fallito:\n{result.stderr}")
            return {"error": f"RUNTIME_ERROR: {result.stderr.strip()}"}

        stdout = result.stdout.strip()
        if not stdout:
            logger.error("OR-Tools subprocess: nessun output su stdout")
            return {"error": "NO_OUTPUT"}

        try:
            parsed = json.loads(stdout)
            logger.info("OR-Tools completato con successo")
            return parsed
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}\nOutput grezzo: {stdout[:500]}")
            return {"error": f"JSON_PARSE_ERROR: {e}", "raw": stdout[:500]}

    except subprocess.TimeoutExpired:
        logger.error(f"OR-Tools timeout dopo {timeout}s")
        return {"error": f"TIMEOUT after {timeout}s"}

    except Exception as e:
        logger.exception("Errore inatteso nell'esecuzione OR-Tools")
        return {"error": f"UNEXPECTED_ERROR: {e}"}

    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass  # Non critico


def extract_code_from_llm_response(response: str) -> str:
    """
    Estrae il blocco di codice Python da una risposta LLM.
    Cerca prima ```python ... ```, poi ``` ... ```, poi prende tutto il testo.
    """
    import re

    # Cerca ```python ... ```
    match = re.search(r"```python\s*(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Cerca ``` ... ``` generico
    match = re.search(r"```\s*(.*?)```", response, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Fallback: prende tutto il testo
    logger.warning("Nessun blocco di codice trovato nella risposta LLM, uso testo grezzo")
    return response.strip()
