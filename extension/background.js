// Service worker (MV3). Performs the actual network calls to the local
// backend on behalf of content scripts and updates connection badge state.
const BACKEND = "http://localhost:8000";

function updateBadge() {
  fetch(`${BACKEND}/health`)
    .then((r) => r.json())
    .then((d) => {
      if (d.ok) {
        chrome.action.setBadgeText({ text: "●" });
        chrome.action.setBadgeBackgroundColor({ color: "#00875a" }); // Green
      } else {
        chrome.action.setBadgeText({ text: "●" });
        chrome.action.setBadgeBackgroundColor({ color: "#de350b" }); // Red
      }
    })
    .catch(() => {
      chrome.action.setBadgeText({ text: "●" });
      chrome.action.setBadgeBackgroundColor({ color: "#de350b" }); // Red
    });
}

chrome.runtime.onInstalled.addListener(() => {
  console.log("QA Checklist Assistant installed.");
  updateBadge();
});

chrome.runtime.onStartup.addListener(() => {
  updateBadge();
});

chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  // Update badge on any message exchange
  updateBadge();

  if (msg.type === "SUGGEST_FROM_JIRA") {
    fetch(`${BACKEND}/suggest-from-jira`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ issue_key: msg.issueKey }),
    })
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true; // keep channel open
  }

  if (msg.type === "APPLY_TO_JIRA") {
    fetch(`${BACKEND}/apply-to-jira`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.payload),
    })
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }

  if (msg.type === "WRITE_TEMPLATE_TO_JIRA") {
    fetch(`${BACKEND}/write-template-to-jira`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(msg.payload),
    })
      .then((r) => r.json())
      .then((data) => sendResponse({ ok: true, data }))
      .catch((err) => sendResponse({ ok: false, error: String(err) }));
    return true;
  }
});
