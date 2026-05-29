### IMPORTS

from pathlib import Path
import logging
import rdflib
import sys
from sentence_transformers import SentenceTransformer
import chromadb
from src.functions import chunk_ontology
from src.config import EMBEDDING_MODEL, ONTOLOGY_PATH, CHROMA_COLLECTION_NAME


def create_collection_from_ontology():
    """
    Zerlegt die Ontologie und speichert sie encodiert in einer Chroma DB.
    """

    ### LOGGER INITIALIZATION

    logging.basicConfig(
        filename='ODD-Log.log',
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    )
    logger = logging.getLogger("ODD-RAG")
    print("Logger initialisiert")

    OWL_ENTITY_TYPES = {
        rdflib.OWL.Class,
        rdflib.OWL.ObjectProperty,
        rdflib.OWL.DatatypeProperty,
        rdflib.OWL.NamedIndividual,
    }

    if not ONTOLOGY_PATH.exists():
        logger.warning(f"Ontologie-Datei '{ONTOLOGY_PATH}' nicht gefunden.")
        sys.exit(f"Ontologie-Datei '{ONTOLOGY_PATH}' nicht gefunden.")

    logger.info(f"Lade Ontologie '{ONTOLOGY_PATH}'")
    onto = rdflib.Graph()
    onto.parse(str(ONTOLOGY_PATH))
    chunks = chunk_ontology(onto, OWL_ENTITY_TYPES)

    texts = [c["text"] for c in chunks]
    ids = [f"chunk_{i}" for i, _ in enumerate(chunks)]
    metas    = [{
                "chunk_id":     c["chunk_id"],
                "label":        c["label"],
                "entity_type":  c["entity_type"],
                "turtle":       c["turtle"]
            } for c in chunks]

    embedder = SentenceTransformer(EMBEDDING_MODEL)
    embeddings = embedder.encode(texts, show_progress_bar=True).tolist()

    client = chromadb.PersistentClient(path="./chroma_db")

    try:
        client.delete_collection(name=CHROMA_COLLECTION_NAME)
        collection = client.create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=None
        )
    except:
        collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=None
        )

    collection.add(
        ids=ids,
        embeddings=embeddings,
        documents=texts,
        metadatas=metas
    )

    return collection