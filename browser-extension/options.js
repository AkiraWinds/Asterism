const DEFAULT_BACKEND_URL = "http://localhost:8000";

function setStatus(text) {
  document.getElementById("status").textContent = text;
}

async function load() {
  const { backendUrl } = await chrome.storage.sync.get("backendUrl");
  document.getElementById("backendUrl").value = backendUrl || DEFAULT_BACKEND_URL;
}

document.getElementById("save").addEventListener("click", async () => {
  const raw = document.getElementById("backendUrl").value.trim().replace(/\/+$/, "");
  if (!raw) {
    setStatus("Backend URL cannot be empty.");
    return;
  }

  let origin;
  try {
    origin = new URL(raw).origin;
  } catch {
    setStatus("Not a valid URL.");
    return;
  }

  const originPattern = `${origin}/*`;
  const hasPermission = await chrome.permissions.contains({ origins: [originPattern] });
  if (!hasPermission) {
    const granted = await chrome.permissions.request({ origins: [originPattern] });
    if (!granted) {
      setStatus("Permission denied — the extension can't reach that URL without it.");
      return;
    }
  }

  await chrome.storage.sync.set({ backendUrl: raw });
  setStatus("Saved.");
});

load();
