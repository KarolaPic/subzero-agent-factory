#!/usr/bin/env python3
"""Project Scaffolding Engine for External Projects.

Scaffolds external projects using official framework CLIs, installs project-source
skills via `npx skills add`, generates a validated .factory.yml adapter config,
and bootstraps public GitHub remotes with labels and webhooks.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any, Dict, List, Optional
import yaml

from scripts.git_identity import governed_identity
from scripts.project_adapter import validate_adapter_config

logger = logging.getLogger("scaffold_project")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

ROOT_DIR = Path(__file__).resolve().parent.parent

# Supported official framework CLIs and default verify/build configs
FRAMEWORK_TEMPLATES: Dict[str, Dict[str, Any]] = {
    "nextjs": {
        "framework": "node",
        "cli_cmd": ["npx", "--yes", "create-next-app@latest", "{name}", "--typescript", "--tailwind", "--eslint", "--app", "--src-dir", "--no-import-alias"],
        "verify_command": "npm test",
        "build_command": "npm run build",
        "package_manager": "npm",
    },
    "expo": {
        "framework": "node",
        "cli_cmd": ["npx", "--yes", "create-expo-app@latest", "{name}", "--template", "blank-typescript"],
        "verify_command": "npm test",
        "build_command": "npx expo export",
        "package_manager": "npm",
    },
    "vite": {
        "framework": "node",
        "cli_cmd": ["npm", "create", "vite@latest", "{name}", "--", "--template", "react-ts"],
        "verify_command": "npm test",
        "build_command": "npm run build",
        "package_manager": "npm",
    },
    "python": {
        "framework": "python",
        "cli_cmd": None,  # Custom python scaffold
        "verify_command": "pytest",
        "build_command": None,
        "package_manager": "pip",
    },
    "rust": {
        "framework": "rust",
        "cli_cmd": ["cargo", "new", "{name}"],
        "verify_command": "cargo test",
        "build_command": "cargo build",
        "package_manager": "cargo",
    },
    "go": {
        "framework": "go",
        "cli_cmd": ["go", "mod", "init", "{name}"],
        "verify_command": "go test ./...",
        "build_command": "go build ./...",
        "package_manager": "go",
    },
}


def generate_factory_config(
    project_name: str,
    framework: str,
    verify_command: str,
    package_manager: Optional[str] = None,
    build_command: Optional[str] = None,
    exclude_skills: Optional[List[str]] = None,
    base_branch: str = "main",
    memory_tier: str = "global",
) -> Dict[str, Any]:
    """Generates and validates .factory.yml dictionary matching adapter schema."""
    meta = FRAMEWORK_TEMPLATES.get(framework, {})
    schema_framework = meta.get("framework", framework if framework in ("node", "python", "rust", "go", "custom") else "custom")

    cfg: Dict[str, Any] = {
        "name": project_name,
        "framework": schema_framework,
        "base_branch": base_branch,
        "verify_command": verify_command,
        "memory_tier": memory_tier,
    }

    if build_command:
        cfg["build_command"] = build_command
    if package_manager:
        cfg["package_manager"] = package_manager
    if exclude_skills:
        cfg["exclude_skills"] = exclude_skills

    validate_adapter_config(cfg)
    return cfg


def install_project_skills(
    project_path: Path | str,
    skills: Optional[List[str]] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Installs project-source skills using `npx skills add` into target directory."""
    path = Path(project_path).resolve()
    target_skills = skills or ["find-skills"]
    installed: List[str] = []

    if dry_run:
        logger.info("[dry-run] Would install project skills %s into %s", target_skills, path)
        return {"success": True, "installed": target_skills, "dry_run": True}

    for skill in target_skills:
        repo_url = "https://github.com/vercel-labs/skills" if skill == "find-skills" else skill
        cmd = ["npx", "--yes", "skills", "add", repo_url, "--skill", skill]
        logger.info("Installing skill '%s' into %s: %s", skill, path, " ".join(cmd))
        try:
            res = subprocess.run(
                cmd,
                cwd=str(path),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode == 0:
                installed.append(skill)
            else:
                logger.warning("Failed to install skill %s: %s", skill, res.stderr.strip())
        except Exception as e:
            logger.error("Exception executing skills installer for %s: %s", skill, e)

    return {"success": True, "installed": installed, "dry_run": False}


def bootstrap_github_repository(
    repo_name: str,
    project_path: Path | str,
    public: bool = True,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Creates a remote repository on GitHub via `gh repo create` and pushes initial code."""
    path = Path(project_path).resolve()
    visibility_flag = "--public" if public else "--private"

    if dry_run:
        logger.info("[dry-run] Would create GitHub repo '%s' (%s) from %s", repo_name, visibility_flag, path)
        return {"success": True, "repo_name": repo_name, "dry_run": True}

    with governed_identity():
        # Ensure git repo is initialized locally
        subprocess.run(["git", "init", "-b", "main"], cwd=str(path), check=False)
        subprocess.run(["git", "add", "."], cwd=str(path), check=False)
        subprocess.run(["git", "commit", "-m", "chore: initial project scaffold"], cwd=str(path), check=False)

        cmd = [
            "gh", "repo", "create",
            repo_name,
            visibility_flag,
            "--source", str(path),
            "--push",
        ]
        logger.info("Creating GitHub repository: %s", " ".join(cmd))
        res = subprocess.run(cmd, cwd=str(path), capture_output=True, text=True, check=False)
        if res.returncode != 0:
            logger.error("gh repo create failed: %s", res.stderr.strip())
            return {"success": False, "error": res.stderr.strip()}

        repo_url = res.stdout.strip()
        return {"success": True, "repo_name": repo_name, "repo_url": repo_url, "dry_run": False}


def provision_project_labels(repo_slug: str, dry_run: bool = False) -> Dict[str, Any]:
    """Runs scripts/setup-labels.sh against target external repository."""
    if dry_run:
        logger.info("[dry-run] Would setup labels on %s", repo_slug)
        return {"success": True, "repo_slug": repo_slug, "dry_run": True}

    script_path = ROOT_DIR / "scripts" / "setup-labels.sh"
    env = os.environ.copy()
    env["GH_REPO"] = repo_slug

    logger.info("Provisioning factory labels on %s", repo_slug)
    res = subprocess.run(
        [str(script_path)],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        logger.warning("setup-labels.sh returned non-zero for %s: %s", repo_slug, res.stderr)
        return {"success": False, "error": res.stderr.strip()}

    return {"success": True, "repo_slug": repo_slug, "dry_run": False}


def configure_project_webhook(
    repo_slug: str,
    webhook_url: str,
    secret: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Configures repository issue webhook pointing to Subzero factory_daemon.py."""
    if dry_run:
        logger.info("[dry-run] Would configure webhook %s on %s", webhook_url, repo_slug)
        return {"success": True, "repo_slug": repo_slug, "webhook_url": webhook_url, "dry_run": True}

    api_path = f"repos/{repo_slug}/hooks"
    config_dict = {
        "url": webhook_url,
        "content_type": "json",
    }
    if secret:
        config_dict["secret"] = secret

    payload = {
        "name": "web",
        "active": True,
        "events": ["issues"],
        "config": config_dict,
    }

    cmd = [
        "gh", "api",
        "--method", "POST",
        "-H", "Accept: application/vnd.github+json",
        api_path,
        "--input", "-",
    ]
    logger.info("Configuring webhook on %s pointing to %s", repo_slug, webhook_url)
    res = subprocess.run(
        cmd,
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        check=False,
    )
    if res.returncode != 0:
        logger.error("Failed to configure webhook on %s: %s", repo_slug, res.stderr.strip())
        return {"success": False, "error": res.stderr.strip()}

    return {"success": True, "repo_slug": repo_slug, "webhook_url": webhook_url, "dry_run": False}


def scaffold_framework_project(
    project_name: str,
    framework: str = "nextjs",
    destination_parent: Optional[Path | str] = None,
    purpose: Optional[str] = None,
    exclude_skills: Optional[List[str]] = None,
    github: bool = False,
    public: bool = True,
    webhook_url: Optional[str] = None,
    dry_run: bool = False,
) -> Dict[str, Any]:
    """Scaffolds a new external project directory, writes .factory.yml, and optionally bootstraps remote."""
    dest_parent = Path(destination_parent or Path.cwd()).resolve()
    target_dir = dest_parent / project_name
    template = FRAMEWORK_TEMPLATES.get(framework, FRAMEWORK_TEMPLATES["nextjs"])

    logger.info("Scaffolding project '%s' (framework: %s) at %s", project_name, framework, target_dir)

    if not dry_run:
        dest_parent.mkdir(parents=True, exist_ok=True)
        target_dir.mkdir(parents=True, exist_ok=True)

    # 1. Run Framework CLI if defined
    cli_cmd = template.get("cli_cmd")
    if cli_cmd and not dry_run:
        formatted_cmd = [part.format(name=project_name) for part in cli_cmd]
        logger.info("Executing framework CLI: %s", " ".join(formatted_cmd))
        try:
            res = subprocess.run(
                formatted_cmd,
                cwd=str(dest_parent),
                capture_output=True,
                text=True,
                check=False,
            )
            if res.returncode != 0:
                logger.warning("Framework CLI returned non-zero code %s: %s", res.returncode, res.stderr)
        except Exception as e:
            logger.error("Failed to run framework CLI: %s", e)

    # 2. Generate .factory.yml
    config_dict = generate_factory_config(
        project_name=project_name,
        framework=framework,
        verify_command=template.get("verify_command", "npm test"),
        package_manager=template.get("package_manager"),
        build_command=template.get("build_command"),
        exclude_skills=exclude_skills,
    )

    if not dry_run:
        factory_yml_path = target_dir / ".factory.yml"
        with open(factory_yml_path, "w", encoding="utf-8") as f:
            yaml.dump(config_dict, f, default_flow_style=False, sort_keys=False)
        logger.info("Wrote adapter config to %s", factory_yml_path)

        # 3. Install project skills into project source
        install_project_skills(target_dir, skills=["find-skills"], dry_run=False)

    remote_res: Optional[Dict[str, Any]] = None
    if github:
        remote_res = bootstrap_github_repository(
            repo_name=project_name,
            project_path=target_dir,
            public=public,
            dry_run=dry_run,
        )
        if remote_res.get("success"):
            repo_slug = remote_res.get("repo_name", project_name)
            provision_project_labels(repo_slug, dry_run=dry_run)
            if webhook_url:
                configure_project_webhook(repo_slug, webhook_url, dry_run=dry_run)

    return {
        "success": True,
        "project_name": project_name,
        "framework": framework,
        "project_path": str(target_dir),
        "factory_config": config_dict,
        "github": remote_res,
        "dry_run": dry_run,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Scaffold external projects for Subzero Agent Factory.")
    parser.add_argument("--name", required=True, help="Target project name")
    parser.add_argument("--framework", default="nextjs", choices=list(FRAMEWORK_TEMPLATES.keys()), help="Target framework")
    parser.add_argument("--dir", default=".", help="Destination parent directory")
    parser.add_argument("--purpose", help="Brief purpose of the project")
    parser.add_argument("--exclude-skills", nargs="*", help="Skills to exclude")
    parser.add_argument("--github", action="store_true", help="Bootstrap GitHub remote repository")
    parser.add_argument("--public", action="store_true", default=True, help="Create repository as public (default: True)")
    parser.add_argument("--webhook-url", help="Webhook URL for factory_daemon.py")
    parser.add_argument("--dry-run", action="store_true", help="Simulate without executing")

    args = parser.parse_args()
    res = scaffold_framework_project(
        project_name=args.name,
        framework=args.framework,
        destination_parent=args.dir,
        purpose=args.purpose,
        exclude_skills=args.exclude_skills,
        github=args.github,
        public=args.public,
        webhook_url=args.webhook_url,
        dry_run=args.dry_run,
    )
    print(json.dumps(res, indent=2))


if __name__ == "__main__":
    main()
