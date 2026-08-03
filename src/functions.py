import rdflib
import logging
import asyncio
import chainlit as cl
from collections import deque

from src.config import STREAMING_SPEED

logger = logging.getLogger("ODD-RAG")

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
        for subj, _, _ in graph.triples((None, rdflib.RDF.type, entity_type)):
            if isinstance(subj, rdflib.URIRef):
                entities[subj] = entity_type.toPython().rsplit("#", 1)[-1]

    # Erstellt Subgraph für jede Entität
    for uri, e_type in entities.items():
        sub_graph = rdflib.Graph()

        # fügt Triples hinzu inkl. Blank Nodes
        queue = deque([uri])
        visited = set()

        while queue:
            current = queue.popleft()

            if current in visited:
                continue

            visited.add(current)

            for subj, pred, obj in graph.triples((current, None, None)):
                sub_graph.add((subj, pred, obj))

                if isinstance(obj, rdflib.BNode):
                    queue.append(obj)
        
        if e_type in ("ObjectProperty", "DatatypeProperty"):

            for restriction, _, _ in graph.triples(
                    (None, rdflib.OWL.onProperty, uri)):

                queue = deque([restriction])
                visited = set()

                while queue:

                    current = queue.popleft()

                    if current in visited:
                        continue

                    visited.add(current)

                    # Restriktions-Tripel
                    for s, p, o in graph.triples((current, None, None)):
                        sub_graph.add((s, p, o))

                        if isinstance(o, rdflib.BNode):
                            queue.append(o)

                    # Welche Klasse verwendet diese Restriktion?
                    for cls, pred, obj in graph.triples((None, None, current)):
                        sub_graph.add((cls, pred, obj))
                       
        # Serialisiert den Subgraphen einer jeden Entität
        turtle_str = sub_graph.serialize(format="turtle")
        label = get_label(graph, uri)

        text_parts = [f"Entität: {label}"]

        if e_type == "Class":

            for _, pred, obj in sub_graph.triples((uri, None, None)):

                pred_local = pred.split("#")[-1].split("/")[-1]

                if isinstance(obj, rdflib.URIRef):
                    obj_local = obj.split("#")[-1].split("/")[-1]
                    text_parts.append(f"{pred_local}: {obj_local}")

            # Restriktionen verständlich darstellen
            for restriction, _, _ in graph.triples((None, rdflib.OWL.onProperty, None)):

                # Wird diese Restriktion von der Klasse verwendet?
                if (uri, rdflib.RDFS.subClassOf, restriction) not in graph:
                    continue

                prop = graph.value(restriction, rdflib.OWL.onProperty)
                some = graph.value(restriction, rdflib.OWL.someValuesFrom)
                only = graph.value(restriction, rdflib.OWL.allValuesFrom)

                if prop:

                    prop_name = str(prop).split("#")[-1].split("/")[-1]

                    if some:
                        filler = str(some).split("#")[-1].split("/")[-1]
                        text_parts.append(
                            f"Restriction: {label} {prop_name} some {filler}"
                        )

                    if only:
                        filler = str(only).split("#")[-1].split("/")[-1]
                        text_parts.append(
                            f"Restriction: {label} {prop_name} only {filler}"
                        )

        elif e_type == "ObjectProperty":

            domain = graph.value(uri, rdflib.RDFS.domain)
            range_ = graph.value(uri, rdflib.RDFS.range)

            if domain:
                text_parts.append(
                    f"Domain: {str(domain).split('#')[-1].split('/')[-1]}"
                )

            if range_:
                text_parts.append(
                    f"Range: {str(range_).split('#')[-1].split('/')[-1]}"
                )

            # Wo wird die Property verwendet?
            for restriction, _, _ in graph.triples((None, rdflib.OWL.onProperty, uri)):

                some = graph.value(restriction, rdflib.OWL.someValuesFrom)
                only = graph.value(restriction, rdflib.OWL.allValuesFrom)

                for cls, _, _ in graph.triples((None, rdflib.RDFS.subClassOf, restriction)):

                    cls_name = str(cls).split("#")[-1].split("/")[-1]

                    if some:
                        filler = str(some).split("#")[-1].split("/")[-1]
                        text_parts.append(
                            f"Used by: {cls_name} -> {label} some {filler}"
                        )

                    if only:
                        filler = str(only).split("#")[-1].split("/")[-1]
                        text_parts.append(
                            f"Used by: {cls_name} -> {label} only {filler}"
                        )

        elif e_type == "DatatypeProperty":

            domain = graph.value(uri, rdflib.RDFS.domain)
            range_ = graph.value(uri, rdflib.RDFS.range)

            if domain:
                text_parts.append(
                    f"Domain: {str(domain).split('#')[-1].split('/')[-1]}"
                )

            if range_:
                text_parts.append(
                    f"Range: {str(range_)}"
                )

        elif e_type == "NamedIndividual":

            for _, pred, obj in sub_graph.triples((uri, None, None)):

                pred_local = pred.split("#")[-1].split("/")[-1]

                if isinstance(obj, rdflib.URIRef):
                    obj_local = obj.split("#")[-1].split("/")[-1]
                else:
                    obj_local = str(obj)

                text_parts.append(f"{pred_local}: {obj_local}")

        chunks.append({
            "chunk_id": str(uri),
            "label": label,
            "entity_type": e_type,
            "turtle": turtle_str,
            "text": "\n".join(text_parts),
        })

    logger.info("Chunking abgeschlossen: %d Entitäts-Chunks erzeugt.", len(chunks))
    return chunks

async def stream_text(text: str, delay: float = STREAMING_SPEED):
    msg = cl.Message(content="")
    await msg.send()
    
    for char in text:
        await msg.stream_token(char)
        await asyncio.sleep(delay)
    
    await msg.update()
    return msg


