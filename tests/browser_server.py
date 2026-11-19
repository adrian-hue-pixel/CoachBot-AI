"""Isolated Streamlit browser-test server."""

from contextlib import contextmanager
import os
from pathlib import Path
import socket
import subprocess
import sys
from time import monotonic, sleep
from urllib.error import URLError
from urllib.request import urlopen

import pytest

ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def server(tmp_path, script):
    with socket.socket() as port_probe:
        port_probe.bind(("127.0.0.1", 0))
        port = port_probe.getsockname()[1]
    url = f"http://127.0.0.1:{port}"
    env = os.environ | {"PYTHONPATH": str(ROOT)}
    env.pop("GEMINI_API_KEY", None)
    empty_secrets = tmp_path / "empty.toml"
    empty_secrets.write_text("# Demo browser fixture\n", encoding="utf-8")
    logfile = tmp_path / "streamlit.log"
    with logfile.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [sys.executable, "-m", "streamlit", "run", str(ROOT / script),
             "--server.headless=true", "--server.fileWatcherType=none", "--server.address=127.0.0.1",
             f"--server.port={port}", "--browser.gatherUsageStats=false",
             f"--secrets.files={empty_secrets}"],
            cwd=ROOT, env=env, stdout=log, stderr=log,
        )
        try:
            expires = monotonic() + 20
            while monotonic() < expires and process.poll() is None:
                try:
                    with urlopen(url + "/_stcore/health", timeout=0.3) as response:
                        if response.status == 200:
                            break
                except (OSError, URLError):
                    sleep(.1)
            else:
                pytest.fail(logfile.read_text(encoding="utf-8"))
            yield url
        finally:
            if process.poll() is None:
                process.terminate()
                process.wait(timeout=10)

