import subprocess
import sys
from pathlib import Path

from src.config import ONTOLOGY_DIR


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