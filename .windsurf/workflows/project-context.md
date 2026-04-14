---
description: Load DSOA project instructions and coding standards for all work
---

Before starting any task, read and follow the project instructions:

1. Read `.github/copilot-instructions.md` for complete project context including:
   - Architecture (plugin-based, triad pattern)
   - Code style requirements (black, flake8, pylint 10.00/10)
   - Testing requirements (pytest, dual-mode mock/live)
   - Documentation standards
   - Delivery process (Proposal → Plan → Implementation)

2. Always use the Python virtual environment at `.venv/`

3. Run `make lint` before considering any change complete
