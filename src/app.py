import chainlit as cl
from chainlit import server as chainlit_server
from config import ONTOLOGY_PATH, LLM_MODEL, MAX_REPAIR_ATTEMPTS, FINAL_ONTOLOGY_PATH, REPAIR_MODEL
from RAG_retrieval import retrieve
from llm import (
    build_llm_prompt,
    call_llm,
    call_llm_repair,
    call_llm_change_description,
    call_llm_reasoning_repair,
    rewrite_scenario
)
from guardrail import preprocess_llm_response, check_syntax
from final_onto import create_final_ontology
import logging
from asyncio import to_thread, sleep
from owlready2 import sync_reasoner_hermit, OwlReadyInconsistentOntologyError, get_ontology

logger = logging.getLogger("ODD-RAG")

async def stream_text(text: str, delay: float = 0.01):
    msg = cl.Message(content="")
    await msg.send()
    
    for char in text:
        await msg.stream_token(char)
        await sleep(delay)
    
    await msg.update()
    return msg




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
            f"Sprachmodell: `{LLM_MODEL}`\n\n"
            "Beschreibe ein Szenario, an das die ODD angepasst werden soll."
        )
    ).send()


@cl.on_message  # this function will be called every time a user inputs a message in the UI
async def main(message: cl.Message):
    """
    STEP 1: RAG-RETRIEVAL of relevant ontology chunks
    STEP 2: QUERY REWRITING
    STEP 3: Generating an Ontology Patch (LLM RESPONSE)
    STEP 4: GUARD RAIL LAYER (Syntax-Prüfung)
    STEP 5: Zusammensetzen der Ontologie (FINAL ONTOLOGY)
    STEP 6: Reasoner
    """

    scenario = message.content

    ### STEP 1: RAG RETRIEVAL ###

    step_message = "Step 1/6: Retrieving corresponding chunks from Ontology."
    await stream_text(step_message)

    retrieved_chunks = retrieve(scenario)
    chunk_text = "\n".join(f"- {chunk['text']}" for chunk in retrieved_chunks)
    retrieval_message = (f"Gefundenen Entitäten (Chunks):\n{chunk_text}")
    await stream_text(retrieval_message)



    ### STEP 2 QUERY REWRITING ###

    step_message = (
        "Step 2/6: Query Rewriting\n"
        "Rewrites the Query based on the scenario and the retrieved chunks.\n"
        "Afterwards another retrieval process is initiated based on the rewritten Query"
        )
    await stream_text(step_message)

    rewritten_scenario = await rewrite_scenario(scenario, retrieved_chunks)

    retrieved_chunks = retrieve(rewritten_scenario)



    ### STEP 3: LLM RESPONSE ###

    step_message = ("Step 3/6: LLM generates a new Ontology Patch.")
    await stream_text(step_message)

    prompt = build_llm_prompt(rewritten_scenario, retrieved_chunks)
    logger.info("Prompt created.")

    llm_response = await call_llm(prompt, model=REPAIR_MODEL)

    logger.info(f"Received response from LLM.\n{llm_response}")



    ### STEP 4: GUARD RAIL LAYER ###

    step_message = ("Step 4/6: Syntax-Überprüfung.")
    await stream_text(step_message)

    # Erste Syntax-Prüfung

    cleaned_llm_response = preprocess_llm_response(llm_response=llm_response)
    llm_response_message = (
        f"Das ist die Antwort des LLMs:\n"
        "```turtle\n"
        f"{cleaned_llm_response}\n"
        "```")
    await stream_text(llm_response_message)

    logger.info(f"Cleaned LLM-Response:\n{cleaned_llm_response}")
    syntax_valid, error_list, graph, fmt = await check_syntax(cleaned_llm_response)
    error_text = "\n".join(f"- {err}" for err in error_list)

    # Wenn fehlschlägt Repair-Versuche

    onto_patch = cleaned_llm_response
    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):
        if syntax_valid:
            break
            
        await stream_text(f"Syntax ungültig: Repair-Versuch {attempt} / {MAX_REPAIR_ATTEMPTS}")

        llm_response = await call_llm_repair(
            broken_turtle=cleaned_llm_response,
            error_text=error_text,
        )

        onto_patch = preprocess_llm_response(llm_response=llm_response)

        syntax_valid, error_list, graph, fmt = await check_syntax(onto_patch)
        error_text = "\n".join(f"- {err}" for err in error_list)

    await stream_text(f"Syntax check: {syntax_valid}")

    # Bestätigung in Chainlit

    if not syntax_valid:
        error_message = cl.Message(error_text)
        await error_message.send()

        return
  


    ### Step 5: FINAL ONTOLOGY ###

    await stream_text("Step 5/6: Erstellung der finalen Ontologie.")

    final_ontology = await create_final_ontology(graph)
    logger.info("Finale Ontologie wurde erstellt.")

    # Speichern der Ontologie 

    final_ontology.serialize(
        destination=FINAL_ONTOLOGY_PATH,
        format="xml"
    )

    await call_llm_change_description(onto_patch)


    final_message = (
        "Finale Ontologie gespeichert unter:\n"
        f"{FINAL_ONTOLOGY_PATH}\n\n"
    )
    await stream_text(final_message)



    ### STEP 6: REASONER ####

    step_message = ("Step 6/6: Reasoning.")
    await stream_text(step_message)

    final_onto = get_ontology(str(FINAL_ONTOLOGY_PATH)).load()

    reasoning_valid = False
    reasoning_error = ""

    for attempt in range(1, MAX_REPAIR_ATTEMPTS + 1):

        try:
            with final_onto:
                await to_thread(sync_reasoner_hermit, infer_property_values=False)
            logger.info("Reasoning erfolgreich.")
            reasoning_message = "Reasoning erfolgreich."
            await stream_text(reasoning_message)
            reasoning_valid = True
            break

        except OwlReadyInconsistentOntologyError as e:
            reasoning_error = str(e)
            logger.warning(f"Reasoning fehlgeschlagen (Versuch {attempt}): {reasoning_error}")

            if attempt >= MAX_REPAIR_ATTEMPTS:
                break

            reasoning_message = (
                f"Ontologie inkonsistent: Repair Versuch {attempt} / {MAX_REPAIR_ATTEMPTS}."
                f"Fehlermeldung:\n{reasoning_error}"
            )

            await stream_text(reasoning_message)

            llm_response = await call_llm_reasoning_repair(
                broken_turtle=onto_patch,
                error_text=reasoning_error,
            )

            onto_patch = preprocess_llm_response(llm_response=llm_response)

            syntax_valid, error_list, graph, _ = await check_syntax(onto_patch)
            if not syntax_valid:
                check_message = "Repair erzeugte Syntaxfehler."
                error_text = "\n".join(f"- {err}" for err in error_list)
                check_message = (check_message.join(error_text))
                await stream_text(check_message)
                break
            
            final_ontology = await create_final_ontology(graph)
            final_ontology.serialize(destination=FINAL_ONTOLOGY_PATH, format="xml")

        except Exception as e:
            logger.error(f"HermiT-Fehler: {e}")
            reasoning_message = (f"HermiT-Fehler.\n{e}")
            await stream_text(reasoning_message)

    if not reasoning_valid:
        reasoning_error_message = (f"Reasoning nach {MAX_REPAIR_ATTEMPTS} Versuchen fehlgeschlagen.\n{reasoning_error}")
        await stream_text(reasoning_error_message)