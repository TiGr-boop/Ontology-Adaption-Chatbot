from config import (
    SYSTEM_PROMPT,
    LLAMA_MODEL,
    REPAIR_SYSTEM_PROMPT,
    RESULT_DESCRIPTION_SYSTEM_PROMPT,
    CONSISTENCY_SYSTEM_PROMPT,
    REWRITE_PROMPT
)
from ollama import chat
from asyncio import to_thread
import chainlit as cl
import logging

logger = logging.getLogger(__file__)

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

async def call_llm(prompt: str, system_prompt: str = SYSTEM_PROMPT, model: str = LLAMA_MODEL) -> str:
    """
    Sendet das Prompt an das LLM und gibt Antwort zurück.
    Das Prompt wird zuvor in einen json Body gepackt.
    Args:
        prompt (Str): Prompt, das an das LLM gesendet werden soll.
        system_prompt (Str): Anweisungen an das System (z.B. konkrete Aufgabe und Regeln)
        model (Str): Name des verwendeten Llama-Models.
    """

    msg = cl.Message(content="")
    await msg.send()

    full_response = ""

    def stream_sync():
        return chat(
            model,
            messages=[
                {'role': 'system', 'content': system_prompt},
                {'role': 'user', 'content': prompt}
            ],
            stream = True
        )
    
    stream = await to_thread(stream_sync)

    for chunk in stream:
        token = chunk['message']['content']
        full_response += token
        await msg.stream_token(token)

    await msg.update()
    return full_response

async def call_llm_repair(broken_turtle: str, error_text: str, model: str = LLAMA_MODEL) -> str:
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

async def call_llm_reasoning_repair(broken_turtle: str, error_text: str, model: str = LLAMA_MODEL) -> str:
    repair_prompt = (
        "The following OWL/Turtle patch caused an inconsistency during reasoning:\n\n"
        f"{broken_turtle}"
        "Reasoner error:"
        f"{error_text}"
        "Fix the patch so the ontology becomes consistent. Return ONLY valid Turtle syntax in a ```turtle ... ``` block."
    )
    response = await call_llm(prompt=repair_prompt, system_prompt=CONSISTENCY_SYSTEM_PROMPT)
    return response

async def call_llm_change_description(ontology_patch_text: str, model: str = LLAMA_MODEL) -> str:
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
