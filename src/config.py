from pathlib import Path

### PARAMETERS ###

EMBEDDING_MODEL = "all-MiniLM-L12-v2"
CHROMA_COLLECTION_NAME = "ODD_embeddings"
LLM_MODEL = 'llama3:8b'#gpt-5.6' #'gpt-5'     #'llama3.2:1b' zu klein
REPAIR_MODEL = 'codellama:7b'#'gpt-5' 
OPENAI_API_KEY = ""
NUM_RETRIEVED_CHUNKS_QR = 584
NUM_RETRIEVED_CHUNKS_CO = 584
MAX_REPAIR_ATTEMPTS = 2



### OPTIONS ###

STREAMING_SPEED = 0   # Number equals the delay per stream --> the smaller the faster
SHOW_CHUNKS = False   # Defines if the retrieved Chunks for Requirement Extraction get streamed to Chainlit --> not recommended for large Number of Chunks  



### PATHS ###

ONTOLOGY_DIR = Path(__file__).resolve().parent.parent
ONTOLOGY_PATH = ONTOLOGY_DIR / "ontology.rdf"
FINAL_ONTOLOGY_PATH = ONTOLOGY_DIR / "final_ontology.rdf"



### FORMATTING OF THE ONTOLOGY PATCH ###

ONTOLOGY_NAMESPACE = "http://www.semanticweb.org/tim/ontologies/2026/3/untitled-ontology-32#"
SUPPORTED_FORMATS = ["turtle", "xml", "n3", "nt", "json-ld"]
STANDARD_PREFIXES = {
    "owl":  "http://www.w3.org/2002/07/owl#",
    "rdf":  "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd":  "http://www.w3.org/2001/XMLSchema#",
}



### SYSTEM PROMPTS ###

SYSTEM_PROMPT = f"""
You are an ontology expert and get a change request of an existing ontology.

1. Respond ONLY with valid Turtle syntax inside a single ```turtle ... ``` code block.
2. Do NOT output explanations, markdown text, or prose outside the Turtle block.
3. Generate ONLY a minimal differential patch.
4. Do NOT regenerate the entire ontology.
5. Preserve and reuse the existing namespace prefixes:
{STANDARD_PREFIXES}
6. Newly created entities MUST use the existing ontology namespace.
7. All generated axioms MUST remain OWL-DL compliant.
8. Every changed entity MUST include exactly one rdfs:comment in English describing the semantic purpose of the change.
9. rdfs:comment annotations are supplemental only and NEVER sufficient on their own.
10. Every requested ontology modification MUST produce at least one structural OWL/RDF change such as:
   - rdf:type
   - rdfs:subClassOf
   - owl:Restriction
   - owl:deprecated
   - owl:equivalentClass
   - owl:disjointWith
   - owl:ObjectProperty
   - owl:DatatypeProperty
   - owl:NamedIndividual
   - domain/range axioms
   - property assertions
"""

REPAIR_SYSTEM_PROMPT = """
You are an RDF/Turtle syntax expert.
You receive a broken Turtle snippet and the parser error messages.
Output ONLY the corrected Turtle inside a single ```turtle ... ``` block.
Do NOT explain anything. Do NOT add prose. Fix ONLY syntax errors.
"""

CONSISTENCY_SYSTEM_PROMPT = """
You are an RDF/Turtle syntax expert.
You receive a broken Turtle snippet and the reasoning error messages.
Output ONLY the corrected Turtle inside a single ```turtle ... ``` block.
Do NOT explain anything. Do NOT add prose. Fix ONLY consistency errors.
"""

REWRITE_PROMPT = """
You are an ontology requirements analyst for OWL-DL ontologies in the domain of autonomous hospital transport systems.

Your task:
Transform the user scenario into the MINIMAL set of ontology changes needed.

Output requirements:
1. Output ONLY a numbered list of concrete ontology changes in English.
2. Each requirement must name the exact entity (class, property, or individual) to be created or modified.
3. Reference ONLY existing ontology entities from the provided chunks.
4. Do NOT output Turtle syntax.
5. Do NOT output explanations or prose outside the numbered list.
6. Do NOT add classes, properties or individuals that are already part of the given chunks.

Requirement format:
- For new classes: "Add class <ClassName> as subclass of <ExistingClass>."
- For new properties: "Add ObjectProperty <PropertyName> with domain <Class> and range <Class>."
- For new individuals: "Add individual <IndividualName> of type <Class>."
- For modifications: "Modify class <ClassName>: add restriction [...]."
- For object property assertions: "Add assertion <Subject> <ObjectProperty> <Object>."
- For data property assertions: "Add assertion <Subject> <DataProperty> "<LiteralValue>"^^<Datatype>."
- For class modifications:
  "Modify class <ClassName>: add restriction <Restriction>."
- For object property modifications:
  "Modify ObjectProperty <PropertyName>: <Modification>."
- For data property modifications:
  "Modify DataProperty <PropertyName>: <Modification>."
- For removals:
  "Remove assertion <Subject> <Property> <Object>."
  "Remove individual <IndividualName>."
  "Remove class <ClassName>."
You do NOT need to add new classes, properties, individuals and assertions. For some usecases only a single class or a single property may be enough.
"""