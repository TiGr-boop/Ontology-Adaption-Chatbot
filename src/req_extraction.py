from functions import stream_text
from RAG_retrieval import retrieve
from config import NUM_RETRIEVED_CHUNKS_QR, SHOW_CHUNKS
from llm import call_llm_req_extraction

import logging

logger = logging.getLogger(__name__)

async def requirement_extraction(scenario: str) -> str:
    await stream_text("Step 1/5: REQUIREMENT EXTRACTION\n")

    retrieved_chunks = retrieve(scenario, num_chunks=NUM_RETRIEVED_CHUNKS_QR)
    logger.info(f"Es wurden {NUM_RETRIEVED_CHUNKS_QR} Chunks aus der Vektordatenbank abgerufen.")
    chunk_text = "\n".join(f"- {chunk['text']}" for chunk in retrieved_chunks)
    retrieval_message = (f"Found Entities (Chunks):\n{chunk_text}")
    if SHOW_CHUNKS:
        await stream_text(retrieval_message)

    rewritten_scenario = await call_llm_req_extraction(scenario, retrieved_chunks)
    logger.info(f"Änderungsanforderungsliste:\n{rewritten_scenario}")

    return rewritten_scenario