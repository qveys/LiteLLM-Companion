# How Competing Tools Detect AI Applications

> Date: 2026-02-13
> Research scope: WakaTime, ActivityWatch, Timing.app, RescueTime

## 1. WakaTime

### Architecture: Plugin-Based Heartbeat System

WakaTime does **NOT** use process scanning. Instead, it relies on a **plugin ecosystem** where each editor/tool has a dedicated plugin that sends "heartbeats" to a central CLI (`wakatime-cli`).

**Detection flow:**
```
IDE Plugin → wakatime-cli (Go binary) → WakaTime API
```

Each plugin:
1. Hooks into the editor's event system (file open, file save, file change)
2. Detects the current file, project, branch, language
3. Sends heartbeats to `wakatime-cli` with `--plugin "editor-name/version plugin-name/version"`
4. Rate-limits to 1 heartbeat per 2 minutes per file (unless saved)

### AI Tool Detection

WakaTime has dedicated plugins for AI CLI tools:

| Tool | Plugin | Detection Method |
|------|--------|-----------------|
| Claude Code | `claude-code-wakatime` | Claude Code hooks system (`.claude/hooks/`) |
| Codex CLI | `codex-wakatime` | Codex notification hooks (`notify = ["codex-wakatime"]` in `~/.codex/config.toml`) |
| OpenCode | `opencode-wakatime` | OpenCode event hooks (tool exec, chat, session events) |
| VS Code | `vscode-wakatime` | VS Code extension API (file events + AI line detection) |

**Key insight:** WakaTime's AI detection is **event-driven**, not process-based. Each AI tool calls the wakatime hook after completing a turn/action.

For the **desktop app** (fallback for unsupported tools), WakaTime uses the OS active window API — similar to our approach but focused on time tracking, not process enumeration.

### AI-Specific Features

- `--ai-line-changes` flag: tracks lines written by AI vs manually
- `category: "ai coding"` heartbeat field: auto-inferred from tool type
- File path + project context included in every heartbeat

### Lessons for Us

- **Event-driven detection is more reliable** than process scanning for CLI tools
- WakaTime doesn't try to detect Claude Code via `psutil` — it hooks into Claude Code's own extension system
- The heartbeat model (report activity, not poll for it) avoids all wrapper/name issues
- However, WakaTime requires explicit plugin installation per tool — our approach (auto-scan) is more user-friendly

---

## 2. ActivityWatch

### Architecture: Watcher + Event System

ActivityWatch uses a modular **watcher** architecture:

```
aw-watcher-window (active window tracking)
aw-watcher-afk    (keyboard/mouse idle detection)
  ↓
aw-server (local REST API + SQLite)
  ↓
aw-webui (dashboard)
```

### macOS Window Detection

The `aw-watcher-window` uses **NSWorkspace + Accessibility API** (implemented in Swift):

```swift
// Get frontmost application
guard let frontmost = NSWorkspace.shared.frontmostApplication else { return }

// Extract data:
// 1. Bundle Identifier (e.g., "com.apple.Safari")
guard let bundleIdentifier = frontmost.bundleIdentifier else { return }

// 2. Localized Name (e.g., "Safari")
let appName = frontmost.localizedName!

// 3. Process ID (for AX API window title)
let pid = frontmost.processIdentifier
let focusedApp = AXUIElementCreateApplication(pid)
// Then use AXObserver to track window title changes
```

**Detection data collected:**
- `app`: Application localized name (from `NSRunningApplication.localizedName`)
- `title`: Window title (from Accessibility framework `AXUIElement`)
- Bundle identifier (for browser detection: Chrome, Firefox, Safari variants)

### Platform Strategy Pattern

ActivityWatch uses a **strategy pattern** for platform abstraction:
- `macos-swift`: Compiled Swift binary using NSWorkspace + AXUIElement
- `linux-x11`: Uses `xprop` and X11 APIs
- `linux-wayland`: Uses wlr-foreign-toplevel-management
- `windows`: Uses Win32 API

### Lessons for Us

- **Bundle Identifier** (`NSRunningApplication.bundleIdentifier`) is the most reliable app identifier on macOS — not process name, not exe path
- `NSWorkspace.shared.frontmostApplication` gives the focused app directly — no need to scan all processes
- **AXUIElement** gives window title, which can contain project/file context
- ActivityWatch's Swift strategy is faster and more accurate than Python+psutil for macOS desktop apps
- **They don't detect CLI tools at all** — only GUI apps with windows

---

## 3. Timing.app (Commercial, macOS-only)

### Architecture: Multi-Layer Detection

Timing.app uses a layered approach (most detailed commercial tracker for Mac):

1. **NSWorkspace** — active app detection (app name, bundle ID)
2. **Accessibility API** — window title, document name
3. **Screen Recording permission** — fallback for apps that don't expose window titles via Accessibility
4. **AppleScript** — deep integration with Safari, Chrome, Finder, Mail (extracts URL, subject, path)
5. **Rule-based engine** — auto-categorizes activities into projects based on patterns

### Key Detection Features

- **CGWindow API** fallback: For apps like Adobe Premiere Pro that don't share window titles via AX API
- **Per-app AppleScript**: Asks Safari for the current URL, Finder for the current folder, etc.
- **Rule system**: Opaque matching rules that auto-assign activities to projects (regex on app name + window title)

### Lessons for Us

- **Layered fallback approach** is key: NSWorkspace → AX API → CGWindow → AppleScript
- Bundle ID is the primary app identifier (stable across versions, updates)
- Screen Recording permission enables window title access for resistant apps
- Rule-based categorization is powerful for user customization

---

## 4. RescueTime (Commercial, Cross-Platform)

### Architecture: System Tray Agent

RescueTime runs as a background agent (system tray app) that:
1. Polls the active window at regular intervals
2. Sends activity data to RescueTime cloud API
3. Categorizes apps into productivity scores

### Detection Method

- Uses OS-native APIs for active window detection (similar to ActivityWatch)
- Classifies apps by name and window title
- Requires Accessibility + Screen Recording permissions on macOS
- No process scanning — only tracks the **active/focused** app

### Lessons for Us

- Active-window-only tracking is sufficient for most productivity use cases
- But our use case (tracking ALL running AI tools, not just focused ones) requires process scanning
- RescueTime's approach wouldn't detect background CLI tools

---

## Comparison Matrix

| Feature | Our Approach | WakaTime | ActivityWatch | Timing.app |
|---------|-------------|----------|---------------|------------|
| **Detection method** | psutil process scan | Plugin hooks | NSWorkspace + AX API | NSWorkspace + AX + CGWindow + AppleScript |
| **App identifier** | Process name | Plugin self-report | Bundle ID | Bundle ID |
| **CLI tool detection** | Process name/cmdline | Dedicated hooks per tool | Not supported | Not supported |
| **Background apps** | Yes (scan all procs) | Yes (plugin sends heartbeats) | No (active window only) | No (active window only) |
| **Window title** | Not used | File path from editor | AX API | AX API + AppleScript |
| **Cross-platform** | Yes (psutil) | Yes (plugins per platform) | Yes (strategy pattern) | macOS only |
| **Install friction** | Zero (auto-scan) | Plugin per tool | App install | App install |

## Key Recommendations

### 1. Add Bundle ID Detection for macOS Desktop Apps
ActivityWatch and Timing.app both use `NSRunningApplication.bundleIdentifier` as the primary identifier. This is:
- **Stable across versions** (unlike process name which can change)
- **Unique per app** (unlike "node" or "python")
- **Available via pyobjc**: `NSWorkspace.shared.runningApplications` → `bundleIdentifier`

### 2. Keep Process Scanning for CLI Tools (Our Unique Advantage)
No competing tool does process-level CLI detection. WakaTime uses hooks (requires plugin per tool), ActivityWatch/Timing don't detect CLIs at all. Our psutil-based approach is the only way to auto-detect ALL running AI CLI tools without requiring per-tool plugin installation.

### 3. Add Layered Fallback for Detection Robustness
Following Timing.app's approach:
```text
Tier 0: Bundle ID match (macOS desktop apps — most reliable) [future enhancement]
Tier 1: Process name exact match (fast, existing) [implemented]
Tier 2: Exe path substring match (catches version-named binaries) [implemented]
Tier 3: Cmdline[0:3] substring match (catches Node/Python wrappers) [implemented]
```
> **Note:** Tier 0 (Bundle ID) is not yet implemented. Current codebase uses Tiers 1–3.

### 4. Consider Hook-Based Detection as a Complement
For tools that support it (Claude Code, Codex), hook-based detection could provide richer data (files modified, prompts used) alongside our process scanning. This is a future enhancement beyond the current scope.

## Sources

- [ActivityWatch aw-watcher-window](https://github.com/ActivityWatch/aw-watcher-window)
- [WakaTime claude-code-wakatime](https://github.com/wakatime/claude-code-wakatime)
- [WakaTime codex-wakatime](https://github.com/angristan/codex-wakatime)
- [WakaTime opencode-wakatime](https://github.com/angristan/opencode-wakatime)
- [WakaTime Plugin Creation Guide](https://wakatime.com/help/creating-plugin)
- [Timing.app FAQ](https://timingapp.com/help/faq)
- [Timing.app AppleScript Reference](https://timingapp.com/help/applescript)
