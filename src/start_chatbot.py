import subprocess
import sys
import logging

from src.config import ONTOLOGY_DIR

logger = logging.getLogger(__file__)

def start_chainlit():
    subprocess.run(
        [
            sys.executable,
            "-m",
            "chainlit",
            "run",
            str(ONTOLOGY_DIR / "src" / "app.py"),
            "--port",
            "8000",
        ],
        cwd=ONTOLOGY_DIR,
        check=True,
    )