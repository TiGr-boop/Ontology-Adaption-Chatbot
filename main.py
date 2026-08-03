from src.create_collection import create_collection_from_ontology
from src.start_chatbot import start_chainlit
import logging

logger = logging.getLogger(__name__)

def main():
    create_collection_from_ontology()
    start_chainlit()

if __name__ == "__main__":
    main()