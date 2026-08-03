from config import ONTOLOGY_PATH, FINAL_ONTOLOGY_PATH
from functions import stream_text

from rdflib import Graph, URIRef
import logging

logger = logging.getLogger(__file__)

def diff_between_ontos(base_onto: Graph, patch_onto: Graph) -> tuple[set, set]:
        """
        Gibt die neu hinzugefügten und entfernten Triples zurück.
        removed_triples: im Patch explizit mit owl:deprecated=true markierte Entitäten.
        Args:
            base_onto (Graph): Basis-Ontologie
            patch_onto (Graph): Von LLM ausgegebener Ontologie-Patch
        Returns:
            durch LLM hinzugefügte Triples
            durch LLM entfernte Triples
        """
        patch_triples = set(patch_onto)
        base_triples  = set(base_onto)

        added   = patch_triples - base_triples

        # owl:deprecated Triples werden entfernt (siehe System Prompt in der config)
        removed = set()
        DEPRECATED = URIRef("http://www.w3.org/2002/07/owl#deprecated")
        for subj, _, obj in patch_onto.triples((None, DEPRECATED, None)):
            if str(obj).lower() in ("true", "1"):
                removed.update(base_onto.triples((subj, None, None)))
                removed.update(base_onto.triples((None, None, subj)))

        return added, removed

async def create_final_ontology(ontology_patch: Graph) -> Graph:
    base_onto = Graph()
    base_onto.parse(str(ONTOLOGY_PATH))

    added_triples, removed_triples = diff_between_ontos(
        base_onto=base_onto,
        patch_onto=ontology_patch
    )

    final_onto = Graph()

    # Namespaces übernehmen
    for prefix, namespace in base_onto.namespaces():
        final_onto.bind(prefix, namespace)
    for prefix, namespace in ontology_patch.namespaces():
        final_onto.bind(prefix, namespace)

    # Alle Triples aus Basis-Ontologie übernehmen, außer die entfernten
    for triple in base_onto:
        if triple not in removed_triples:
            final_onto.add(triple)

    for triple in ontology_patch:
        if triple in added_triples:
            final_onto.add(triple)

    logger.info(
        "Patch in Basis-Ontologie integriert."
        f"{len(added_triples)} Triples hinzugefügt."
        f"{len(removed_triples)} Triples entfernt."
    )

    return final_onto

async def ontology_merge(ontology_graph: Graph, path_to_save_ontology = FINAL_ONTOLOGY_PATH ):
    await stream_text("Step 4/5: ONTOLOGY MERGE")

    final_ontology = await create_final_ontology(ontology_graph)
    logger.info("Finale Ontologie wurde erstellt.")

    # Speichern der Ontologie 

    final_ontology.serialize(
        destination=path_to_save_ontology,
        format="xml"
    )

    final_message = (
        "Final Ontology saved as:\n"
        f"{path_to_save_ontology}\n\n"
    )
    await stream_text(final_message)