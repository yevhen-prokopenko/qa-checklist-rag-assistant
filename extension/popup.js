const BACKEND = "http://localhost:8000";
const statusEl = document.getElementById("status");

fetch(`${BACKEND}/health`)
  .then((r) => r.json())
  .then((d) => {
    if (d.ok) {
      statusEl.innerHTML = "Backend: Connected ✅";
      chrome.action.setBadgeText({ text: "●" });
      chrome.action.setBadgeBackgroundColor({ color: "#00875a" }); // Green
    } else {
      statusEl.innerHTML = "Backend: Error ❌";
      chrome.action.setBadgeText({ text: "●" });
      chrome.action.setBadgeBackgroundColor({ color: "#de350b" }); // Red
    }
  })
  .catch(() => {
    statusEl.innerHTML = "Backend: Offline ❌";
    chrome.action.setBadgeText({ text: "●" });
    chrome.action.setBadgeBackgroundColor({ color: "#de350b" }); // Red
  });
