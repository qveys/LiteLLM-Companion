/**
 * AI Cost Observer — Options Page
 * Manages the agent base URL configuration.
 */

const DEFAULT_AGENT_BASE_URL = "http://127.0.0.1:8080";

const agentUrlInput = document.getElementById("agentUrl");
const saveBtn = document.getElementById("saveBtn");
const statusEl = document.getElementById("status");
const statusText = document.getElementById("statusText");

/**
 * Load saved settings from chrome.storage.sync.
 */
async function loadSettings() {
  const { agentBaseUrl } = await chrome.storage.sync.get({
    agentBaseUrl: DEFAULT_AGENT_BASE_URL,
  });
  agentUrlInput.value = agentBaseUrl;
}

/**
 * Show a status message below the save button.
 */
function showStatus(message, type) {
  statusEl.className = "status visible " + type;
  statusText.textContent = message;
  setTimeout(hideStatus, 5000);
}

/**
 * Hide the status message.
 */
function hideStatus() {
  statusEl.className = "status";
}

/**
 * Normalize the URL: trim whitespace and remove trailing slashes.
 */
function normalizeUrl(url) {
  const normalized = url.trim().replace(/\/+$/, "");
  try {
    new URL(normalized);
    return normalized;
  } catch {
    return null;
  }
}

/**
 * Save settings to chrome.storage.sync, then test the connection.
 */
async function saveSettings() {
  const url = normalizeUrl(agentUrlInput.value);

  if (!url) {
    showStatus("Please enter a valid URL.", "warning");
    return;
  }

  agentUrlInput.value = url;

  await chrome.storage.sync.set({ agentBaseUrl: url });

  showStatus("Saved. Testing connection...", "success");

  try {
    const healthUrl = url + "/health";
    const response = await fetch(healthUrl, {
      signal: AbortSignal.timeout(5000),
    });
    if (response.ok) {
      showStatus("Saved. Agent connected.", "success");
    } else {
      showStatus("Saved. Agent returned HTTP " + response.status + ".", "error");
    }
  } catch {
    showStatus("Saved. Could not reach agent.", "error");
  }
}

saveBtn.addEventListener("click", saveSettings);

agentUrlInput.addEventListener("input", hideStatus);

agentUrlInput.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    saveSettings();
  }
});

loadSettings();
