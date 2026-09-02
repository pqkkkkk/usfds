import json
from pathlib import Path
from typing import Any, Dict, Optional, Union
import yaml

from usfds_core.domain.schemas.preprocessing_config import PreprocessingConfig


def load_preprocessing_config(config_path: Union[str, Path]) -> PreprocessingConfig:
    """Loads and validates a PreprocessingConfig from a YAML or JSON file."""
    path = Path(config_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Config file not found: {path}")

    content = path.read_text(encoding="utf-8")
    if path.suffix.lower() in [".yaml", ".yml"]:
        raw_dict = yaml.safe_load(content)
    elif path.suffix.lower() == ".json":
        raw_dict = json.loads(content)
    else:
        try:
            raw_dict = yaml.safe_load(content)
        except Exception:
            raw_dict = json.loads(content)

    if not isinstance(raw_dict, dict):
        raise ValueError(f"Config file must define a dictionary/mapping, got {type(raw_dict).__name__}")

    return PreprocessingConfig(**raw_dict)


def get_default_config_dict() -> Dict[str, Any]:
    """Returns a dictionary representation of the default PreprocessingConfig."""
    default_config = PreprocessingConfig()
    return default_config.model_dump(mode="json")


def dump_template_config(output_path: Optional[Union[str, Path]] = None, fmt: str = "yaml") -> str:
    """Generates and optionally writes a template configuration file."""
    config_dict = get_default_config_dict()
    if fmt.lower() == "json":
        formatted = json.dumps(config_dict, indent=2)
    else:
        formatted = yaml.dump(config_dict, sort_keys=False, default_flow_style=False)

    if output_path is not None:
        p = Path(output_path).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(formatted, encoding="utf-8")

    return formatted
