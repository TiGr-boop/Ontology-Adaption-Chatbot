from functions import stream_text
from llm import call_llm_reasoning_repair
from guardrail import preprocess_llm_response, check_syntax
from onto_merge import create_final_ontology
from config import FINAL_ONTOLOGY_PATH, MAX_REPAIR_ATTEMPTS

from asyncio import to_thread
from owlready2 import sync_reasoner_hermit, get_ontology, OwlReadyInconsistentOntologyError
import logging

logger = logging.getLogger(__file__)

async def run_reasoner(onto):
    with onto:
        await to_thread(sync_reasoner_hermit, infer_property_values=False)


async def reasoning_repair(onto_patch, error):
    llm_response = await call_llm_reasoning_repair(
        broken_turtle=onto_patch,
        error_text=error,
    )

    onto_patch = preprocess_llm_response(llm_response)

    syntax_valid, error_list, graph, _ = await check_syntax(onto_patch)

    if not syntax_valid:
        check_message = "Repair attempt resulted in syntax error."
        error_text = "\n".join(f"- {err}" for err in error_list)
        check_message = (check_message.join(error_text))
        await stream_text(check_message)
        return None, False

    final_ontology = await create_final_ontology(graph)
    final_ontology.serialize(destination=FINAL_ONTOLOGY_PATH, format="xml")

    return  onto_patch, True


async def repair_reasoning_loop(onto_patch):
    for attempt in range(MAX_REPAIR_ATTEMPTS):

        onto = get_ontology(str(FINAL_ONTOLOGY_PATH)).load()

        try:
            await run_reasoner(onto)
            return True, ""

        except OwlReadyInconsistentOntologyError as e:
            error = str(e)

            await stream_text(
                f"Reasoning failed (attempt {attempt+1})"
            )

            onto_patch, success = await reasoning_repair(onto_patch, error)

            if not success:
                break
            
        except Exception as e:
            error = str(e)
            logger.error(f"HermiT Error:\n{e}")
            await stream_text(f"HermiT-Error.\n\n{e}")

    return False, error

async def reasoning(onto_patch):

    consistent, error = await repair_reasoning_loop(onto_patch)

    if consistent:
        await stream_text("Reasoning successful")
    else:
        await stream_text(f"Reasoning failed: {error}")

    return consistent