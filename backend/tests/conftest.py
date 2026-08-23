import sys
import os
import pytest
from pathlib import Path

# ── 1. sys.path ───────────────────────────────────────────────────────────────
backend_dir = Path(__file__).parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

# ── 2. Force all temp I/O to D: drive ─────────────────────────────────────────
_D_TMP = Path(r"D:\projects\Deepfake_agenticai\data\tmp")
_D_TMP.mkdir(parents=True, exist_ok=True)

os.environ["TMPDIR"] = str(_D_TMP)
os.environ["TEMP"]   = str(_D_TMP)
os.environ["TMP"]    = str(_D_TMP)

import tempfile as _tempfile
_tempfile.tempdir = str(_D_TMP)


def pytest_configure(config):
    """Redirect pytest's own basetemp (tmp_path fixture) to D: drive."""
    if config.option.basetemp is None:
        basetemp = _D_TMP / "pytest"
        basetemp.mkdir(parents=True, exist_ok=True)
        config.option.basetemp = str(basetemp)


# ── 3. Redirect structlog output to stderr during tests ───────────────────────
# Pytest captures stdout through a temp file on C: drive.
# Structlog writing to stdout → C: temp → OSError: No space left on device.
# Writing to sys.stderr bypasses pytest's stdout capture entirely.

@pytest.fixture(autouse=True, scope="session")
def redirect_structlog_to_stderr():
    """
    Reconfigure structlog to write to sys.stderr instead of sys.stdout.
    sys.stderr is not routed through pytest's temp-file-based capture,
    so this eliminates the C:-drive space dependency during test runs.
    """
    import structlog
    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.dev.ConsoleRenderer(colors=False),
        ],
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
    )
    yield

