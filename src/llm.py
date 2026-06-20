from config import (
    SYSTEM_PROMPT,
    LLM_MODEL,
    REPAIR_SYSTEM_PROMPT,
    RESULT_DESCRIPTION_SYSTEM_PROMPT,
    CONSISTENCY_SYSTEM_PROMPT,
    REWRITE_PROMPT,
    OPENAI_API_KEY
)
from ollama import chat
from openai import AsyncOpenAI
from asyncio import to_thread
import chainlit as cl
import logging

logger = logging.getLogger(__file__)

if OPENAI_API_KEY != "":
    openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)

OPENAI_MODEL_PREFIXES = ("gpt-", "o1-", "o3-", "o4-")

def is_openai_model(model = LLM_MODEL) -> bool:
    return model.startswith(OPENAI_MODEL_PREFIXES)


def build_llm_prompt(
        user_input: str,
        chunks: list,
) -> str:
    """
    Baut das vollständige LLM-Prompt zusammen.
    Args:
        user_input (Str): Durch den User eingegebenes Prompt.
    """

    chunks_content = []
    for c in chunks:
        chunks_content.append(
            f"Enität: {c['label']}\nTyp: {c['entity_type']}\nTurtle: {c['turtle']}"
        )

    context = "\n\n".join(chunks_content)

    final_prompt = (
        "Betrachte folgendes Szenario\n"
        f"{user_input}\n\n"
        "Berücksichtige dabei diese relevanten Ontologie-Ausschnitte:\n"
        f"{context}")

    return final_prompt

async def _stream_ollama(prompt: str, system_prompt: str, model: str, msg: cl.Message) -> str:
    full_response = ""

    def stream_sync():
        return chat(
            model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            stream=True
        )

    stream = await to_thread(stream_sync)

    for chunk in stream:
        token = chunk['message']['content']
        full_response += token
        await msg.stream_token(token)

    return full_response


async def _stream_openai(prompt: str, system_prompt: str, model: str, msg: cl.Message) -> str:
    full_response = ""

    stream = await openai_client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ],
        stream=True
    )

    async for chunk in stream:
        token = chunk.choices[0].delta.content or ""
        full_response += token
        await msg.stream_token(token)

    return full_response


async def call_llm(prompt: str, system_prompt: str = SYSTEM_PROMPT, model: str = LLM_MODEL) -> str:
    """
    Sendet das Prompt an das LLM und gibt Antwort zurück.
    Wählt automatisch zwischen Ollama und OpenAI basierend auf dem Modellnamen.
    Args:
        prompt (Str): Prompt, das an das LLM gesendet werden soll.
        system_prompt (Str): Anweisungen an das System (z.B. konkrete Aufgabe und Regeln)
        model (Str): Name des verwendeten Modells (z.B. 'llama3:8b' oder 'gpt-4o').
    """

    assert not is_openai_model(model=LLM_MODEL) or OPENAI_API_KEY, \
        "Es wurde ein OpenAI-Modell gewählt, aber kein API-Key zur Verfügung gestellt"
    
    msg = cl.Message(content="")
    await msg.send()

    if is_openai_model(model):
        full_response = await _stream_openai(prompt, system_prompt, model, msg)
    else:
        full_response = await _stream_ollama(prompt, system_prompt, model, msg)

    await msg.update()
    return full_response

async def call_llm_repair(broken_turtle: str, error_text: str, model: str = LLM_MODEL) -> str:
    """
    Sendet falsche Turtle-Serialisierung + Fehlermeldungen ans LLM zur Korrektur.
    Wird aufgerufen wenn check_syntax() fehlschlägt.
    """
    repair_prompt = (
        "The following Turtle snippet is syntactically invalid.\n\n"
        f"{broken_turtle}\n\n"
        "Thare the Parser errors\n\n"
        f"{error_text}\n\n"
        "Fix all syntax errors and return only the corrected Turtle block."
    )
    response = await call_llm(repair_prompt, system_prompt=REPAIR_SYSTEM_PROMPT)
    return response

async def call_llm_reasoning_repair(broken_turtle: str, error_text: str, model: str = LLM_MODEL) -> str:
    repair_prompt = (
        "The following OWL/Turtle patch caused an inconsistency during reasoning:\n\n"
        f"{broken_turtle}"
        "Reasoner error:"
        f"{error_text}"
        "Fix the patch so the ontology becomes consistent. Return ONLY valid Turtle syntax in a ```turtle ... ``` block."
    )
    response = await call_llm(prompt=repair_prompt, system_prompt=CONSISTENCY_SYSTEM_PROMPT)
    return response

async def call_llm_change_description(ontology_patch_text: str, model: str = LLM_MODEL) -> str:
    """
    Sendet den Ontologie-Patch an das LLM, welches die Änderungen in natürlicher Sprache beschreiben soll.
    """
    prompt = (
        "The following ontology patch is added to the base ontology.\n"
        "Describe the changes with natural language in german.\n\n"
        f"{ontology_patch_text}\n\n"
    )
    
    await call_llm(prompt=prompt, system_prompt=RESULT_DESCRIPTION_SYSTEM_PROMPT)


async def rewrite_scenario(scenario: str, chunks: list) -> str:
    existing_entities = "\n".join(f"- {c['label']} (Typ: {c['entity_type']})" for c in chunks)
    chunk_text = "\n\n".join(c["text"] for c in chunks)

    prompt = REWRITE_PROMPT + f"""
        EXISTING ENTITIES (already in ontology, do NOT recreate these):
        {existing_entities}

        FULL CHUNK DETAILS:
        {chunk_text}"""
    
    requirements = await call_llm(prompt=scenario, system_prompt=prompt)
    logger.info(f"Rewritten requirements:\n{requirements}")
    return requirements
