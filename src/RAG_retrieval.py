from sentence_transformers import SentenceTransformer
from config import EMBEDDING_MODEL, CHROMA_COLLECTION_NAME, NUM_RETRIEVED_CHUNKS
import logging
import chromadb

def retrieve(prompt: str):
    """
    Gibt die semantisch ähnlichsten Chunks zurück basierend auf dem eingegebenen Prompt.
    Args:
        prompt (Str): Eingabe durch den User in Chainlit UI
    """

    logger = logging.getLogger("ODD-RAG")

    # embedding of the user input
    embedder = SentenceTransformer(EMBEDDING_MODEL)
    embedding = embedder.encode([prompt]).tolist()
    logger.info("Encoding of prompt completed.")

    # Retrieve Collection
    client = chromadb.PersistentClient(path="./chroma_db")
    collection = client.get_or_create_collection(
            name=CHROMA_COLLECTION_NAME,
            embedding_function=None
        )
    
    retrieval_results = collection.query(
        query_embeddings=embedding,
        n_results=NUM_RETRIEVED_CHUNKS,
        include=["documents", "metadatas", "distances"]
    )

    chunks = []
    for document, metadata, distance in zip(
        #[0] dahinter, weil Ergebnisse noch mal in einer Liste pro Query. In dem Fall gibts nur eine Query, deshalb erstes Ergebnis nehmen.
        retrieval_results["documents"][0],
        retrieval_results["metadatas"][0],
        retrieval_results["distances"][0],
    ):
        chunks.append({"text": document, **metadata, "distance": distance})
    logger.info(f"RAG retrieved '{len(chunks)}' chunks from Ontology.")

    return chunks        

    
