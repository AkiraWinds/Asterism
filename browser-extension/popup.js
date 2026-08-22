const DEFAULT_BACKEND_URL = "http://localhost:8000";

function setStatus(text, kind) {
  const el = document.getElementById("status");
  el.textContent = text;
  el.className = kind || "";
}

async function getBackendUrl() {
  const { backendUrl } = await chrome.storage.sync.get("backendUrl");
  return backendUrl || DEFAULT_BACKEND_URL;
}

async function capturePage(tabId) {
  const [{ result }] = await chrome.scripting.executeScript({
    target: { tabId },
    func: () => ({
      html: document.documentElement.outerHTML,
      title: document.title,
      url: location.href,
    }),
  });
  return result;
}

function setTriageResult(text, kind) {
  const el = document.getElementById("triage-result");
  el.textContent = text;
  el.className = kind || "";
}

function triageKind(action) {
  if (action === "must_read" || action === "worth_reading") return "good";
  if (action === "skim") return "mid";
  return "low"; // summary_only, skip
}

document.getElementById("analyze").addEventListener("click", async () => {
  setTriageResult("Analyzing…");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const { html, title, url } = await capturePage(tab.id);
    const backendUrl = await getBackendUrl();

    const origin = new URL(backendUrl).origin;
    const hasPermission = await chrome.permissions.contains({ origins: [`${origin}/*`] });
    if (!hasPermission) {
      setTriageResult("Backend access not granted — open the extension's Options page and re-grant access to this URL.", "low");
      return;
    }

    const response = await fetch(`${backendUrl}/sources/preview-triage`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, html }),
    });

    const body = await response.json();
    if (!response.ok) {
      setTriageResult(body.message || `Analyze failed (${response.status})`, "low");
      return;
    }

    if (body.duplicate) {
      setTriageResult(`Already in your library: ${body.title}`);
      return;
    }

    const { score, action, reason } = body.triage;
    setTriageResult(`${score}/100 — ${action}: ${reason}`, triageKind(action));
  } catch (err) {
    setTriageResult(`Error: ${err.message}`, "low");
  }
});

document.getElementById("save").addEventListener("click", async () => {
  setStatus("Saving…");
  try {
    const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
    const { html, title, url } = await capturePage(tab.id);
    const backendUrl = await getBackendUrl();

    const origin = new URL(backendUrl).origin;
    const hasPermission = await chrome.permissions.contains({ origins: [`${origin}/*`] });
    if (!hasPermission) {
      setStatus("Backend access not granted — open the extension's Options page and re-grant access to this URL.", "error");
      return;
    }

    const response = await fetch(`${backendUrl}/sources`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, html }),
    });

    const body = await response.json();
    if (!response.ok) {
      setStatus(body.message || `Save failed (${response.status})`, "error");
      return;
    }
    setStatus(`Saved: ${body.title}`, "success");
  } catch (err) {
    setStatus(`Error: ${err.message}`, "error");
  }
});
