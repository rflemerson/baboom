# Nix Environment

## Overview

- Nix support lives in `.idx/dev.nix`.
- Do not manually document or install system packages ad hoc if they belong in the dev environment.

## Rules

- Add system dependencies to the Nix environment when they are genuinely required for development.
- Keep runtime container concerns in Docker config, not in Nix docs.
