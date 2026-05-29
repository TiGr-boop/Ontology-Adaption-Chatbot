from config import SYSTEM_PROMPT, LLAMA_MODEL, REPAIR_SYSTEM_PROMPT
from ollama import chat
from asyncio import to_thread

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
    response = await to_thread(
        chat,
        model,
        messages=[
            {'role': 'system', 'content': system_prompt},
            {'role': 'user', 'content': prompt}
        ]
    )
    return response['message']['content']

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
    response = chat(
        model,
        messages=[
            {"role": "system", "content": REPAIR_SYSTEM_PROMPT},
            {"role": "user",   "content": repair_prompt},
        ],
    )
    return response["message"]["content"]

    
