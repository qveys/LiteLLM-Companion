# Process Inventory — Truth Table

> Machine: macOS Darwin 25.2.0 (arm64)
> Date: 2026-02-13
> Method: psutil scan + filesystem inspection + bundle ID lookup

---

## 1. Desktop Apps — Config vs Reality

### Apps INSTALLED on this machine

| App | Config `process_names.macos` | Real psutil `name` | Real `exe` path | Bundle ID | Running? | Detected by agent? |
|-----|------|------|------|------|------|------|
| **ChatGPT** | `["ChatGPT"]` | `ChatGPTHelper` | `/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper` | `com.openai.chat` | YES | **NO** — name mismatch |
| **Claude Desktop** | `["Claude"]` | `chrome-native-host` (only helper visible) | `/Applications/Claude.app/Contents/Helpers/chrome-native-host` | `com.anthropic.claudefordesktop` | Partial | **NO** — main process invisible to psutil in background |
| **Ollama (GUI)** | `["Ollama"]` | `Ollama` | `/Applications/Ollama.app/Contents/MacOS/Ollama` | `com.electron.ollama` | YES | **YES** |
| **Ollama (serve)** | (cli: `["ollama"]`) | `ollama` | `/Applications/Ollama.app/Contents/Resources/ollama` | — | YES | **YES** |
| **Cursor** | `["Cursor Helper (Renderer)", "Cursor"]` | — (not running) | `/Applications/Cursor.app/Contents/MacOS/Cursor` | `com.todesktop.230313mzl4w4u92` | NO | Cannot verify |
| **JetBrains IDEA** | `["idea", ...]` | `idea` | `/Users/qveys/Applications/IntelliJ IDEA.app/Contents/MacOS/idea` | — | YES | **YES** |
| **Copilot (JetBrains)** | (via JetBrains AI heuristic) | `copilot-language-server` | `...JetBrains/.../copilot-agent/native/darwin-arm64/copilot-language-server` | — | YES | Indirect only |
| **Comet (Perplexity)** | **NOT IN CONFIG** | `Comet` + `Comet Helper` + `Comet Helper (Renderer)` x18 | `/Applications/Comet.app/Contents/MacOS/Comet` | `ai.perplexity.comet` | YES | **NO** — missing |
| **Codex Desktop** | **NOT IN CONFIG** | `Codex` (expected) | `/Applications/Codex.app/Contents/MacOS/Codex` | `com.openai.codex` | NO | **NO** — missing |
| **Auto-Claude** | **NOT IN CONFIG** | `Auto-Claude` (expected) | `/Applications/Auto-Claude.app/Contents/MacOS/Auto-Claude` | `com.autoclaude.ui` | NO | **NO** — missing |
| **Zed** | **NOT IN CONFIG** | `zed` (expected) | `/Applications/Zed.app/Contents/MacOS/zed` | `dev.zed.Zed` | NO | **NO** — missing |
| **superwhisper** | **NOT IN CONFIG** | `superwhisper` | `/Applications/superwhisper.app/Contents/MacOS/superwhisper` | `com.superduper.superwhisper` | YES | **NO** — missing |

### Apps in config but NOT INSTALLED

| App | Config `process_names.macos` | Installed? |
|-----|------|------|
| Perplexity (standalone) | `["Perplexity"]` | NO (Comet is the desktop client) |
| Windsurf | `["Windsurf", "Windsurf Helper (Renderer)"]` | NO |
| GitHub Copilot (VS Code) | `["Code Helper (Renderer)"]` | NO (VS Code not installed) |
| Midjourney | `["Midjourney"]` | NO |
| LM Studio | `["LM Studio"]` | NO |
| Jan | `["Jan"]` | NO |
| Msty | `["Msty"]` | NO |
| Pieces | `["Pieces OS", "Pieces for Developers"]` | NO |

---

## 2. CLI Tools — Config vs Reality

| Tool | Config `process_names.macos` | Real binary path | Real psutil `name` | Binary type | Found? | Detected? |
|------|------|------|------|------|------|------|
| **Claude Code** | `["claude"]` | `/Users/qveys/.local/bin/claude` → `~/.local/share/claude/versions/2.1.39` | **`2.1.39`** | Mach-O arm64 native | YES | **NO** — process name is version number! |
| **gemini** | `["gemini"]` | NOT in PATH | — | — | NO | N/A |
| **codex (CLI)** | `["codex"]` | NOT in PATH | — | — | NO | N/A |
| **vibe** | `["vibe"]` | NOT in PATH | — | — | NO | N/A |
| **gh** | `["gh"]` | NOT in PATH | — | — | NO | N/A |
| **aider** | `["aider"]` | NOT in PATH | — | — | NO | N/A |
| **ollama (CLI)** | `["ollama"]` | `/Applications/Ollama.app/Contents/Resources/ollama` | `ollama` | Embedded in GUI | YES | **YES** |
| openai, llm, sgpt | respective names | NOT in PATH | — | — | NO | N/A |

---

## 3. Critical Findings

### BUG 1: Claude Code CLI — Process name is version number

```
Symlink chain:
  /usr/local/bin/claude → /Users/qveys/.local/bin/claude → ~/.local/share/claude/versions/2.1.39

psutil sees:
  PID=65627 | NAME=2.1.39 | EXE=/Users/qveys/.local/share/claude/versions/2.1.39
  CMDLINE: claude --resume 49958b5c... --dangerously-skip-permissions

Also for sub-agents:
  PID=81509 | NAME=2.1.39 | CMDLINE: ...versions/2.1.39 --agent-id explorer-macos@...
```

**Impact**: The config expects process name `"claude"`, but psutil reports `"2.1.39"`. The process name changes with every Claude Code update. Detection will NEVER match by `proc.name()`.

**Fix options**:
1. Match on `cmdline[0]` containing "claude" or on `exe` path containing `/claude/versions/`
2. Match on symlink resolution (expensive)
3. Use `cmdline_patterns` already defined in config

### BUG 2: ChatGPT — Only helper process visible

```
psutil sees:
  PID=801 | NAME=ChatGPTHelper | EXE=/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper

Main executable exists at:
  /Applications/ChatGPT.app/Contents/MacOS/ChatGPT
  ...but does NOT appear in psutil when app is in background
```

**Impact**: Config expects `"ChatGPT"` but the only visible process is `"ChatGPTHelper"`. The main ChatGPT process may only be visible when the app is in the foreground. Background detection fails.

**Fix**: Add `"ChatGPTHelper"` to `process_names.macos` list.

### BUG 3: Claude Desktop — Main process invisible

```
psutil sees:
  PID=48921 | NAME=chrome-native-host | EXE=/Applications/Claude.app/Contents/Helpers/chrome-native-host

Main executable exists at:
  /Applications/Claude.app/Contents/MacOS/Claude
  ...but does NOT appear in psutil process list
```

**Impact**: Config expects `"Claude"` but the main process may not be visible to psutil. Only a helper (`chrome-native-host`) from the Claude.app bundle is visible.

**Fix**: Add `"chrome-native-host"` to `process_names.macos` AND use exe path matching against `Claude.app` to avoid false positives from other chrome-native-host instances.

### BUG 4: Comet (Perplexity Desktop) — Missing from config entirely

```
psutil sees:
  PID=48885 | NAME=Comet | EXE=/Applications/Comet.app/Contents/MacOS/Comet
  + 3x Comet Helper + 18x Comet Helper (Renderer)

Bundle ID: ai.perplexity.comet
```

**Impact**: Perplexity's actual desktop app is called "Comet", not "Perplexity". Config has `Perplexity` which doesn't exist on this machine. Zero detection.

**Fix**: Add `"Comet"` to the Perplexity entry's `process_names.macos`, or create a separate `Comet` entry.

### Missing Apps — Not in config

| App | Process Name | Category | Notes |
|-----|-------------|----------|-------|
| Codex Desktop | `Codex` | code | OpenAI's Codex desktop app (com.openai.codex) |
| Auto-Claude | `Auto-Claude` | chat | Automation wrapper (com.autoclaude.ui) |
| Zed | `zed` | code | Editor with AI assistant built-in |
| superwhisper | `superwhisper` | audio/ai | AI voice transcription, running |

---

## 4. Process Detail: Running AI Processes at Scan Time

### Ollama (WORKING)
```
PID=  847 | NAME=Ollama          | EXE=/Applications/Ollama.app/Contents/MacOS/Ollama      # GUI (Electron)
PID=  803 | NAME=Squirrel        | EXE=.../Squirrel.framework/.../Squirrel                  # Auto-updater
PID= 1129 | NAME=ollama          | EXE=/Applications/Ollama.app/Contents/Resources/ollama   # CLI server
           CMDLINE: ollama serve
```

### Comet / Perplexity (NOT DETECTED)
```
PID=48885 | NAME=Comet                | EXE=/Applications/Comet.app/Contents/MacOS/Comet
PID=48891 | NAME=Comet Helper         | 3 instances (GPU, network, utility)
PID=48897 | NAME=Comet Helper (Renderer) | 18 instances (tab renderers)
```

### Claude Code CLI (NOT DETECTED)
```
PID=65627 | NAME=2.1.39 | EXE=~/.local/share/claude/versions/2.1.39
           CMDLINE: claude --resume 49958b5c... --dangerously-skip-permissions

PID=81509 | NAME=2.1.39 | (sub-agent: explorer-macos)
PID=82219 | NAME=2.1.39 | (sub-agent: explorer-research)
PID=83523 | NAME=2.1.39 | (sub-agent: explorer-inventory)
PID=84375 | NAME=2.1.39 | (sub-agent: explorer-cli)
```

### JetBrains IntelliJ (WORKING)
```
PID=77843 | NAME=idea | EXE=/Users/qveys/Applications/IntelliJ IDEA.app/Contents/MacOS/idea
```

### Copilot Language Server (INDIRECT)
```
PID=78708 | NAME=copilot-language-server | EXE=.../github-copilot-intellij/copilot-agent/native/darwin-arm64/copilot-language-server
```

### ChatGPT (NOT DETECTED)
```
PID=  801 | NAME=ChatGPTHelper | EXE=/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper
```

### superwhisper (NOT DETECTED)
```
PID=80204 | NAME=superwhisper | EXE=/Applications/superwhisper.app/Contents/MacOS/superwhisper
```

---

## 5. Summary Scorecard

| Category | Total in Config | Installed | Running | Correctly Detected |
|----------|:-:|:-:|:-:|:-:|
| Desktop Apps | 13 | 5 | 4 | **2** (Ollama, JetBrains) |
| CLI Tools | 10 | 2 | 2 | **1** (ollama serve) |
| **Missing from config** | — | 4 | 2 | **0** |

**Detection rate for running apps: 3/8 (37.5%)**

### Priority fixes needed:
1. **CRITICAL**: Claude Code CLI — process name is version number, not `"claude"`
2. **HIGH**: ChatGPT — add `"ChatGPTHelper"` to process names
3. **HIGH**: Comet/Perplexity — add `"Comet"` to config
4. **HIGH**: Claude Desktop — add helper detection or use exe path matching
5. **MEDIUM**: Add Codex Desktop, Zed, Auto-Claude, superwhisper to config
