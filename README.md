# GuardCode Agent

A coding agent for trustworthy software development — autonomous file editing and command execution with pre-execution risk gating and test-driven feedback loops.

## Overview

GuardCode Agent interacts with LLMs (via OpenAI-compatible API) to autonomously read/write files and execute commands. Key features:

- **Agent Loop**: Self-implemented multi-turn tool calling with bounded iteration
- **Security Critic**: Pre-write code scanning (eval/exec/os.system detection) + pre-execution command risk classification
- **Test-Driven Fix**: Automatically find and run tests after code changes, analyze failures, and iterate on fixes
- **Workspace Isolation**: All operations restricted to a resolved workspace boundary
- **Three-Layer Visibility**: Model feedback + terminal output (Rich) + persistent logging

## Tech Stack

- Python 3.10+
- `openai` — model API client
- `rich` — terminal formatting
- Standard library: `pathlib`, `subprocess`, `logging`, `json`, `re`

## Quick Start

```bash
# Install dependencies
pip install openai rich

# Set API key
export OPENAI_API_KEY="your-key-here"

# Run
python -m guardcode "implement quicksort in Python with tests"

# Specify workspace
python -m guardcode --workspace /path/to/project "fix the bug in main.py"
```

## Project Structure

```
guardcode/
├── __main__.py          # CLI entry point
├── agent.py             # Core agent loop
├── tools/               # File and command tools
├── security/            # Risk classification + code scanning
├── context/             # Context management and compression
├── ui/                  # Rich terminal output
└── config.py            # Configuration loading
```

## Design Documents

- [SPEC.md](docs/SPEC.md) — Design specification
- [PLAN.md](docs/PLAN.md) — Implementation plan
- [TASKS.md](docs/TASKS.md) — Task checklist

## License

MIT
