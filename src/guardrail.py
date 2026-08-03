from config import SUPPORTED_FORMATS, STANDARD_PREFIXES, MAX_REPAIR_ATTEMPTS
from functions import stream_text
from llm import call_llm_repair

from rdflib import Graph
import logging
import re
from asyncio import to_thread

logger = logging.getLogger("__file__")

async def check_syntax(llm_response: str) -> tuple[bool, list, Graph, str]:
    """
    Versucht die LLM-Antwort in mehreren Formaten zu parsen.
    Args:
        llm-response (Str): Antwort des LLMs auf das Prompt. Die Antwort sollte lediglich einen RDF-Block beinhalten.

    Returns:
        bool: Result of parsing. True, if parsing was successful.
        list: list of errors in case parsing wasn't successfull
        Graph: Parsed graph
        Format: format of the parsed graph
    """
    error_list = []

    for format in SUPPORTED_FORMATS:
        graph = Graph()
        try:
            logger.debug("Typ: %s", type(llm_response))
            await to_thread(graph.parse, data=llm_response, format=format)
            logger.info("Syntax-Validierung erfolgreich (Format: %s).", format)
            return True, error_list, graph, format
        except Exception as e:
            error_list.append(e)
            print(f"Format: {e}")
            continue
    
    return False, error_list, Graph, ""


### CLAUDE FUNKTION
def preprocess_llm_response(llm_response: str) -> str:
    """
    Bereinigt die rohe LLM-Ausgabe, bevor sie an den RDF-Parser weitergegeben wird.

    Folgende Probleme werden behoben:
    1. Markdown-Fences werden entfernt
    2. Default-Namespace des Parsers durch Ontologie-Namespace ersetzen
    3. Fehlende spitze Klammern in @prefix-Zeilen werden ergänzt
    4. Standard-Präfixe werden einfügt, sofern nicht vorhanden
    """

    # in String überführen, wenn Byte-Stream erhalten wird
    if isinstance(llm_response, bytes):
        llm_response = llm_response.decode("utf-8")

    # String-Repräsentation eines Bytes-Objekts ("b'...'" oder 'b"..."')
    if isinstance(llm_response, str):
        llm_response = llm_response.strip()

        if (
            (llm_response.startswith("b'") and llm_response.endswith("'"))
            or
            (llm_response.startswith('b"') and llm_response.endswith('"'))
        ):
            llm_response = llm_response[2:-1]

            # Escape-Sequenzen (\n, \t, ...) wieder in echte Zeichen umwandeln
            llm_response = bytes(llm_response, "utf-8").decode("unicode_escape")

    # 1. Markdown-Fence extrahieren (```turtle ... ``` oder ``` ... ```)
    fence_match = re.search(
        r"^\s*```(?:turtle|rdf|n3|ntriples|xml)?\s*(.*?)\s*```\s*$",
        llm_response,
        flags=re.DOTALL | re.MULTILINE,
    )
    if fence_match:
        turtle_str = fence_match.group(1).strip()
        logger.debug("Markdown-Fence entfernt.")
    else:
        turtle_str = llm_response.strip()
        logger.warning("Keine Markdown-fences gefunden. Rohe LLM-Response wird genutzt.")

    # Backup, falls Regex scheitert
    turtle_str = turtle_str.replace("```turtle", "")
    turtle_str = turtle_str.replace("```rdf", "")
    turtle_str = turtle_str.replace("```xml", "")
    turtle_str = turtle_str.replace("```n3", "")
    turtle_str = turtle_str.replace("```", "")
    turtle_str = turtle_str.strip()

    # 2. Default-Namespace des Parsers durch Ontologie-Namespace ersetzen
    turtle_str = re.sub(
        r"@prefix\s+:\s*<http://example\.com/>\s*\.",
        "@prefix : <http://www.semanticweb.org/tim/ontologies/2026/3/untitled-ontology-32#> .",
        turtle_str,
    )

    # 3. Fehlende spitze Klammern um URIs in @prefix-Zeilen ergänzen
    turtle_str = re.sub(
        r"(@prefix\s+[\w-]*:\s+)(https?://[^\s<>]+?)(\s*\.)",
        r"\1<\2>\3",
        turtle_str,
    )

    # 4. Fehlende Präfixe adden
    defined_pres = set(re.findall(r"@prefix\s+([\w-]*):", turtle_str))
    added_pres = []
    for prefix, uri in STANDARD_PREFIXES.items():
        if prefix not in defined_pres:
            added_pres.append(f"@prefix {prefix}: <{uri}> .")
            logger.debug("Präfix hinzugefügt: %s", prefix)

    return turtle_str


async def guard_rail_layer(ontology_patch, scenario):
    step_message = ("Step 3/5: GUARD RAIL LAYER")
    await stream_text(step_message)

    # First syntax Check

    cleaned_llm_response = preprocess_llm_response(ontology_patch)
    syntax_valid, error_list, graph, fmt = await check_syntax(cleaned_llm_response)
    error_text = "\n".join(f"- {err}" for err in error_list)

    # Repair attempts if first syntax check fails

    onto_patch = cleaned_llm_response
    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        if syntax_valid:
            break
            
        await stream_text(f"Bad Syntax: Repair attempt {attempt} / {MAX_REPAIR_ATTEMPTS}")

        llm_response = await call_llm_repair(
            broken_turtle=cleaned_llm_response,
            error_text=error_text,
            scenario=scenario
        )

        onto_patch = preprocess_llm_response(llm_response=llm_response)
        syntax_valid, error_list, graph, fmt = await check_syntax(onto_patch)
        error_text = "\n".join(f"- {err}" for err in error_list)

    await stream_text(f"Syntax check: {syntax_valid}")  
    
    return syntax_valid, onto_patch, graph, error_text
