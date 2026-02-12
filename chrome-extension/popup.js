/**
 * AI Cost Observer — Popup UI
 * Shows today's AI domain usage with time and estimated cost.
 * Loads cost rates from agent config (cached in chrome.storage.local),
 * falling back to hardcoded defaults.
 */

const DEFAULT_AGENT_BASE_URL = "http://127.0.0.1:8080";

/**
 * Read the agent base URL from chrome.storage.sync (falls back to default).
 */
async function getAgentBaseUrl() {
  const { agentBaseUrl } = await chrome.storage.sync.get({
    agentBaseUrl: DEFAULT_AGENT_BASE_URL,
  });
  return agentBaseUrl;
}

// Hardcoded fallback cost rates per hour in USD (used when no cached config)
const DEFAULT_COST_RATES = {
  "chatgpt.com": 0.5,
  "chat.openai.com": 0.5,
  "platform.openai.com": 1.0,
  "claude.ai": 0.6,
  "console.anthropic.com": 1.0,
  "gemini.google.com": 0.4,
  "aistudio.google.com": 0.8,
  "poe.com": 0.3,
  "perplexity.ai": 0.4,
  "you.com": 0.2,
  "github.com/copilot": 0.4,
  "idx.dev": 0.3,
  "replit.com": 0.5,
  "v0.dev": 0.6,
  "bolt.new": 0.5,
  "lovable.dev": 0.5,
  "midjourney.com": 1.2,
  "leonardo.ai": 0.8,
  "runwayml.com": 2.0,
  "elevenlabs.io": 0.6,
  "suno.com": 0.4,
  "phind.com": 0.3,
  "copilot.microsoft.com": 0.4,
  "deepseek.com": 0.2,
  "groq.com": 0.1,
  "together.ai": 0.3,
  "huggingface.co": 0.2,
  "pi.ai": 0.2,
  "character.ai": 0.2,
  "labs.google": 0.4,
  "cohere.com": 0.3,
};

// Active cost rates (loaded from cache or defaults)
let costRates = DEFAULT_COST_RATES;

/**
 * Load cost rates from cached extension config, fall back to hardcoded defaults.
 */
async function loadCostRates() {
  try {
    const stored = await chrome.storage.local.get(["extensionConfig"]);
    const cached = stored.extensionConfig;
    if (cached && cached.cost_rates && typeof cached.cost_rates === "object") {
      costRates = cached.cost_rates;
      return;
    }
  } catch {
    // Cache read failed
  }
  costRates = DEFAULT_COST_RATES;
}

function formatTime(seconds) {
  if (seconds < 60) return `${Math.round(seconds)}s`;
  const mins = Math.floor(seconds / 60);
  if (mins < 60) return `${mins}m`;
  const hrs = Math.floor(mins / 60);
  const remainMins = mins % 60;
  return `${hrs}h ${remainMins}m`;
}

function estimateCost(domain, durationSeconds) {
  const rate = costRates[domain] || 0;
  return rate * (durationSeconds / 3600);
}

async function loadData() {
  const today = new Date().toISOString().slice(0, 10);
  const stored = await chrome.storage.local.get(["dailyTotals", "dailyDate"]);

  if (stored.dailyDate !== today || !stored.dailyTotals) {
    return {};
  }
  return stored.dailyTotals;
}

async function render() {
  await loadCostRates();
  const totals = await loadData();
  const entries = Object.entries(totals).sort((a, b) => b[1].duration - a[1].duration);

  let totalSeconds = 0;
  let totalCost = 0;

  const listEl = document.getElementById("domainList");

  if (entries.length === 0) {
    listEl.innerHTML = '<div class="empty">No AI usage tracked today</div>';
    document.getElementById("totalTime").textContent = "0m";
    document.getElementById("totalCost").textContent = "$0.00";
    document.getElementById("totalDomains").textContent = "0";
    return;
  }

  listEl.innerHTML = "";

  for (const [domain, data] of entries) {
    totalSeconds += data.duration;
    const cost = estimateCost(domain, data.duration);
    totalCost += cost;

    const row = document.createElement("div");
    row.className = "domain-row";
    row.innerHTML = `
      <span class="domain-name" title="${domain}">${domain}</span>
      <span class="domain-time">${formatTime(data.duration)}</span>
      <span class="domain-cost">${cost > 0 ? "$" + cost.toFixed(2) : "Free"}</span>
    `;
    listEl.appendChild(row);
  }

  document.getElementById("totalTime").textContent = formatTime(totalSeconds);
  document.getElementById("totalCost").textContent = "$" + totalCost.toFixed(2);
  document.getElementById("totalDomains").textContent = entries.length.toString();
}

async function checkAgentStatus() {
  const dot = document.getElementById("statusDot");
  const text = document.getElementById("statusText");
  try {
    const baseUrl = await getAgentBaseUrl();
    const res = await fetch(baseUrl + "/health", { signal: AbortSignal.timeout(3000) });
    if (res.ok) {
      dot.className = "status-dot connected";
      text.textContent = "Agent connected";
    } else {
      dot.className = "status-dot disconnected";
      text.textContent = "Agent error";
    }
  } catch (err) {
    dot.className = "status-dot disconnected";
    if (err.name === "TypeError" || (err.message && err.message.includes("Failed to fetch"))) {
      text.textContent = "Connection refused — is the agent running?";
    } else if (err.name === "TimeoutError" || err.name === "AbortError") {
      text.textContent = "Agent not responding (timeout)";
    } else {
      text.textContent = "Agent offline";
    }
  }
}

// Open settings page
document.getElementById("openSettings").addEventListener("click", (e) => {
  e.preventDefault();
  chrome.runtime.openOptionsPage();
});

// Initialize
render();
checkAgentStatus();
