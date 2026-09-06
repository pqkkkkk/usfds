"""Global constants and environment configurations for USFDS Core."""

import os
from pathlib import Path
import tempfile

# Root temporary workspace directory for USFDS local tasks (training, preprocessing, etc.)
# Can be customized via USFDS_WORKSPACE_ROOT environment variable.
DEFAULT_WORKSPACE_ROOT: Path = Path(
    os.getenv("USFDS_WORKSPACE_ROOT", Path(tempfile.gettempdir()) / "usfds")
)
