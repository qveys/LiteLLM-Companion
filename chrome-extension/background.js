/**
 * AI Cost Observer — Chrome Extension Background Service Worker
 *
 * Tracks time on AI domains, sends delta metrics to the local agent every 60s.
 * Loads domain list and API patterns from the agent's config endpoint,
 * falling back to cached config then hardcoded defaults.
 */

const DEFAULT_AGENT_BASE_URL = "http://127.0.0.1:8080";
const EXPORT_INTERVAL_SECONDS = 60;
const CONFIG_REFRESH_MINUTES = 5;
const ALARM_NAME = "export-metrics";
const CONFIG_ALARM_NAME = "refresh-config";
const STORAGE_PENDING_DELTAS_KEY = "pendingDeltas";
const STORAGE_PENDING_TOKEN_EVENTS_KEY = "pendingTokenEvents";
const STORAGE_EXTENSION_CONFIG_KEY = "extensionConfig";

// --- Hardcoded fallback defaults (used when agent is offline and no cache) ---

const DEFAULT_AI_API_PATTERNS = [
  { url_prefix: "https://api.anthropic.com/v1/messages", tool: "claude-web" },
  { url_prefix: "https://api.openai.com/v1/chat/completions", tool: "chatgpt-web" },
  { url_prefix: "https://generativelanguage.googleapis.com", tool: "gemini-web" },
  { url_prefix: "https://api.deepseek.com/v1/chat/completions", tool: "deepseek-web" },
  { url_prefix: "https://api.groq.com/openai/v1/chat/completions", tool: "groq-web" },
  { url_prefix: "https://api.cohere.ai/v2/chat", tool: "cohere-web" },
  { url_prefix: "https://api.together.xyz/v1/chat/completions", tool: "together-web" },
  { url_prefix: "https://api-inference.huggingface.co/models", tool: "huggingface-web" },
  { url_prefix: "https://api.mistral.ai/v1/chat/completions", tool: "mistral-web" },
  { url_prefix: "https://api.perplexity.ai/chat/completions", tool: "perplexity-web" },
];

const DEFAULT_AI_DOMAINS = [
  "chatgpt.com",
  "chat.openai.com",
  "platform.openai.com",
  "claude.ai",
  "console.anthropic.com",
  "gemini.google.com",
  "aistudio.google.com",
  "poe.com",
  "perplexity.ai",
  "you.com",
  "github.com/copilot",
  "idx.dev",
  "replit.com",
  "v0.dev",
  "bolt.new",
  "lovable.dev",
  "midjourney.com",
  "leonardo.ai",
  "runwayml.com",
  "elevenlabs.io",
  "suno.com",
  "phind.com",
  "copilot.microsoft.com",
  "deepseek.com",
  "groq.com",
  "together.ai",
  "huggingface.co",
  "pi.ai",
  "character.ai",
  "labs.google",
  "cohere.com",
];

// --- Dynamic config (loaded from agent or cache, falls back to defaults) ---

let activeDomains = DEFAULT_AI_DOMAINS;
let activeApiPatterns = DEFAULT_AI_API_PATTERNS;

/**
 * Read the agent base URL from chrome.storage.sync (falls back to default).
 */
async function getAgentBaseUrl() {
  const { agentBaseUrl } = await chrome.storage.sync.get({
    agentBaseUrl: DEFAULT_AGENT_BASE_URL,
  });
  return agentBaseUrl;
}

/**
 * Fetch extension config from the agent, cache it, and update active lists.
 * Falls back to cached config if agent is unreachable, then to hardcoded defaults.
 */
async function loadExtensionConfig() {
  try {
    const baseUrl = await getAgentBaseUrl();
    const response = await fetch(baseUrl + "/api/extension-config", {
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) {
      const config = await response.json();
      // Validate the response has expected shape
      if (Array.isArray(config.domains) && config.domains.length > 0) {
        activeDomains = config.domains;
      }
      if (Array.isArray(config.api_patterns) && config.api_patterns.length > 0) {
        activeApiPatterns = config.api_patterns;
      }
      // Cache the config for offline use
      await chrome.storage.local.set({ [STORAGE_EXTENSION_CONFIG_KEY]: config });
      console.log("Extension config loaded from agent:", activeDomains.length, "domains,", activeApiPatterns.length, "API patterns");
      return;
    }
  } catch {
    // Agent is unreachable — try cached config
  }

  // Try loading from cache
  try {
    const stored = await chrome.storage.local.get([STORAGE_EXTENSION_CONFIG_KEY]);
    const cached = stored[STORAGE_EXTENSION_CONFIG_KEY];
    if (cached) {
      if (Array.isArray(cached.domains) && cached.domains.length > 0) {
        activeDomains = cached.domains;
      }
      if (Array.isArray(cached.api_patterns) && cached.api_patterns.length > 0) {
        activeApiPatterns = cached.api_patterns;
      }
      console.log("Extension config loaded from cache:", activeDomains.length, "domains,", activeApiPatterns.length, "API patterns");
      return;
    }
  } catch {
    // Cache read failed
  }

  // Fall back to hardcoded defaults (already set at module level)
  activeDomains = DEFAULT_AI_DOMAINS;
  activeApiPatterns = DEFAULT_AI_API_PATTERNS;
  console.log("Extension config using hardcoded defaults:", activeDomains.length, "domains,", activeApiPatterns.length, "API patterns");
}

// Pending token intercept events (persisted to chrome.storage.local)
let pendingTokenEvents = [];
let pendingTokenEventsLoaded = false;

async function ensurePendingTokenEventsLoaded() {
  if (pendingTokenEventsLoaded) return;
  try {
    const stored = await chrome.storage.local.get([STORAGE_PENDING_TOKEN_EVENTS_KEY]);
    const raw = stored[STORAGE_PENDING_TOKEN_EVENTS_KEY];
    if (Array.isArray(raw)) {
      pendingTokenEvents = raw;
    }
  } catch {
    // Storage read failed — start with empty array
  }
  pendingTokenEventsLoaded = true;
}

async function persistPendingTokenEvents() {
  try {
    await chrome.storage.local.set({ [STORAGE_PENDING_TOKEN_EVENTS_KEY]: pendingTokenEvents });
  } catch {
    // Storage write failed — events remain in memory
  }
}

// Current session tracking
let currentDomain = null;
let sessionStart = null;

// Accumulated deltas since last export
let pendingDeltas = {};
let pendingDeltasLoaded = false;
let stateLock = Promise.resolve();

function withStateLock(fn) {
  stateLock = stateLock.then(fn, fn);
  return stateLock;
}

function normalizePendingDeltas(raw) {
  if (!raw || typeof raw !== "object") {
    return {};
  }

  const normalized = {};
  for (const [domain, value] of Object.entries(raw)) {
    if (!value || typeof value !== "object") {
      continue;
    }
    const duration = Number(value.duration ?? 0);
    const visits = Number(value.visits ?? 0);
    if (!Number.isFinite(duration) || !Number.isFinite(visits)) {
      continue;
    }
    if (duration > 0 || visits > 0) {
      normalized[domain] = { duration, visits };
    }
  }

  return normalized;
}

async function ensurePendingDeltasLoaded() {
  if (pendingDeltasLoaded) return;
  const stored = await chrome.storage.local.get([STORAGE_PENDING_DELTAS_KEY]);
  pendingDeltas = normalizePendingDeltas(stored[STORAGE_PENDING_DELTAS_KEY]);
  pendingDeltasLoaded = true;
}

async function persistPendingDeltas() {
  await chrome.storage.local.set({ [STORAGE_PENDING_DELTAS_KEY]: pendingDeltas });
}

function addPendingDelta(domain, durationSeconds, visits) {
  if (!pendingDeltas[domain]) {
    pendingDeltas[domain] = { duration: 0, visits: 0 };
  }
  pendingDeltas[domain].duration += durationSeconds;
  pendingDeltas[domain].visits += visits;
}

function buildEventsFromPendingDeltas() {
  const events = [];
  for (const [domain, data] of Object.entries(pendingDeltas)) {
    if (data.duration > 0 || data.visits > 0) {
      events.push({
        domain,
        duration_seconds: Math.round(data.duration * 100) / 100,
        visit_count: Math.max(0, Math.round(data.visits)),
        browser: "chrome",
      });
    }
  }
  return events;
}

/**
 * Check if a URL matches a tracked AI domain.
 * Uses the dynamic activeDomains list (loaded from agent config).
 */
function matchAIDomain(url) {
  if (!url) return null;
  try {
    const parsedUrl = new URL(url);
    const hostname = parsedUrl.hostname.toLowerCase();
    const pathname = parsedUrl.pathname;

    for (const domain of activeDomains) {
      if (domain.includes("/")) {
        const [domPart, ...pathParts] = domain.split("/");
        const pathPrefix = "/" + pathParts.join("/");
        if (
          (hostname === domPart || hostname.endsWith("." + domPart)) &&
          pathname.startsWith(pathPrefix)
        ) {
          return domain;
        }
      } else if (hostname === domain || hostname.endsWith("." + domain)) {
        return domain;
      }
    }
  } catch {
    // Invalid URL
  }
  return null;
}

/**
 * End the current session and accumulate delta.
 */
function endCurrentSession() {
  if (currentDomain && sessionStart) {
    const elapsed = (Date.now() - sessionStart) / 1000;
    if (elapsed > 0.5) {
      addPendingDelta(currentDomain, elapsed, 0);
    }
  }
  currentDomain = null;
  sessionStart = null;
}

/**
 * Start tracking a new domain session.
 */
function startSession(domain) {
  endCurrentSession();
  if (domain) {
    currentDomain = domain;
    sessionStart = Date.now();
    addPendingDelta(domain, 0, 1);
  }
}

/**
 * Handle tab activation / URL change.
 */
async function handleTabUpdate(url) {
  const domain = matchAIDomain(url);
  if (domain !== currentDomain) {
    await withStateLock(async () => {
      await ensurePendingDeltasLoaded();
      startSession(domain);
      await persistPendingDeltas();
    });
  }
}

// --- Chrome Events ---

chrome.tabs.onActivated.addListener(async (activeInfo) => {
  try {
    const tab = await chrome.tabs.get(activeInfo.tabId);
    await handleTabUpdate(tab.url);
  } catch {
    // Tab might not exist anymore
  }
});

chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.url && tab.active) {
    void handleTabUpdate(changeInfo.url);
  }
});

chrome.windows.onFocusChanged.addListener(async (windowId) => {
  if (windowId === chrome.windows.WINDOW_ID_NONE) {
    await withStateLock(async () => {
      await ensurePendingDeltasLoaded();
      endCurrentSession();
      await persistPendingDeltas();
    });
    return;
  }
  try {
    const [tab] = await chrome.tabs.query({ active: true, windowId });
    if (tab) {
      await handleTabUpdate(tab.url);
    }
  } catch {
    await withStateLock(async () => {
      await ensurePendingDeltasLoaded();
      endCurrentSession();
      await persistPendingDeltas();
    });
  }
});

// --- Periodic Export ---

chrome.alarms.create(ALARM_NAME, { periodInMinutes: EXPORT_INTERVAL_SECONDS / 60 });
chrome.alarms.create(CONFIG_ALARM_NAME, { periodInMinutes: CONFIG_REFRESH_MINUTES });

chrome.alarms.onAlarm.addListener((alarm) => {
  if (alarm.name === ALARM_NAME) {
    void exportMetrics();
    void exportTokenEvents();
  }
  if (alarm.name === CONFIG_ALARM_NAME) {
    void loadExtensionConfig();
  }
});

// --- API Response Interception ---

/**
 * Intercept completed AI API requests to record API call events.
 * Note: MV3 webRequest cannot read response bodies, so we record the call
 * and the agent correlates with API usage endpoints for actual token counts.
 *
 * Chrome requires static URL patterns in the listener filter, so we use a
 * broad filter based on the hardcoded defaults and check dynamically against
 * the activeApiPatterns list in the callback.
 */
chrome.webRequest.onCompleted.addListener(
  (details) => {
    if (details.method !== "POST" || details.statusCode !== 200) return;

    for (const api of activeApiPatterns) {
      const prefix = api.url_prefix;
      if (details.url.startsWith(prefix)) {
        pendingTokenEvents.push({
          type: "api_intercept",
          tool: api.tool,
          url: details.url,
          timestamp: new Date().toISOString(),
          input_tokens: 0,
          output_tokens: 0,
        });
        void persistPendingTokenEvents();
        break;
      }
    }
  },
  { urls: DEFAULT_AI_API_PATTERNS.map((p) => p.url_prefix + (p.url_prefix.endsWith("/") ? "*" : "/*")) }
);

/**
 * Export intercepted token events to the local agent.
 */
async function exportTokenEvents() {
  await ensurePendingTokenEventsLoaded();

  if (pendingTokenEvents.length === 0) return;

  const events = pendingTokenEvents;
  pendingTokenEvents = [];

  try {
    const baseUrl = await getAgentBaseUrl();
    const response = await fetch(baseUrl + "/api/tokens", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ events }),
    });
    if (!response.ok) {
      throw new Error(`Agent rejected token events: HTTP ${response.status}`);
    }
    // Successfully sent — clear from storage
    await persistPendingTokenEvents();
  } catch (error) {
    // Agent is down — re-queue events for next cycle
    if (error.message && error.message.includes("Failed to fetch")) {
      console.warn("Agent not reachable for token export. Will retry next cycle.");
    }
    pendingTokenEvents = events.concat(pendingTokenEvents);
    await persistPendingTokenEvents();
  }
}

/**
 * Export accumulated deltas to the local agent.
 */
async function exportMetrics() {
  await withStateLock(async () => {
    await ensurePendingDeltasLoaded();

    // Snapshot current session into deltas
    if (currentDomain && sessionStart) {
      const elapsed = (Date.now() - sessionStart) / 1000;
      if (elapsed > 0.5) {
        addPendingDelta(currentDomain, elapsed, 0);
      }
      // Reset session start to now (we've accounted for elapsed so far)
      sessionStart = Date.now();
    }

    const events = buildEventsFromPendingDeltas();
    if (events.length === 0) {
      await persistPendingDeltas();
      return;
    }

    try {
      const baseUrl = await getAgentBaseUrl();
      const response = await fetch(baseUrl + "/metrics/browser", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ events }),
      });
      if (!response.ok) {
        throw new Error(`Agent rejected metrics: HTTP ${response.status}`);
      }
    } catch (error) {
      if (error.message && error.message.includes("Failed to fetch")) {
        console.warn("Agent not reachable (connection refused). Is it running? Will retry next cycle.");
      } else {
        console.warn("Failed to export metrics, will retry on next cycle:", error.message);
      }
      await persistPendingDeltas();
      return;
    }

    // Only mark as exported after successful agent ack.
    pendingDeltas = {};
    await persistPendingDeltas();
    await updateDailyTotals(events);
  });
}

/**
 * Update daily totals in chrome.storage.local for popup display.
 */
async function updateDailyTotals(events) {
  const today = new Date().toISOString().slice(0, 10);
  const stored = await chrome.storage.local.get(["dailyTotals", "dailyDate"]);

  let totals = {};
  if (stored.dailyDate === today && stored.dailyTotals) {
    totals = stored.dailyTotals;
  }

  for (const event of events) {
    if (!totals[event.domain]) {
      totals[event.domain] = { duration: 0, visits: 0 };
    }
    totals[event.domain].duration += event.duration_seconds;
    totals[event.domain].visits += event.visit_count;
  }

  await chrome.storage.local.set({ dailyTotals: totals, dailyDate: today });
}

async function initializeState() {
  // Load dynamic config from agent (or cache, or defaults)
  await loadExtensionConfig();

  // Restore persisted state from chrome.storage.local
  await ensurePendingTokenEventsLoaded();
  await withStateLock(async () => {
    await ensurePendingDeltasLoaded();
  });

  try {
    const [tab] = await chrome.tabs.query({ active: true, lastFocusedWindow: true });
    if (tab) {
      await handleTabUpdate(tab.url);
    }
  } catch {
    // Best effort only.
  }
}

chrome.runtime.onStartup.addListener(() => {
  void initializeState();
});

chrome.runtime.onInstalled.addListener(() => {
  void initializeState();
});

void initializeState();
