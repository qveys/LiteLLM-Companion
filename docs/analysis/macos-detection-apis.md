# macOS Native Detection APIs — Comparison Report

> Generated: 2026-02-13 | Machine: macOS Darwin 25.2.0 (ARM64)

## Executive Summary

Our agent currently uses `psutil.process_iter()` to detect AI apps, which gives **process names** like `ChatGPTHelper`, `Comet Helper (Renderer)`, `2.1.39`, `chrome-native-host` — NOT the user-facing app names. macOS provides several native APIs that give the **real app name** and **bundle identifier**, enabling reliable detection.

**Key finding:** A **hybrid 3-layer strategy** is required because no single API covers all cases:

| Layer | API | Covers | Misses |
|-------|-----|--------|--------|
| 1 | `NSRunningApplication` (bundleID lookup) | Comet, Ollama, Cursor (when running) | ChatGPT (no bundleID!), Claude Desktop (helper-only), CLI tools |
| 2 | psutil `proc.exe()` → `.app` Info.plist | ChatGPT, Claude Desktop helpers, all Electron helpers | CLI tools without `.app` parent |
| 3 | psutil cmdline/exe path pattern match | Claude CLI, copilot-language-server, aider, etc. | Nothing (catch-all) |

---

## 1. APIs Tested

### 1.1 NSRunningApplication (via pyobjc)

```python
from AppKit import NSWorkspace, NSRunningApplication

# List all running apps
ws = NSWorkspace.sharedWorkspace()
apps = ws.runningApplications()

# Direct lookup by bundle ID (most efficient)
apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_("ai.perplexity.comet")
```

**Fields available:**
- `localizedName()` — user-facing app name (e.g., "Comet", "Ollama")
- `bundleIdentifier()` — reverse-DNS ID (e.g., `ai.perplexity.comet`)
- `executableURL()` — full path to the executable binary
- `processIdentifier()` — PID
- `activationPolicy()` — 0=Regular (GUI), 1=Accessory (menu bar), 2=Prohibited (background)
- `isHidden()`, `isActive()`, `icon()` — UI state and app icon

**Pros:**
- Gives the **real app name** and **bundle ID**
- `runningApplicationsWithBundleIdentifier_()` is O(1) lookup
- Includes activation policy (GUI vs menu bar vs background)
- Icon available for UI

**Cons:**
- **ChatGPT appears as "ChatGPTHelper" with NO bundleIdentifier** (None)
- Claude Desktop doesn't appear at all when not in foreground (only helper processes)
- CLI tools (claude CLI, aider, copilot-language-server) are NOT macOS apps → invisible
- Requires `pyobjc-framework-Cocoa` dependency

### 1.2 lsappinfo (CLI tool)

```bash
lsappinfo list                    # All registered apps
lsappinfo info -app "Comet"       # Specific app lookup
```

**Fields available:** bundleID, bundle path, executable path, pid, type (Foreground/UIElement/BackgroundOnly), flavor, Version, Arch, coalition, launch/checkin times.

**Pros:**
- Very detailed — includes app type, version, architecture
- Shows coalition (process group) information
- Available without Python dependencies

**Cons:**
- Same limitations as NSRunningApplication (ChatGPT shows as "ChatGPTHelper" with NULL bundleID)
- CLI tool — slower to parse than native API
- Output format is custom (not JSON), harder to parse

### 1.3 psutil.process_iter()

```python
import psutil
for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline', 'ppid']):
    info = p.info
```

**Fields available:** pid, name, exe (full path), cmdline (full command line), ppid, status, etc.

**Pros:**
- Sees ALL processes including CLI tools and background daemons
- `exe` gives the full path → can resolve to `.app` bundle
- `cmdline` reveals the actual command (e.g., `claude --resume ...`)
- Cross-platform (works on Windows too)

**Cons:**
- `name` is the **binary name**, not the app name:
  - ChatGPT → `ChatGPTHelper`
  - Perplexity → `Comet Helper (Renderer)` (14+ child processes!)
  - Claude CLI → `2.1.39` (the version number!)
  - Claude Desktop → `chrome-native-host`
  - Ollama server → `ollama` (lowercase, different from Electron wrapper `Ollama`)

### 1.4 mdfind (Spotlight)

```bash
mdfind "kMDItemCFBundleIdentifier == 'ai.perplexity.comet'"
mdfind "kMDItemFSName == 'Claude.app'"
```

**Pros:**
- Finds **installed** apps (not just running), useful for building the detection registry
- Works with bundle IDs and file names

**Cons:**
- Only finds installed apps, doesn't tell if they're running
- Some bundle IDs not indexed (com.anthropic.claude NOT FOUND, but com.anthropic.claudefordesktop works via file name search)
- Depends on Spotlight indexing being enabled

### 1.5 launchctl

```bash
launchctl list | grep -i ollama
# 803  0  com.ollama.ollama
```

**Pros:**
- Shows registered launchd services (auto-start apps)
- Includes PID if running

**Cons:**
- Only shows launchd-managed services, not all apps
- Limited AI tool coverage

### 1.6 sfltool (Login Items / BTM)

```bash
sfltool dumpbtm
```

Shows login items including ChatGPT, Comet, Ollama with their bundle IDs and paths. Useful for discovering which AI apps are configured to auto-start.

---

## 2. Per-App Detection Analysis

### 2.1 ChatGPT (com.openai.chat)

| API | Result |
|-----|--------|
| NSRunningApplication (bundle lookup) | **FAILS** — bundleIdentifier is None |
| NSRunningApplication (all apps) | Shows as "ChatGPTHelper" with no bundle |
| psutil name | `ChatGPTHelper` |
| psutil exe | `/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper` |
| exe → .app resolution | `/Applications/ChatGPT.app` → Info.plist → `com.openai.chat` |
| mdfind | Found via filename `ChatGPT.app`, NOT via bundle ID |

**ChatGPT is a special case:** The main app process registers as "ChatGPTHelper" with NO bundle identifier. The only reliable way to detect it is by resolving `proc.exe()` back to the `.app` bundle and reading its `Info.plist`.

### 2.2 Claude Desktop (com.anthropic.claudefordesktop)

| API | Result |
|-----|--------|
| NSRunningApplication (bundle lookup) | **NOT RUNNING** as GUI app |
| psutil (helper) | PID=48921 `chrome-native-host` exe=`/Applications/Claude.app/Contents/Helpers/chrome-native-host` |
| exe → .app resolution | `/Applications/Claude.app` → Info.plist → `com.anthropic.claudefordesktop` |
| mdfind | Found via filename `Claude.app` |

**Claude Desktop** runs primarily as a background helper (`chrome-native-host`) when not in the foreground. The bundle lookup fails. Detection requires psutil exe → .app resolution.

### 2.3 Claude CLI

| API | Result |
|-----|--------|
| NSRunningApplication | **INVISIBLE** (not a macOS app) |
| psutil name | `2.1.39` (the VERSION NUMBER!) |
| psutil exe | `/Users/qveys/.local/share/claude/versions/2.1.39` |
| psutil cmdline | `claude --resume ...` or `/Users/qveys/.local/share/claude/versions/2.1.39 --agent-id ...` |

**Claude CLI** is the worst case for detection:
- Process name = version number (`2.1.39`)
- No `.app` bundle
- Detection strategy: match `cmdline[0]` containing `claude` OR exe path containing `/claude/versions/`

### 2.4 Perplexity / Comet (ai.perplexity.comet)

| API | Result |
|-----|--------|
| NSRunningApplication (bundle lookup) | **WORKS** — PID, name="Comet" |
| psutil (main) | PID=48885 `Comet` exe=`/Applications/Comet.app/Contents/MacOS/Comet` |
| psutil (children) | 20+ processes: `Comet Helper`, `Comet Helper (Renderer)`, `chrome_crashpad_handler` |

**Perplexity (Comet)** works perfectly with NSRunningApplication bundle lookup. The issue is that psutil sees 20+ child processes that should be attributed to the parent app, not counted separately.

### 2.5 Ollama (com.electron.ollama)

| API | Result |
|-----|--------|
| NSRunningApplication (bundle lookup) | **WORKS** — PID, name="Ollama" |
| psutil (Electron wrapper) | `Ollama` exe=`/Applications/Ollama.app/Contents/MacOS/Ollama` |
| psutil (Squirrel updater) | `Squirrel` exe=`/Applications/Ollama.app/Contents/Frameworks/Squirrel.framework/...` |
| psutil (server) | `ollama` exe=`/Applications/Ollama.app/Contents/Resources/ollama` (cmdline: `ollama serve`) |
| launchctl | `com.ollama.ollama` registered as launchd service |

**Ollama** has 3 distinct processes: Electron wrapper (detected by bundle), Squirrel updater, and the actual `ollama serve` backend. All can be resolved to the same `.app` bundle.

### 2.6 Cursor (com.todesktop.230313mzl4w4u92)

| API | Result |
|-----|--------|
| NSRunningApplication | Not running during test |
| mdfind (bundle) | Found at `/Applications/Cursor.app` |
| Info.plist | BundleID=`com.todesktop.230313mzl4w4u92`, Name=`Cursor` |

**Cursor** has a non-obvious bundle ID (`com.todesktop.*`). Detection by bundle ID requires knowing this mapping. The exe → .app resolution strategy would work regardless.

### 2.7 GitHub Copilot (IDE plugin)

| API | Result |
|-----|--------|
| NSRunningApplication | **INVISIBLE** (runs as IDE subprocess) |
| psutil name | `copilot-language-server` |
| psutil exe | `/Users/.../JetBrains/.../github-copilot-intellij/copilot-agent/native/darwin-arm64/copilot-language-server` |

**Copilot** runs as a language server subprocess of the IDE. Detection requires pattern matching on process name or exe path.

---

## 3. False Positive: CursorUIViewService

`CursorUIViewService` (PID=1257) contains "cursor" in its name but is actually a **macOS system service** (`com.apple.TextInputUI.xpc.CursorUIViewService`) for text input cursor rendering. Its exe path is `/System/Library/PrivateFrameworks/TextInputUIMacHelper.framework/...`.

**Mitigation:** Always check exe path — if it starts with `/System/Library/`, it's a system process, not an AI tool.

---

## 4. Recommended Hybrid Detection Strategy

### Layer 1: NSRunningApplication Bundle ID Lookup (fastest, most reliable for GUI apps)

```python
from AppKit import NSRunningApplication

KNOWN_BUNDLES = {
    'ai.perplexity.comet': 'Perplexity',
    'com.electron.ollama': 'Ollama',
    'com.todesktop.230313mzl4w4u92': 'Cursor',
    'com.anthropic.claudefordesktop': 'Claude',
    'com.openai.chat': 'ChatGPT',
    # ... more apps
}

for bundle_id, app_name in KNOWN_BUNDLES.items():
    apps = NSRunningApplication.runningApplicationsWithBundleIdentifier_(bundle_id)
    if apps:
        # App is running — get PID from apps[0].processIdentifier()
```

**Coverage:** Comet, Ollama, Cursor (when running as main process). **Misses:** ChatGPT (no bundleID on process), Claude Desktop (background helper only).

### Layer 2: psutil exe → .app Bundle Resolution (catches helpers/children)

```python
import psutil, plistlib, os

def resolve_exe_to_app(exe_path):
    parts = exe_path.split('/')
    for i, part in enumerate(parts):
        if part.endswith('.app'):
            app_path = '/'.join(parts[:i+1])
            plist_path = os.path.join(app_path, 'Contents', 'Info.plist')
            if os.path.exists(plist_path):
                with open(plist_path, 'rb') as f:
                    plist = plistlib.load(f)
                return plist.get('CFBundleIdentifier'), plist.get('CFBundleName')
    return None, None

for p in psutil.process_iter(['pid', 'exe']):
    bundle_id, name = resolve_exe_to_app(p.info.get('exe', ''))
    if bundle_id in KNOWN_BUNDLES:
        # Detected! Attribute to parent app.
```

**Coverage:** ChatGPT (via ChatGPTHelper exe), Claude Desktop (via chrome-native-host exe), all Electron helpers, Ollama server.

**Performance note:** Reading Info.plist for every process is expensive. Cache results by app_path (the `.app` bundle path doesn't change).

### Layer 3: CLI Pattern Matching (for tools without .app bundles)

```python
CLI_PATTERNS = {
    'claude': {
        'exe_contains': ['/claude/versions/', '/.local/share/claude/'],
        'cmdline_starts': ['claude'],
        'label': 'Claude CLI',
    },
    'copilot': {
        'name_contains': ['copilot-language-server'],
        'label': 'GitHub Copilot',
    },
    'aider': {
        'cmdline_starts': ['aider'],
        'label': 'Aider',
    },
}

for p in psutil.process_iter(['pid', 'name', 'exe', 'cmdline']):
    # Match against CLI_PATTERNS
    # Exclude system processes (exe starts with /System/Library/)
```

**Coverage:** Claude CLI, copilot-language-server, aider, and any future CLI tools.

### Deduplication Strategy

Electron apps spawn many child processes (Comet has 20+). To avoid counting helpers:
1. **Use PPID:** If `proc.ppid()` leads to a process already detected as the main app, skip.
2. **Use .app bundle dedup:** If multiple PIDs resolve to the same `.app` path, keep only the one with the lowest PID (usually the main process).
3. **For CLI tools:** Use `cmdline[0]` dedup — multiple `claude` instances should each be counted.

---

## 5. Bundle ID Registry (Installed Apps on This Machine)

| App | Bundle ID | Detection Layer | Notes |
|-----|-----------|----------------|-------|
| ChatGPT | `com.openai.chat` | Layer 2 (exe→.app) | Main process has NO bundleID in NSRunningApplication |
| Claude Desktop | `com.anthropic.claudefordesktop` | Layer 2 (exe→.app) | Runs as `chrome-native-host` helper |
| Claude CLI | N/A | Layer 3 (cmdline) | Process name = version number (e.g., `2.1.39`) |
| Perplexity (Comet) | `ai.perplexity.comet` | Layer 1 (NSRunningApplication) | Chromium-based, 20+ child processes |
| Ollama | `com.electron.ollama` | Layer 1 (NSRunningApplication) | Electron wrapper + `ollama serve` backend |
| Cursor | `com.todesktop.230313mzl4w4u92` | Layer 1 (NSRunningApplication) | Non-obvious bundle ID |
| GitHub Copilot | N/A (IDE plugin) | Layer 3 (process name) | `copilot-language-server` binary |

---

## 6. Performance Considerations

| Operation | Cost | When to Use |
|-----------|------|-------------|
| `NSRunningApplication.runningApplicationsWithBundleIdentifier_()` | ~1ms per lookup | Every scan cycle (15s) |
| `NSWorkspace.runningApplications()` | ~5ms for all apps | Once per scan cycle if needed |
| `psutil.process_iter()` | ~50-100ms for all processes | Every scan cycle (already used) |
| `plistlib.load()` on Info.plist | ~1ms per file | Cache results — only read once per `.app` path |
| `mdfind` | ~100-500ms | One-time at startup to discover installed apps |

**Recommendation:** The psutil scan is already happening. Adding Layer 2 (exe → .app) is nearly free if Info.plist results are cached. Layer 1 (NSRunningApplication) is optional but provides instant, authoritative detection for apps with valid bundle IDs.

---

## 7. Raw Data Highlights

### ChatGPT — The Problematic Case
```
NSRunningApplication:
  PID=801  name="ChatGPTHelper"  bundleID=None  policy=Accessory
  exe=/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper

psutil:
  PID=801  name="ChatGPTHelper"  PPID=1
  exe=/Applications/ChatGPT.app/Contents/Resources/ChatGPTHelper

Info.plist (/Applications/ChatGPT.app):
  CFBundleIdentifier = com.openai.chat
  CFBundleName = ChatGPT
  CFBundleDisplayName = ChatGPT
  CFBundleExecutable = ChatGPT  (but the actual running binary is ChatGPTHelper!)
```

### Claude CLI — Version Number as Process Name
```
psutil:
  PID=65627  name="2.1.39"  PPID=65082
  exe=/Users/qveys/.local/share/claude/versions/2.1.39
  cmdline: claude --resume 49958b5c-280c-49c4-8a49-62bd54be5a6c
```

### Comet (Perplexity) — 20+ Child Processes
```
NSRunningApplication:
  PID=48885  name="Comet"  bundle="ai.perplexity.comet"  policy=Regular

psutil children (all PPID=48885):
  Comet Helper (GPU)
  Comet Helper (Network)
  Comet Helper (Storage)
  Comet Helper (Renderer) x14+
  chrome_crashpad_handler
```

---

## 8. Conclusions

1. **psutil alone is insufficient** — process names are unreliable for user-facing identification
2. **NSRunningApplication alone is insufficient** — ChatGPT has no bundleID, Claude Desktop often invisible
3. **The exe → .app → Info.plist strategy is the most reliable universal approach** — works for ALL macOS apps regardless of how they register with the system
4. **CLI tools require cmdline-based detection** — no macOS API helps here
5. **CursorUIViewService is a false positive trap** — always check exe path prefix to exclude system processes
6. **Deduplication is critical** — Electron apps spawn dozens of helper processes that should not be counted separately
