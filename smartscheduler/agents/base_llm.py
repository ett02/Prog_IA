"""
agents/base_llm.py — Wrapper per chiamate a Ollama.
"""

from __future__ import annotations
import logging
from typing import Optional

import ollama

from config import OLLAMA_MODEL

logger = logging.getLogger(__name__)


def call_llm(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """
    Chiama Ollama e ritorna il testo della risposta.

    Args:
        prompt: Il messaggio utente da inviare al modello.
        model: Modello Ollama da usare (default: config.OLLAMA_MODEL).
        system_prompt: System prompt opzionale.
        temperature: Temperatura per la generazione (bassa = più deterministico).

    Returns:
        Testo della risposta del modello.

    Raises:
        RuntimeError: Se Ollama non è raggiungibile o risponde con errore.
    """
    model = model or OLLAMA_MODEL
    messages = []

    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})

    messages.append({"role": "user", "content": prompt})

    logger.info(f"Chiamata LLM [{model}] — prompt length: {len(prompt)} chars")

    try:
        response = ollama.chat(
            model=model,
            messages=messages,
            options={"temperature": temperature},
        )
        content = response["message"]["content"]
        logger.info(f"Risposta LLM ricevuta — length: {len(content)} chars")
        return content

    except Exception as e:
        logger.error(f"Errore chiamata Ollama: {e}")
        raise RuntimeError(f"Ollama non raggiungibile o errore API: {e}") from e


def call_llm_for_json(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Chiama l'LLM chiedendo esplicitamente output JSON.
    Usa temperatura molto bassa per massimizzare la consistenza del formato.
    """
    json_system = (
        "Sei un assistente preciso. Rispondi SEMPRE e SOLO con JSON valido, "
        "senza testo aggiuntivo prima o dopo il JSON. "
        "Non aggiungere markdown, commenti o spiegazioni."
    )
    if system_prompt:
        json_system = system_prompt + "\n\n" + json_system

    return call_llm(prompt, model=model, system_prompt=json_system, temperature=0.1)


def call_llm_for_code(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> str:
    """
    Chiama l'LLM per generare codice Python.
    Usa temperatura bassa per output deterministico.
    """
    code_system = (
        "Sei un esperto programmatore Python specializzato in OR-Tools CP-SAT. "
        "Genera SOLO codice Python valido all'interno di un blocco ```python ... ```. "
        "Il codice deve essere eseguibile direttamente con: python script.py"
    )
    if system_prompt:
        code_system = system_prompt + "\n\n" + code_system

    return call_llm(prompt, model=model, system_prompt=code_system, temperature=0.15)
