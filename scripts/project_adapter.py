#!/usr/bin/env python3
"""Project Adapter and Zero-Config Framework Detection Engine.

Discovers build/test verification commands from standard frameworks (Node.js,
Python, Rust, Go) with zero target configuration, and provides schema validation
for .factory.yml overrides.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
import yaml

ROOT_DIR = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA_PATH = ROOT_DIR / ".factory" / "schemas" / "factory-adapter.schema.json"


class SchemaValidationError(Exception):
    """Raised when .factory.yml violates factory-adapter.schema.json."""


def detect_framework(project_path: Path | str) -> Dict[str, Any]:
    """Auto-detects framework and test/build commands based on standard project markers."""
    path = Path(project_path).resolve()

    # 1. Node.js
    if (path / "package.json").is_file():
        return {
            "framework": "node",
            "verify_command": "npm test",
            "package_manager": "npm",
            "base_branch": "main",
        }

    # 2. Python
    if any((path / f).is_file() for f in ("pyproject.toml", "requirements.txt", "setup.py")):
        return {
            "framework": "python",
            "verify_command": "pytest",
            "package_manager": "pip",
            "base_branch": "main",
        }

    # 3. Rust
    if (path / "Cargo.toml").is_file():
        return {
            "framework": "rust",
            "verify_command": "cargo test",
            "package_manager": "cargo",
            "base_branch": "main",
        }

    # 4. Go
    if (path / "go.mod").is_file():
        return {
            "framework": "go",
            "verify_command": "go test ./...",
            "package_manager": "go",
            "base_branch": "main",
        }

    # Fallback / Custom
    return {
        "framework": "custom",
        "verify_command": "true",
        "package_manager": None,
        "base_branch": "main",
    }


def validate_adapter_config(
    config: Dict[str, Any],
    schema_path: Optional[Path | str] = None,
) -> bool:
    """Validates configuration dictionary against factory-adapter.schema.json."""
    sch_p = Path(schema_path or DEFAULT_SCHEMA_PATH).resolve()
    if not sch_p.is_file():
        raise SchemaValidationError(f"Schema file not found at {sch_p}")

    with open(sch_p, "r", encoding="utf-8") as f:
        schema = json.load(f)

    if not isinstance(config, dict):
        raise SchemaValidationError("Configuration must be a dictionary")

    allowed_properties = schema.get("properties", {})
    additional_allowed = schema.get("additionalProperties", True)

    # 1. Check for unauthorized properties
    if not additional_allowed:
        for k in config:
            if k not in allowed_properties:
                raise SchemaValidationError(f"Unauthorized property '{k}' in configuration")

    # 2. Check property types and enums
    for k, val in config.items():
        if k not in allowed_properties:
            continue
        prop_schema = allowed_properties[k]
        expected_type = prop_schema.get("type")

        if expected_type == "string" and not isinstance(val, str):
            raise SchemaValidationError(f"Property '{k}' must be string, got {type(val).__name__}")
        elif expected_type == "array" and not isinstance(val, list):
            raise SchemaValidationError(f"Property '{k}' must be array, got {type(val).__name__}")
        elif expected_type == "object" and not isinstance(val, dict):
            raise SchemaValidationError(f"Property '{k}' must be object, got {type(val).__name__}")

        if "enum" in prop_schema and val not in prop_schema["enum"]:
            raise SchemaValidationError(
                f"Invalid value '{val}' for property '{k}'. Allowed: {prop_schema['enum']}"
            )

    return True


class ProjectAdapter:
    """Encapsulates resolved project configuration and verification adapters."""

    def __init__(self, data: Dict[str, Any]):
        self.name: Optional[str] = data.get("name")
        self.framework: str = data.get("framework", "custom")
        self.base_branch: str = data.get("base_branch", "main")
        self.verify_command: str = data.get("verify_command", "true")
        self.build_command: Optional[str] = data.get("build_command")
        self.package_manager: Optional[str] = data.get("package_manager")
        self.exclude_skills: List[str] = data.get("exclude_skills") or []
        self.github_user: Optional[str] = data.get("github_user")
        self.git_email: Optional[str] = data.get("git_email")
        self.memory_tier: str = data.get("memory_tier", "global")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "framework": self.framework,
            "base_branch": self.base_branch,
            "verify_command": self.verify_command,
            "build_command": self.build_command,
            "package_manager": self.package_manager,
            "exclude_skills": self.exclude_skills,
            "github_user": self.github_user,
            "git_email": self.git_email,
            "memory_tier": self.memory_tier,
        }


def load_project_adapter(project_path: Path | str) -> ProjectAdapter:
    """Loads and resolves project adapter, merging zero-config detection with .factory.yml."""
    path = Path(project_path).resolve()
    detected = detect_framework(path)

    # Check for .factory.yml or .factory.yaml
    config_file = None
    for cand in (".factory.yml", ".factory.yaml"):
        p = path / cand
        if p.is_file():
            config_file = p
            break

    merged = dict(detected)

    if config_file:
        with open(config_file, "r", encoding="utf-8") as f:
            user_config = yaml.safe_load(f) or {}

        validate_adapter_config(user_config)
        for k, v in user_config.items():
            if v is not None:
                merged[k] = v

    return ProjectAdapter(merged)


if __name__ == "__main__":
    import pprint
    target = sys.argv[1] if len(sys.argv) > 1 else "."
    adapter = load_project_adapter(target)
    pprint.pprint(adapter.to_dict())
