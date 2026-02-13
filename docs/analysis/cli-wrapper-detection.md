# CLI Wrapper Detection Analysis

> Date: 2026-02-13
> Machine: macOS arm64 (Darwin 25.2.0)
> psutil version: via `uv run`

## Problem Statement

Many modern AI CLI tools are **wrappers** around Node.js or Python interpreters. When psutil reads `proc.name()`, it returns the interpreter name (`node`, `python`) or an unexpected binary name (e.g., `2.1.39` for Claude Code), **not** the tool name. Our current detection based on `process_names` in `ai_config.yaml` fails silently for these tools.

## Tool Inventory — What psutil Actually Sees

### 1. Claude Code (Mach-O binary, version-named)

```
Installation: ~/.local/bin/claude -> ~/.local/share/claude/versions/2.1.39
Binary type:  Mach-O 64-bit executable arm64
File naming:  The binary IS the version number (2.1.39)
```

**psutil output (VERIFIED on running process PID 65627):**
```
proc.name()    = "2.1.39"           # ← The version number!
proc.exe()     = "/Users/qveys/.local/share/claude/versions/2.1.39"
proc.cmdline() = ["claude", "--resume", "49958b5c-...", "--dangerously-skip-permissions"]
```

**For agent sub-processes (PID 84375):**
```
proc.name()    = "2.1.39"
proc.exe()     = "/Users/qveys/.local/share/claude/versions/2.1.39"
proc.cmdline() = ["/Users/qveys/.local/share/claude/versions/2.1.39", "--agent-id", "explorer-cli@..."]
```

**Key insight:** `proc.name()` returns `"2.1.39"` (useless), but:
- `proc.exe()` path contains `/claude/` → **reliable**
- `cmdline[0]` = `"claude"` for user-launched instances → **reliable**
- Agent sub-processes use full path in cmdline[0], but path still contains `/claude/`

### 2. Gemini CLI (Node.js script)

```
Installation: ~/.nvm/.../bin/gemini -> ../lib/node_modules/@google/gemini-cli/dist/index.js
Script type:  #!/usr/bin/env node (JavaScript)
```

**Expected psutil output:**
```
proc.name()    = "node"
proc.exe()     = "/Users/qveys/.nvm/versions/node/v24.13.0/bin/node"
proc.cmdline() = ["node", "/.../@google/gemini-cli/dist/index.js", ...]
```

**Key insight:** `proc.name()` returns `"node"` (ambiguous — hundreds of node processes). But:
- `cmdline` contains `gemini-cli` in the script path → **reliable**
- Cannot use `proc.exe()` (just points to node binary)

### 3. Codex CLI (Native Mach-O binary, arch-qualified name)

```
Installation: /opt/homebrew/bin/codex -> /opt/homebrew/Caskroom/codex/0.99.0/codex-aarch64-apple-darwin
Binary type:  Mach-O 64-bit executable arm64
```

**Expected psutil output:**
```
proc.name()    = "codex-aarch64-apple-darwin"  # ← Architecture-qualified!
proc.exe()     = "/opt/homebrew/Caskroom/codex/0.99.0/codex-aarch64-apple-darwin"
proc.cmdline() = ["codex", ...] or ["/opt/homebrew/.../codex-aarch64-apple-darwin", ...]
```

**Key insight:** `proc.name()` returns `"codex-aarch64-apple-darwin"` (contains `codex` but not exact match). Fix:
- Substring match: `"codex" in name.lower()` → **reliable**
- `proc.exe()` path contains `codex` → **reliable**

### 4. Vibe / Mistral Vibe (Python script via uv)

```
Installation: ~/.local/bin/vibe -> ~/.local/share/uv/tools/mistral-vibe/bin/vibe
Script type:  #!/.../uv/tools/mistral-vibe/bin/python (Python shebang)
```

**Expected psutil output:**
```
proc.name()    = "python"  (or "python3")
proc.exe()     = "/Users/qveys/.local/share/uv/tools/mistral-vibe/bin/python"
proc.cmdline() = ["/...uv/tools/mistral-vibe/bin/python", "/...uv/tools/mistral-vibe/bin/vibe", ...]
```

**Key insight:** `proc.name()` returns `"python"` (ambiguous). But:
- `proc.exe()` path contains `mistral-vibe` → **reliable**
- `cmdline` contains `vibe` or `mistral-vibe` → **reliable**

### 5. Aider (Python script via pip/uv)

```
Installation: typically ~/.local/bin/aider or via pipx/uv
Script type:  Python shebang
```

**Expected psutil output:** Same pattern as Vibe — `proc.name()` = `"python"`, need cmdline/exe fallback.

### 6. Ollama (Native binary, well-behaved)

```
Installation: /usr/local/bin/ollama (direct binary)
Binary type:  Mach-O 64-bit executable arm64
```

**psutil output:**
```
proc.name()    = "ollama"  # ← Works correctly!
proc.exe()     = "/usr/local/bin/ollama"
```

No detection issue — process name matches config.

## Current Code Analysis

### cli.py Detection Flow (lines 81-113)

```python
# Current: scan with ["pid", "name", "cmdline"]
for proc in psutil.process_iter(["pid", "name", "cmdline"]):
    # 1. Fast path: exact name match via self._process_map
    if proc_name_lower in self._process_map:
        tool_cfg = self._process_map[proc_name_lower]

    # 2. Fallback: cmdline pattern matching via self._cmdline_patterns
    if tool_cfg is None and self._cmdline_patterns:
        cmdline_str = " ".join(cmdline).lower()
        for pattern, candidate in self._cmdline_patterns.items():
            if pattern in cmdline_str:
                tool_cfg = candidate
```

### Current Config Problems

| Tool | Config `process_names.macos` | Actual `proc.name()` | Match? |
|------|------------------------------|----------------------|--------|
| claude-code | `["claude"]` | `"2.1.39"` | **NO** |
| gemini-cli | `["gemini"]` | `"node"` | **NO** |
| codex-cli | `["codex"]` | `"codex-aarch64-apple-darwin"` | **NO** |
| vibe | `["vibe"]` | `"python"` | **NO** |
| aider | `["aider"]` | `"python"` | **NO** |
| ollama | `["ollama"]` | `"ollama"` | YES |

**4 out of 6 CLI tools are currently undetectable by process name alone.**

### cmdline_patterns Fallback

The code already supports `cmdline_patterns` (line 53-57, 106-113). However:
- Only `gemini-cli`, `codex-cli`, and `vibe` have `cmdline_patterns` configured
- `claude-code` has NO `cmdline_patterns` → completely invisible when running!
- The cmdline search searches the FULL cmdline string (`" ".join(cmdline)`) → false positive risk from heredoc arguments

## False Positive Analysis

During testing, the naive `"claude" in cmdline_str` approach produced 3 false positives:

| PID | Process | Why it matched | Real identity |
|-----|---------|----------------|---------------|
| 48921 | chrome-native-host | Chrome extension ID contains "claude" | Claude Desktop app helper |
| 65674 | bash | Path `~/.config/claude/` in args | JetBrains MCP wrapper |
| 87143 | zsh | Heredoc script text contains "claude" | Current shell running psutil |

**Fix:** Limit cmdline search to `cmdline[0:3]` only (executable + first 2 args), not the full argument list.

## Performance Benchmark

Adding `exe` to `process_iter` has minimal overhead:

| Fields | 5x full scan (851 procs) | Per scan |
|--------|--------------------------|----------|
| pid, name | 72.3ms | 14.5ms |
| pid, name, cmdline | 101.6ms | 20.3ms |
| pid, name, exe, cmdline | 112.9ms | 22.6ms |

Adding `exe` costs ~2ms per scan — negligible on a 15-second cycle.

## Recommended Detection Strategy

### Three-tier detection (priority order):

```
Tier 1: proc.name() exact match         (fast, no false positives)
Tier 2: proc.exe() path substring match  (NEW — catches version-named binaries)
Tier 3: cmdline[0:3] substring match     (catches Node.js/Python wrappers)
```

### Implementation: New config field `exe_path_patterns`

```yaml
ai_cli_tools:
  - name: claude-code
    process_names:
      macos: ["claude"]
    exe_path_patterns:
      - "/claude/versions/"        # Catches version-named binaries
      - "/claude-code/"            # Future-proofing
    cmdline_patterns:
      - "claude"                   # Catches cmdline[0] = "claude"
    category: code
    cost_per_hour: 1.00

  - name: gemini-cli
    process_names:
      macos: ["gemini"]
    exe_path_patterns: []          # exe is just "node", useless
    cmdline_patterns:
      - "gemini-cli"               # Found in script path
      - "@google/gemini"           # npm module path
    category: code
    cost_per_hour: 0.80

  - name: codex-cli
    process_names:
      macos: ["codex"]
    exe_path_patterns:
      - "/codex"                   # Catches codex-aarch64-apple-darwin
    cmdline_patterns:
      - "codex"
    category: code
    cost_per_hour: 1.00

  - name: vibe
    process_names:
      macos: ["vibe"]
    exe_path_patterns:
      - "mistral-vibe"             # uv-managed python contains tool name
    cmdline_patterns:
      - "vibe"
      - "mistral-vibe"
    category: code
    cost_per_hour: 0.60

  - name: aider
    process_names:
      macos: ["aider"]
    exe_path_patterns:
      - "/aider/"                  # pipx/uv managed path
    cmdline_patterns:
      - "aider"
    category: code
    cost_per_hour: 0.80
```

### Implementation: cli.py changes

```python
# In __init__: add exe_path_patterns lookup
self._exe_patterns: list[tuple[str, dict]] = []
for tool in config.ai_cli_tools:
    for pattern in tool.get("exe_path_patterns", []):
        self._exe_patterns.append((pattern.lower(), tool))

# In scan(): add "exe" to process_iter fields
for proc in psutil.process_iter(["pid", "name", "exe", "cmdline"]):
    # ... existing pid dedup ...

    # Tier 1: exact process name match (existing)
    if proc_name_lower in self._process_map:
        tool_cfg = self._process_map[proc_name_lower]

    # Tier 2: exe path substring match (NEW)
    if tool_cfg is None and self._exe_patterns:
        exe_path = (proc.info.get("exe") or "").lower()
        if exe_path:
            for pattern, candidate in self._exe_patterns:
                if pattern in exe_path:
                    tool_cfg = candidate
                    break

    # Tier 3: cmdline[0:3] substring match (IMPROVED — was full cmdline)
    if tool_cfg is None and self._cmdline_patterns:
        cmdline = proc.info.get("cmdline") or []
        if cmdline:
            # Only search first 3 args to avoid false positives
            cmdline_str = " ".join(cmdline[:3]).lower()
            for pattern, candidate in self._cmdline_patterns.items():
                if pattern in cmdline_str:
                    tool_cfg = candidate
                    break
```

### Key improvements over current code:

1. **Add `exe` to `process_iter`** — only +2ms cost, enables Tier 2 detection
2. **New `exe_path_patterns` config field** — catches Claude Code (version-named binary), Codex (arch-qualified), Vibe (uv python path)
3. **Limit cmdline search to `cmdline[:3]`** — eliminates false positives from heredoc args
4. **Add `cmdline_patterns` for claude-code** — currently missing, tool is invisible

## Edge Cases & Caveats

### macOS-specific
- No `/proc/PID/exe` on macOS — `proc.exe()` uses `sysctl(KERN_PROCARGS)` internally
- Symlinks are NOT followed by `proc.exe()` — returns the actual binary path, not the symlink
- App Sandbox: some apps may have `AccessDenied` on `proc.exe()` — handle gracefully

### Version updates
- Claude Code updates create new version files (2.1.37, 2.1.38, 2.1.39...)
- Detection by `/claude/versions/` pattern is immune to version changes
- Codex via Homebrew: `codex-aarch64-apple-darwin` is stable across versions

### Multi-instance detection
- Claude agents spawn as separate processes with same binary → all detected correctly
- Each agent has unique PID, all share the same `exe()` path

### Windows differences
- On Windows, `proc.name()` returns the `.exe` filename → usually correct
- `proc.exe()` returns full path with `.exe` extension
- Node.js scripts on Windows use `.cmd` wrappers → `proc.name()` = `cmd.exe` or `node.exe`
- Need separate `cmdline_patterns` for Windows (e.g., `"gemini.cmd"`)

## Summary Table

| Tool | Type | proc.name() | Best Detection Method |
|------|------|-------------|----------------------|
| Claude Code | Mach-O (version-named) | `"2.1.39"` | exe path: `/claude/versions/` |
| Gemini CLI | Node.js script | `"node"` | cmdline: `gemini-cli` or `@google/gemini` |
| Codex CLI | Mach-O (arch-qualified) | `"codex-aarch64-..."` | exe path: `/codex` or name substring |
| Vibe | Python script (uv) | `"python"` | exe path: `mistral-vibe` or cmdline |
| Aider | Python script | `"python"` | cmdline: `aider` |
| Ollama | Native binary | `"ollama"` | name exact match (works today) |
| LLM | Python script | `"python"` | cmdline: `llm` |
| SGPT | Python script | `"python"` | cmdline: `sgpt` |
