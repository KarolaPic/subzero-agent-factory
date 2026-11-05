#!/usr/bin/env python3
"""Validation utility for models.yml against models.allowed.yml.

Enforces:
1. models.yml and models.allowed.yml exist and are valid YAML.
2. All required roles (builder, auditor, planner, epic_planner, subagents, scorer) are specified.
3. Every role's model is in the allowed models list.
4. The auditor model MUST NOT be the same as the builder model.
5. Forbidden models (Argon, Claude, GPT) are completely rejected.
"""

import os
import sys
import yaml

REQUIRED_ROLES = ["builder", "auditor", "planner", "epic_planner", "subagents", "scorer"]
FORBIDDEN_PATTERNS = ["argon", "claude", "gpt", "openai", "anthropic"]


def load_yaml(filepath):
    if not os.path.exists(filepath):
        raise FileNotFoundError(f"Configuration file not found: {filepath}")
    with open(filepath, "r", encoding="utf-8") as f:
        try:
            return yaml.safe_load(f)
        except yaml.YAMLError as exc:
            raise ValueError(f"Failed to parse YAML in {filepath}: {exc}") from exc


def get_allowed_models(allowed_path):
    data = load_yaml(allowed_path)
    if isinstance(data, list):
        return [str(m).strip() for m in data if m]
    if isinstance(data, dict):
        models = data.get("models") or data.get("allowed_models") or []
        if isinstance(models, list):
            return [str(m).strip() for m in models if m]
    raise ValueError(f"Could not parse allowed models list from {allowed_path}")


def validate_models(models_path, allowed_path):
    allowed_models = get_allowed_models(allowed_path)
    if not allowed_models:
        raise ValueError(f"No allowed models defined in {allowed_path}")

    # Check for forbidden models in allowed list itself
    for model in allowed_models:
        for forbidden in FORBIDDEN_PATTERNS:
            if forbidden in model.lower():
                raise ValueError(f"Forbidden model '{model}' found in allowed list {allowed_path}")

    data = load_yaml(models_path)
    if not isinstance(data, dict):
        raise ValueError(f"{models_path} must be a YAML dictionary of role to model mappings")

    errors = []

    # 1. Check all required roles are present
    for role in REQUIRED_ROLES:
        if role not in data or not data[role]:
            errors.append(f"Missing required role: '{role}'")

    # 2. Check each role against allowed list & forbidden patterns
    for role, model in data.items():
        if role not in REQUIRED_ROLES:
            continue
        model_str = str(model).strip()
        if model_str not in allowed_models:
            errors.append(f"Role '{role}' uses unauthorized model '{model_str}'. Allowed: {', '.join(allowed_models)}")
        for forbidden in FORBIDDEN_PATTERNS:
            if forbidden in model_str.lower():
                errors.append(f"Role '{role}' uses forbidden model '{model_str}'")

    # 3. Check builder != auditor
    builder_model = str(data.get("builder", "")).strip()
    auditor_model = str(data.get("auditor", "")).strip()
    if builder_model and auditor_model and builder_model == auditor_model:
        errors.append(f"Auditor model ('{auditor_model}') must differ from builder model ('{builder_model}')")

    if errors:
        raise ValueError("\n".join(errors))

    return data


def main():
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    models_path = os.environ.get("MODELS_YML", os.path.join(root_dir, "models.yml"))
    allowed_path = os.environ.get("MODELS_ALLOWED_YML", os.path.join(root_dir, "models.allowed.yml"))

    try:
        data = validate_models(models_path, allowed_path)
        print("✓ models.yml is valid:")
        for role in REQUIRED_ROLES:
            print(f"  - {role}: {data.get(role)}")
        sys.exit(0)
    except Exception as exc:
        print(f"✗ Validation failed for models.yml:\n{exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
