# GuardCode Agent

A coding agent for trustworthy software development — autonomous file editing and command execution with pre-execution risk gating and test-driven feedback loops.

## Overview

GuardCode Agent interacts with LLMs (via OpenAI-compatible API) to autonomously read/write files and execute commands. Key features:

- **Agent Loop**: Self-implemented multi-turn tool calling with bounded iteration
- **Security Critic**: Pre-write code scanning (eval/exec/os.system detection) + pre-execution command risk classification
- **Test-Driven Fix**: Automatically find and run tests after code changes, analyze failures, and iterate on fixes
- **Workspace Isolation**: All operations restricted to a resolved workspace boundary
- **Three-Layer Visibility**: Model feedback + terminal output (Rich) + persistent logging
- **Context Compression**: Two-level compression (rule-based + optional LLM summary) with write-invalidation and lazy re-reading
- **Error Recovery**: Model call retry with exponential backoff, session save on interrupt

## Tech Stack

- Python 3.10+
- `openai` — model API client
- `rich` — terminal formatting
- Standard library: `pathlib`, `subprocess`, `logging`, `json`, `re`

## Installation

```bash
# Clone the repository
git clone https://github.com/yourusername/guardcode-agent.git
cd guardcode-agent

# Install dependencies
pip install -r requirements.txt
```

## Quick Start

```bash
# Set API key
export OPENAI_API_KEY="your-key-here"

# Run a task
python -m guardcode "implement quicksort in Python with tests"

# Specify workspace
python -m guardcode --workspace /path/to/project "fix the bug in main.py"

# Use a different model
python -m guardcode --model gpt-4o "write a REST API server"

# Use a custom API endpoint (e.g., DeepSeek)
python -m guardcode --api-base https://api.deepseek.com/v1 --model deepseek-chat "refactor auth module"

# Verbose mode
python -m guardcode --verbose "implement a stack with push/pop/peek"

# Check version
python -m guardcode --version
```

## CLI Parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `task` | Programming task for the agent (required) | — |
| `--workspace PATH` | Workspace directory | Current directory |
| `--model NAME` | Model name override | From config or `gpt-4-turbo` |
| `--api-base URL` | API endpoint URL override | From config or OpenAI |
| `--max-iterations N` | Maximum loop iterations | 50 |
| `--config PATH` | Path to config file | Auto-discovered |
| `--verbose` | Enable verbose output | Off |
| `--version` | Show version number | — |

## Configuration

### Configuration Files

GuardCode Agent loads configuration in the following order (later overrides earlier):

1. **Default config** — built-in defaults
2. **Global config** — `~/.guardcode/config.json`
3. **Environment variables** — `OPENAI_API_KEY`, `OPENAI_API_BASE`, etc.
4. **Project config** — `{workspace}/.guardcode.json`
5. **CLI config** — `--config PATH` (highest priority)

### Example Configuration

```json
{
  "api_base": "https://api.openai.com/v1",
  "model": "gpt-4-turbo",
  "max_iterations": 10,
  "security": {
    "always_block": [
      "rm -rf /",
      "format c:",
      "dd if=/dev/zero"
    ],
    "auto_approve": [
      "ls",
      "pwd",
      "cat",
      "echo"
    ]
  },
  "context": {
    "max_context_size": 100000,
    "keep_recent_messages": 5
  },
  "verbose": false
}
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `OPENAI_API_KEY` | API key for the model provider (required) |
| `OPENAI_API_BASE` | API endpoint URL |
| `GUARDCODE_MODEL` | Default model name |
| `GUARDCODE_MAX_ITERATIONS` | Default max iterations |
| `GUARDCODE_VERBOSE` | Enable verbose output (`1`, `true`, `yes`) |

## Architecture

### Three-Layer Design

```
┌──────────────────────────────────────────────────┐
│ Layer 1: Execution State (Current Turn)          │
│ - response["tool_calls"] ← execution source     │
│ - Absolutely not compressible                    │
└──────────────────────────────────────────────────┘
                    ↓ After execution
┌──────────────────────────────────────────────────┐
│ Layer 2: Context (messages list)                 │
│ - Conversation history (volatile memory)         │
│ - Compressible: write-invalidation, lazy re-read │
└──────────────────────────────────────────────────┘
                    ↓ Source of Truth
┌──────────────────────────────────────────────────┐
│ Layer 3: Workspace (file system)                 │
│ - Real file content                               │
│ - read_file reads from disk every time           │
└──────────────────────────────────────────────────┘
```

### Project Structure

```
guardcode/
├── __main__.py              # CLI entry point
├── agent.py                 # Core agent loop
├── config.py                # Configuration loading
├── model.py                 # OpenAI-compatible model adapter
├── workspace.py             # Workspace management & path validation
├── tools/
│   ├── base.py              # Tool registry & execution
│   ├── file_tools.py        # File operations (read/write/list/delete)
│   └── command_tools.py    # Command execution
├── security/
│   ├── risk_classifier.py   # Risk classification (SAFE/DANGEROUS/BLOCKED)
│   ├── code_scanner.py      # Static code risk scanning
│   └── user_confirm.py      # Interactive confirmation prompts
├── context/
│   ├── manager.py           # Context size estimation
│   └── compressor.py        # Two-level context compression
└── ui/
    └── console.py           # Rich terminal output & logging
```

### Security Features

- **Risk Classification**: Commands are classified as SAFE, DANGEROUS, or BLOCKED before execution
- **Code Scanning**: Python files are scanned for risky patterns (eval, exec, os.system, etc.) before writing
- **User Confirmation**: Dangerous operations require explicit user approval
- **Workspace Isolation**: All file operations are restricted to the workspace boundary

### Context Compression

Two-level compression strategy:

1. **Level 1 (Rule-based)**:
   - Write invalidation: After write/delete, old read results are marked stale
   - Lazy re-reading: Large results compressed to metadata placeholders
   - Tool call compression: Large write_file content arguments compressed
   - Working set preservation: Recent N messages kept intact

2. **Level 2 (LLM Summary, optional)**: When Level 1 compression is insufficient, an LLM generates a summary

### Logging

Logs are persisted to `~/.guardcode/logs/agent.log` with format:
```
2024-01-15 10:23:45 | INFO     | guardcode | Tool: read_file({"path": "main.py"})
2024-01-15 10:23:46 | WARN     | guardcode | Risk: eval at line 42
2024-01-15 10:23:47 | ERROR    | guardcode | Model call failed: Connection timeout
```

### Error Handling

- **Model call retry**: 3 retries with exponential backoff (1s, 2s, 4s)
- **User interrupt**: Ctrl+C saves conversation history to `~/.guardcode/sessions/`
- **Log write fallback**: All logging calls wrapped in try/except

## Design Documents

- [SPEC.md](docs/SPEC.md) — Design specification
- [PLAN.md](docs/PLAN.md) — Implementation plan
- [TASKS.md](docs/TASKS.md) — Task checklist

## FAQ

### How do I use a non-OpenAI model?

GuardCode Agent supports any OpenAI-compatible API. Use `--api-base` to specify the endpoint:

```bash
# DeepSeek
python -m guardcode --api-base https://api.deepseek.com/v1 --model deepseek-chat "task"

# Kimi
python -m guardcode --api-base https://api.moonshot.cn/v1 --model moonshot-v1-8k "task"
```

### How do I auto-approve certain commands?

Add them to the `auto_approve` list in your config file:

```json
{
  "security": {
    "auto_approve": ["git status", "pytest"]
  }
}
```

### How do I block certain commands?

Add them to the `always_block` list in your config file:

```json
{
  "security": {
    "always_block": ["rm -rf /", "sudo"]
  }
}
```

### Where are logs stored?

Logs are stored at `~/.guardcode/logs/agent.log`.

### Where are interrupted sessions saved?

Sessions are saved at `~/.guardcode/sessions/{timestamp}.json`.

## License

MIT
