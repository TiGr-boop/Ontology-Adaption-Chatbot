from functions import stream_text
from config import NUM_RETRIEVED_CHUNKS_CO, REPAIR_MODEL
from RAG_retrieval import retrieve
from llm import build_llm_prompt, call_llm

import logging

logger = logging.getLogger(__name__)

async def ontology_patch_generation(rewritten_scenario: str) -> str:
    step_message = ("Step 2/5: ONTOLOGY PATCH GENERATION")
    await stream_text(step_message)

    retrieved_chunks = retrieve(rewritten_scenario, NUM_RETRIEVED_CHUNKS_CO)

    prompt = build_llm_prompt(rewritten_scenario, retrieved_chunks)
    logger.info("Prompt created.")

    llm_response = await call_llm(prompt, model=REPAIR_MODEL)

    logger.info(f"Received response from LLM.\n{llm_response}")

    return llm_response