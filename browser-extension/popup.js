const DEFAULT_BACKEND_URL = "http://localhost:8000";
// How long a pendingSaveUrl flag (see the Save handler) is trusted as still
// meaningful. Past this, whatever request it referred to has certainly
// finished one way or another (success, error, or the 45s client timeout
// itself), so treat it as stale rather than showing a misleading "may still
// be finishing" message indefinitely.
const PENDING_SAVE_STALE_MS = 5 * 60 * 1000;

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
  // Both buttons hit the same backend, so a concurrent Save while an Analyze
  // is in flight (or a second Analyze click) is undesirable — disable both
  // for the duration of this request and always re-enable via try/finally,
  // regardless of success, error, or timeout.
  const analyzeButton = document.getElementById("analyze");
  const saveButton = document.getElementById("save");
  analyzeButton.disabled = true;
  saveButton.disabled = true;

  // The backend's LLM providers can have long timeouts and run_triage retries
  // once on failure, so a slow/hung provider call can take many minutes.
  // Meanwhile the popup is destroyed the moment it loses focus, aborting the
  // fetch client-side while the backend keeps working — so cap our own wait
  // at 45s rather than letting the user stare at "Analyzing…" indefinitely.
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 45000);
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
      signal: controller.signal,
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
    if (err.name === "AbortError") {
      setTriageResult("Analyze took too long — the backend may still be working; try again in a moment.", "low");
    } else {
      setTriageResult(`Error: ${err.message}`, "low");
    }
  } finally {
    clearTimeout(timeoutId);
    analyzeButton.disabled = false;
    saveButton.disabled = false;
  }
});

document.getElementById("save").addEventListener("click", async () => {
  setStatus("Saving…");
  // Mirror the Analyze handler's timeout/disable/finally pattern (see its
  // comment above): the backend save can legitimately take 60s+ (the
  // AI-extraction fallback path), and the popup's whole DOM/JS context is
  // destroyed the instant it loses focus, not just paused — so a save that
  // outlives the popup being closed used to leave "Saving…" on screen
  // forever with no way for the user to tell it actually finished.
  const analyzeButton = document.getElementById("analyze");
  const saveButton = document.getElementById("save");
  analyzeButton.disabled = true;
  saveButton.disabled = true;

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 45000);
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

    // Recorded before the fetch so that if this popup context is torn down
    // mid-request (see above), the next popup open can tell the user a save
    // may still be in flight rather than showing blank default state.
    // Cleared below only once the outcome is actually known (success, or an
    // error response the server has definitively returned) — NOT on the
    // AbortError/timeout path, whose entire point is that the outcome is
    // still unknown when this context sees it.
    await chrome.storage.session.set({ pendingSaveUrl: url, pendingSaveAt: Date.now() });

    const response = await fetch(`${backendUrl}/sources`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ url, title, html }),
      signal: controller.signal,
    });

    const body = await response.json();
    await clearPendingSave();
    if (!response.ok) {
      setStatus(body.message || `Save failed (${response.status})`, "error");
      return;
    }
    setStatus(`Saved: ${body.title}`, "success");
  } catch (err) {
    if (err.name === "AbortError") {
      // Outcome still unknown — leave pendingSaveUrl set so a reopened popup
      // (this one, or a later one) can tell the user rather than clearing
      // the exact flag this message just told them would let them recover.
      setStatus("Save took too long — the backend may still be working. Reopening and clicking Save again is safe (duplicates are detected automatically).", "error");
    } else {
      await clearPendingSave();
      setStatus(`Error: ${err.message}`, "error");
    }
  } finally {
    clearTimeout(timeoutId);
    analyzeButton.disabled = false;
    saveButton.disabled = false;
  }
});

async function clearPendingSave() {
  try {
    await chrome.storage.session.remove(["pendingSaveUrl", "pendingSaveAt"]);
  } catch {
    // Best-effort only — if this popup context is being torn down right
    // now, the flag is exactly what the next popup open should still see.
  }
}

// If a previous popup was destroyed mid-save (see above), pendingSaveUrl
// survives in session storage and this tells the user rather than showing
// silent blank default state. Anything older than PENDING_SAVE_STALE_MS is
// certainly resolved by now (success, error, or its own 45s client timeout)
// even if this context never saw how — showing the warning forever would be
// actively misleading, so treat it as stale and clear it silently instead.
(async () => {
  try {
    const { pendingSaveUrl, pendingSaveAt } = await chrome.storage.session.get(["pendingSaveUrl", "pendingSaveAt"]);
    if (!pendingSaveUrl) return;
    if (!pendingSaveAt || Date.now() - pendingSaveAt > PENDING_SAVE_STALE_MS) {
      await clearPendingSave();
      return;
    }
    setStatus(`A previous save of ${pendingSaveUrl} may still be finishing — click Save again to check; duplicates are detected automatically, so retrying is safe.`);
  } catch {
    // chrome.storage.session unavailable (older Chrome) — nothing to recover.
  }
})();
