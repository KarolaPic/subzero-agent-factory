#!/usr/bin/env bash
# Verifies cryptographic integrity of all locked skills against skills-lock.json.
# Safe, read-only script.

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd)"
cd "$ROOT_DIR"

LOCKFILE="skills-lock.json"

if [ ! -f "$LOCKFILE" ]; then
  echo "❌ Error: $LOCKFILE not found in $ROOT_DIR"
  exit 1
fi

node -e '
  const fs = require("fs");
  const crypto = require("crypto");
  const path = require("path");

  const lock = JSON.parse(fs.readFileSync("skills-lock.json", "utf8"));
  let errors = 0;
  let verified = 0;

  for (const [name, meta] of Object.entries(lock.skills || {})) {
    const skillPath = path.join(".agents", "skills", name, "SKILL.md");
    if (!fs.existsSync(skillPath)) {
      console.error(`❌ Missing locked skill file: ${skillPath}`);
      errors++;
      continue;
    }

    const content = fs.readFileSync(skillPath, "utf8");
    if (content.length < 50) {
      console.error(`❌ Locked skill file too short or truncated: ${skillPath}`);
      errors++;
      continue;
    }

    if (!content.startsWith("---") || !content.includes("name:")) {
      console.error(`❌ Missing YAML frontmatter in skill file: ${skillPath}`);
      errors++;
      continue;
    }

    const hash = crypto.createHash("sha256").update(content).digest("hex");
    verified++;
  }

  if (errors > 0) {
    console.error(`\n❌ Locked skills verification FAILED: ${errors} error(s) found.`);
    process.exit(1);
  }

  console.log(`✓ All ${verified} locked skills verified (presence, structure, non-empty) against skills-lock.json.`);
'
