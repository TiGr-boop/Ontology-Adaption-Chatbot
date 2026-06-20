from pathlib import Path

EMBEDDING_MODEL = "all-MiniLM-L6-v2"
ONTOLOGY_PATH = Path("ontology.rdf")
ONTOLOGY_DIR = Path(ONTOLOGY_PATH).parents[0]
FINAL_ONTOLOGY_PATH = ONTOLOGY_DIR / "final_ontology.rdf"
ONTOLOGY_NAMESPACE = "http://www.semanticweb.org/tim/ontologies/2026/3/untitled-ontology-32#"
CHROMA_COLLECTION_NAME = "ODD_embeddings"
NUM_RETRIEVED_CHUNKS = 1
SUPPORTED_FORMATS = ["turtle", "xml", "n3", "nt", "json-ld"]
STANDARD_PREFIXES = {
    "owl":  "http://www.w3.org/2002/07/owl#",
    "rdf":  "http://www.w3.org/1999/02/22-rdf-syntax-ns#",
    "rdfs": "http://www.w3.org/2000/01/rdf-schema#",
    "xsd":  "http://www.w3.org/2001/XMLSchema#",
}
MAX_REPAIR_ATTEMPTS = 2

# LLM Config
LLM_MODEL = 'llama3:8B'    #'llama3.2:1b' zu klein
REPAIR_MODEL = 'codellama:7b'
OPENAI_API_KEY = ""



SYSTEM_PROMPT = f"""1. Respond ONLY with valid Turtle syntax inside a single ```turtle ... ``` code block.
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

RESULT_DESCRIPTION_SYSTEM_PROMPT = """
You are an RDF/Turtle expert.
You receive a Turtle patch. This patch will be added to a base ontology.
Describe the Turtle patch and what it changes in the base ontology with natural language in german.
"""

REWRITE_PROMPT = f"""You are an ontology requirements analyst for OWL-DL ontologies in the domain of autonomous hospital transport systems.

Your task:
Transform the user scenario into the MINIMAL set of ontology changes needed.

Rules:

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
You do NOT need to add new classes, properties and individuals. For some usecases only a single class or a single property may be enough.

Existing ontology chunks:

"""