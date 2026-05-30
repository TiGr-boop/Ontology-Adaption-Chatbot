import chainlit as cl
from chainlit import server as chainlit_server
from config import ONTOLOGY_PATH, LLAMA_MODEL, MAX_REPAIR_ATTEMPTS, FINAL_ONTOLOGY_PATH
from RAG_retrieval import retrieve
from llm import build_llm_prompt, call_llm, call_llm_repair, call_llm_change_description
from guardrail import preprocess_llm_response, check_syntax
from final_onto import create_final_ontology
import logging
from asyncio import to_thread
from owlready2 import sync_reasoner_hermit, OwlReadyInconsistentOntologyError, get_ontology

logger = logging.getLogger("ODD-RAG")


CHOSEN_REASONER = "TO BE DEFINED"

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
            f"Geladene Ontologie: `{ONTOLOGY_PATH}`\n"
            f"Sprachmodell: `{LLAMA_MODEL}`\n"
            f"Reasoner: '{CHOSEN_REASONER}'\n\n"
            "Beschreibe ein Szenario, an das die ODD angepasst werden soll."
        )
    ).send()


@cl.on_message  # this function will be called every time a user inputs a message in the UI
async def main(message: cl.Message):
    """
    STEP 1: RAG-RETRIEVAL of relevant ontology chunks
    STEP 2: Generating an Ontology Patch (LLM RESPONSE)
    STEP 3: GUARD RAIL LAYER (Syntax-Prüfung)
    STEP 4: Zusammensetzen der Ontologie (FINAL ONTOLOGY)
    STEP 5: Reasoner
    """

    scenario = message.content

    ### STEP 1: RAG RETRIEVAL ###

    step_message = cl.Message("Step 1/5: Retrieving corresponding chunks from Ontology.")
    await step_message.send()

    retrieved_chunks = retrieve(scenario)
    retrieval_message = cl.Message(f"Retrieved {len(retrieved_chunks)} Chunks.")
    await retrieval_message.send()



    ### STEP 2: LLM RESPONSE ###

    step_message = cl.Message("Step 2/5: LLM generates a new Ontology Patch.")
    await step_message.send()

    prompt = build_llm_prompt(scenario, retrieved_chunks)
    logger.info("Prompt created.")

    llm_response = await call_llm(prompt)
    llm_message = cl.Message(content=(
        "--- RAW LLM RESPONSE ---"
        f"{llm_response}"
        )
    )
    await llm_message.send()

    logger.info("Received response from LLM.")



    ### STEP 3: GUARD RAIL LAYER ###

    step_message = cl.Message("Step 3/5: Syntax-Überprüfung.")
    await step_message.send()

    # Erste Syntax-Prüfung

    cleaned_llm_response = preprocess_llm_response(llm_response=llm_response)
    syntax_valid, error_list, graph, fmt = await check_syntax(cleaned_llm_response)
    error_text = "\n".join(f"- {err}" for err in error_list)

    # Wenn fehlschlägt Repair-Versuche

    onto_patch = cleaned_llm_response
    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        if syntax_valid:
            break
            
        await cl.Message(f"Syntax ungültig: Repair-Versuch {attempt} / {MAX_REPAIR_ATTEMPTS}").send()

        onto_patch = await call_llm_repair(
            broken_turtle=cleaned_llm_response,
            error_text=error_text,
        )

        syntax_valid, error_list, graph, fmt = await check_syntax(onto_patch)
        error_text = "\n".join(f"- {err}" for err in error_list)

    check_message = cl.Message(f"Syntax check: {syntax_valid}")
    await check_message.send()

    # Bestätigung in Chainlit

    if not syntax_valid:
        error_message = cl.Message(error_text)
        await error_message.send()

        return


    final_rdf_block_message = cl.Message(
        content=(
            "--- FINAL RDF BLOCK ---\n\n"
            f"{onto_patch}"
        )
    )
    await final_rdf_block_message.send()
    



    ### Step 4: FINAL ONTOLOGY ###

    step_message = cl.Message("Step 4/5: Erstellung der finalen Ontologie.")
    await step_message.send()

    final_ontology, _, _ = await create_final_ontology(graph)
    logger.info("Finale Ontologie wurde erstellt.")

    # Speichern der Ontologie 

    final_ontology.serialize(
        destination=FINAL_ONTOLOGY_PATH,
        format="xml"
    )

    description_message = await call_llm_change_description(onto_patch)


    final_message = cl.Message(
        "Finale Ontologie gespeichert unter:\n"
        f"{FINAL_ONTOLOGY_PATH}\n\n"
        f"{description_message}"
    )
    await final_message.send()



    ### STEP 5: REASONER ####

    step_message = cl.Message("Step 5/5: Reasoning.")
    await step_message.send()

    final_onto = get_ontology(str(FINAL_ONTOLOGY_PATH)).load()

    try:
        with final_onto:
            await to_thread(sync_reasoner_hermit, infer_property_values=False)
        logger.info("Reasoning erfolgreich.")
        reasoning_message = cl.Message("Reasoning erfolgreich.")
    except OwlReadyInconsistentOntologyError as e:
        logger.warning(
            "Resoning fehlgeschlagen. Ontologie ist inkonsistent\n"
            f"{e}"
            )
        reasoning_message = cl.Message(
            "Reasoning fehlgeschlagen. Ontologie ist inkonsistent."
            f"{e}"
        )
    except Exception as e:
        logger.error(f"HermiT-Fehler: {e}")
        reasoning_message = cl.Message(
            "HermiT-Fehler."
            f"{e}"
        )

    await reasoning_message.send()