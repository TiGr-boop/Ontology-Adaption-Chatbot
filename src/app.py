from functions import stream_text
from req_extraction import requirement_extraction
from patch_generation import ontology_patch_generation
from guardrail import guard_rail_layer
from onto_merge import ontology_merge
from reasoning import reasoning
from config import (
    ONTOLOGY_PATH,
    LLM_MODEL,
    REPAIR_MODEL,
    )

import chainlit as cl
import logging

logger = logging.getLogger(__file__)

### CHAINLIT GUI

@cl.step(type="tool")
async def tool():
    # Fake tool
    await cl.sleep(2)
    return "Response from the tool!"

@cl.on_chat_start
async def on_start():
    await cl.Message(
        content=(
            f"Loaded Ontology: `{ONTOLOGY_PATH}`\n"
            f"Language Model Interpretation: `{LLM_MODEL}`\n"
            f"Language Model Code Generation: `{REPAIR_MODEL}`"
            "\n\nDescribe a scenario the ODD should get adapted to."
        )
    ).send()


@cl.on_message  # this function will be called every time a user inputs a message in the UI
async def main(message: cl.Message):
    """
    STEP 1: REQUIREMENT EXTRACTION
    STEP 2: ONTOLOGY PATCH GENERATION
    STEP 3: GUARD RAIL LAYER
    STEP 4: ONTOLOGY MERGE
    STEP 5: REASONING
    """

    scenario = message.content

    ### STEP 1 QUERY REWRITING ###

    rewritten_scenario = await requirement_extraction(scenario=scenario)

    ### STEP 2: ONTOLOGY PATCH GENERATION ###

    llm_response = await ontology_patch_generation(rewritten_scenario=rewritten_scenario)

    ### STEP 3: GUARD RAIL LAYER ###

    syntax_valid, onto_patch, graph, error_text = await guard_rail_layer(ontology_patch=llm_response)

    if not syntax_valid:
        await stream_text(f"Syntax not valid!\n{error_text}")
        return
  
    ### Step 4: ONTOLOGY MERGE ###

    await ontology_merge(graph)

    ### STEP 5: REASONING ####

    await reasoning(onto_patch=onto_patch)