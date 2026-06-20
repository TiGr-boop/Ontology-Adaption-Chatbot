import rdflib
import logging
import subprocess
import webbrowser
import time
from src.config import ONTOLOGY_DIR, ONTOLOGY_PATH, REWRITE_PROMPT, ONTOLOGY_NAMESPACE
from rdflib import Graph, URIRef
import asyncio
import chainlit as cl

logger = logging.getLogger("ODD-RAG")

def start_chatbot():
    """
    Öffnet Chainlit im Browser.
    """
    process = subprocess.Popen(
        ["chainlit", "run", "src/app.py", "--port", "8000"],
        cwd=ONTOLOGY_DIR)
    time.sleep(3)  # Warten bis Server hochgefahren ist
    webbrowser.open("http://localhost:8000")
    return process

def get_label(graph: rdflib.Graph, uri: rdflib.URIRef) -> str:
    """
    Gibt das Label einer URI zurück.
    Wenn kein Label vergeben ist, wird stattdessen der Name aus der URI genommen.
    """

    for _, _, obj in graph.triples((uri, rdflib.namespace.RDFS.label, None)):
        return str(obj) 
    uri_name = str(uri).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
    return uri_name

def chunk_ontology(graph: rdflib.Graph,
                   owl_entity_types: set[rdflib.URIRef],
                   ) -> list[dict]:
    """
    Zerlegt die gegebene Ontologie in Chunks, wobei jeder Eintrag einer Entität entspricht.
    Chunks enthalten:
    - URI
    - Label
    - Entitätstyp, z.B. Klasse, ObjectProperty, etc.
    - Turtle-Serialisierung der Triple dieser Entität
    - Beschreibungstext für Embedding
    """

    chunks = []
    entities = {}   # ein Dict für jede Entität

    # Dict aller Entitäten mit ihren Typen
    # Keys sind die URIs, Values der Typ
    for entity_type in owl_entity_types:
        for subj, pred, obj in graph.triples((None, rdflib.RDF.type, entity_type)):
            if isinstance(subj, rdflib.URIRef):
                entities[subj] = entity_type.toPython().rsplit("#", 1)[-1]

    # Erstellt Subgraph für jede Entität
    for uri, e_type in entities.items():
        sub_graph = rdflib.Graph()
        
        for triple in graph.triples((uri, None, None)):
            sub_graph.add(triple)

        # Serialisiert den Subgraphen einer jeden Entität
        turtle_str = sub_graph.serialize(format="turtle")
        label = get_label(graph, uri)

        text_parts = [f"Entität: {label} (Typ: {e_type})"]
        for _, pred, obj in sub_graph.triples((uri, None, None)):
            pred_local = str(pred).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            obj_str = str(obj).rsplit("#", 1)[-1].rsplit("/", 1)[-1]
            text_parts.append(f"{pred_local}: {obj_str}")

        chunks.append({
            "chunk_id":    str(uri),
            "label":       label,
            "entity_type": e_type,
            "turtle":      turtle_str,
            "text":        "\n".join(text_parts),
        })

    logger.info("Chunking abgeschlossen: %d Entitäts-Chunks erzeugt.", len(chunks))
    return chunks
