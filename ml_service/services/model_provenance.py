"""Source digests used to identify the exact checked-in equation implementation."""
import hashlib
import inspect
from pathlib import Path
from typing import Any


def source_model_version(model_class: Any) -> str:
    path = Path(inspect.getsourcefile(model_class) or "").resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return f"{model_class.__module__}:{model_class.__name__}@sha256:{digest}"
