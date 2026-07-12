"""
agents/base_llm.py — Wrapper per chiamate a Gemini API.
"""

from __future__ import annotations
import logging
from typing import Optional
import os

from google import genai
from google.genai import types

from config import LLM_MODEL

logger = logging.getLogger(__name__)


def get_client() -> genai.Client:
    """Restituisce il client Gemini."""
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        msg = (
            "\n❌ GEMINI_API_KEY NON TROVATA\n"
            "   Imposta la variabile d'ambiente GEMINI_API_KEY nel tuo sistema "
            "o in un file .env per usare le API."
        )
        logger.error(msg)
        raise RuntimeError(msg)
    
    return genai.Client(api_key=api_key)


def call_llm(
    prompt: str,
    model: Optional[str] = None,
    system_prompt: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    """
    Chiama l'API Gemini e ritorna il testo della risposta.

    Args:
        prompt: Il messaggio utente da inviare al modello.
        model: Modello da usare (default: config.LLM_MODEL).
        system_prompt: System prompt opzionale.
        temperature: Temperatura per la generazione.

    Returns:
        Testo della risposta del modello.
    """
    model = model or LLM_MODEL
    client = get_client()

    logger.info(f"Chiamata API [{model}] — prompt length: {len(prompt)} chars")

    try:
        config_kwargs = {"temperature": temperature}
        if system_prompt:
            config_kwargs["system_instruction"] = system_prompt

        response = client.models.generate_content(
            model=model,
            contents=prompt,
            config=types.GenerateContentConfig(**config_kwargs),
        )
        content = response.text
        if content is None:
            content = ""
        logger.info(f"Risposta API ricevuta — length: {len(content)} chars")
        return content

    except Exception as e:
        logger.error(f"Errore chiamata API Gemini: {e}")
        raise RuntimeError(f"Errore API Gemini: {e}") from e


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

    # Con l'API Gemini potremmo usare response_mime_type="application/json", 
    # ma manterremo l'approccio text-based con prompt forte per coerenza col resto del codice.
    return call_llm(prompt, model=model, system_prompt=json_system, temperature=0.1)


