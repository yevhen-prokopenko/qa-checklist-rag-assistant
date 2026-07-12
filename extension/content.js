// Content script for QA Checklist Assistant.
// Injects the AI Assistant button below the description block and handles localized scanner overlays.

let lastTesterChecklist = [];
let lastAiApplied = [];
let lastSuggestions = [];
let lastTaskText = "";
let currentIssueKey = "";

// Jira SPA navigation observer
setInterval(injectButton, 2000);

function findDescriptionWrapper() {
  const selectors = [
    '[data-testid="issue.views.field.select-to-edit.description-wrapper"]',
    '[data-testid="issue.views.field.rich-text.description"]',
    '[data-testid="issue-field-description"]',
    '.description-field',
    '#description-val'
  ];

  for (let sel of selectors) {
    const el = document.querySelector(sel);
    if (el) return el;
  }

  // Fallback to searching heading
  const headings = Array.from(document.querySelectorAll('h2, h3, h4, h5, div'));
  for (let h of headings) {
    const txt = h.textContent.trim();
    if (txt === 'Описание' || txt === 'Description') {
      let next = h.nextElementSibling;
      if (next) return next;
      let parent = h.parentElement;
      if (parent) return parent;
    }
  }

  return null;
}

function getIssueKey() {
  return (location.pathname.match(/[A-Z]+-\d+/) || [])[0];
}

function isDarkMode() {
  const htmlTheme = document.documentElement.getAttribute("data-theme") || "";
  const htmlColorMode = document.documentElement.getAttribute("data-color-mode") || "";
  const bodyTheme = document.body.getAttribute("data-theme") || "";
  if (htmlTheme.includes("dark") || htmlColorMode.includes("dark") || bodyTheme.includes("dark")) {
    return true;
  }
  
  const bg = window.getComputedStyle(document.body).backgroundColor;
  const match = bg.match(/\d+/g);
  if (match && match.length >= 3) {
    const r = parseInt(match[0], 10);
    const g = parseInt(match[1], 10);
    const b = parseInt(match[2], 10);
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness < 128;
  }
  return false;
}

function injectButton() {
  const wrapper = findDescriptionWrapper();
  if (!wrapper) return;
  
  const sibling = wrapper.nextElementSibling;
  if (sibling && sibling.id === "qa-rag-btn-container") return;
  
  const old = document.getElementById("qa-rag-btn-container");
  if (old) old.remove();

  const container = document.createElement("div");
  container.id = "qa-rag-btn-container";
  container.className = "qa-btn-container-inline";

  const btn = document.createElement("button");
  btn.id = "qa-rag-btn";
  btn.className = "qa-rag-inline-btn";
  btn.innerHTML = "✨ QA AI Assistant";
  btn.onclick = onGenerate;

  container.appendChild(btn);
  wrapper.parentNode.insertBefore(container, wrapper.nextSibling);
}

function escapeHtml(str) {
  if (!str) return "";
  return str
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#039;");
}

function closeOverlay() {
  const backdrop = document.getElementById("qa-modal-backdrop");
  if (backdrop) backdrop.remove();
  const overlay = document.getElementById("qa-scanner-overlay");
  if (overlay) overlay.remove();
}

async function onGenerate() {
  const issueKey = getIssueKey();
  if (!issueKey) {
    alert("Jira key not found in URL.");
    return;
  }

  const wrapper = findDescriptionWrapper();
  if (!wrapper) {
    alert("Description wrapper not found.");
    return;
  }

  closeOverlay();

  const cleanText = (wrapper.innerText || wrapper.textContent || "").trim();
  const isEmpty = !cleanText || 
                  cleanText === "Add a description..." || 
                  cleanText === "Добавьте описание..." ||
                  cleanText === "Нажмите здесь, чтобы ввести описание" ||
                  cleanText.toLowerCase().includes("click here to add a description");

  // Update button with spinner — no overlay on the description, everything on the button
  const btn = document.getElementById("qa-rag-btn");
  let originalBtnHtml = "";
  if (btn) {
    originalBtnHtml = btn.innerHTML;
    btn.disabled = true;
    const initialText = isEmpty ? "Reading Description..." : "Analyzing requirements...";
    btn.innerHTML = `<span class="qa-spinner"></span> <span class="qa-btn-text">${initialText}</span>`;
  }

  currentIssueKey = issueKey;

  // Sequentially update button text while waiting
  let step = 1;
  const textInterval = setInterval(() => {
    if (btn) {
      const txtEl = btn.querySelector(".qa-btn-text");
      if (txtEl) {
        if (!isEmpty) {
          if (step === 1) {
            txtEl.textContent = "Querying database...";
            step = 2;
          } else if (step === 2) {
            txtEl.textContent = "Generating QA recommendations...";
            clearInterval(textInterval);
          }
        } else {
          if (step === 1) {
            txtEl.textContent = "Preparing template...";
            clearInterval(textInterval);
          }
        }
      }
    }
  }, 1500);

  // API call + minimum 3s perceived latency
  const apiPromise = new Promise((resolve) => {
    chrome.runtime.sendMessage({ type: "SUGGEST_FROM_JIRA", issueKey }, resolve);
  });
  const timerPromise = new Promise(resolve => setTimeout(resolve, 3000));

  const [res] = await Promise.all([apiPromise, timerPromise]);

  clearInterval(textInterval);
  if (btn) {
    btn.disabled = false;
    btn.innerHTML = originalBtnHtml;
  }

  if (!res || !res.ok) {
    showModal(() => showErrorContent("Connection error. Is the backend server running?"));
    return;
  }

  const data = res.data;
  if (data.error) {
    showModal((overlay) => showTemplateContent(overlay, data.error, data.template, issueKey));
  } else {
    lastTesterChecklist = data.tester_checklist || [];
    lastAiApplied = data.ai_applied || [];
    lastSuggestions = data.suggestions || [];
    lastTaskText = `${issueKey}: ${data.summary || ""}`;
    showModal((overlay) => showSuggestionsContent(overlay, data.suggestions || [], issueKey));
  }
}

function showModal(contentFn) {
  closeOverlay();
  const dark = isDarkMode();

  const backdrop = document.createElement("div");
  backdrop.id = "qa-modal-backdrop";
  backdrop.style.cssText = `
    position: fixed;
    inset: 0;
    background: rgba(9, 30, 66, 0.54);
    z-index: 9998;
    display: flex;
    align-items: center;
    justify-content: center;
  `;
  document.body.appendChild(backdrop);

  const overlay = document.createElement("div");
  overlay.id = "qa-scanner-overlay";
  overlay.className = "qa-scanner-overlay results-active" + (dark ? " qa-dark-theme" : "");
  backdrop.appendChild(overlay);

  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop) closeOverlay();
  });

  contentFn(overlay);
}

function showErrorContent(msg) {
  const overlay = document.getElementById("qa-scanner-overlay");
  if (!overlay) return;
  overlay.innerHTML = `
    <div class="qa-overlay-error">
      <p>⚠️ ${escapeHtml(msg)}</p>
      <button id="qa-overlay-error-cancel" class="qa-btn-cancel-manual" style="margin-top: 12px;">Close</button>
    </div>
  `;
  document.getElementById("qa-overlay-error-cancel").onclick = closeOverlay;
}

function showTemplateContent(overlay, errorMsg, template, issueKey) {
  overlay.innerHTML = `
    <div class="qa-overlay-error">
      <p>⚠️ ${escapeHtml(errorMsg)}</p>
      <pre class="qa-overlay-template-pre">${escapeHtml(template)}</pre>
      <div class="qa-overlay-actions">
        <button id="qa-overlay-insert" class="qa-btn-insert">✍️ Insert into Description</button>
        <button id="qa-overlay-cancel" class="qa-btn-cancel-manual">Cancel</button>
      </div>
    </div>
  `;

  document.getElementById("qa-overlay-cancel").onclick = closeOverlay;

  const insertBtn = document.getElementById("qa-overlay-insert");
  insertBtn.onclick = () => {
    insertBtn.textContent = "⏳ Inserting...";
    insertBtn.disabled = true;

    chrome.runtime.sendMessage(
      { type: "WRITE_TEMPLATE_TO_JIRA", payload: { issue_key: issueKey, template: template } },
      (res) => {
        if (res && res.ok && res.data && res.data.ok) {
          insertBtn.textContent = "Done! Reloading...";
          setTimeout(() => window.location.reload(), 1000);
        } else {
          insertBtn.textContent = "Error ❌";
          insertBtn.disabled = false;
          alert((res && res.error) || (res && res.data && res.data.error) || "Failed to update Jira.");
        }
      }
    );
  };
}

function showSuggestionsContent(overlay, suggestions, issueKey) {
  if (!Array.isArray(suggestions)) suggestions = [];
  if (!Array.isArray(lastTesterChecklist)) lastTesterChecklist = [];
  if (!Array.isArray(lastAiApplied)) lastAiApplied = [];

  // Human rows — written by tester
  const humanRows = lastTesterChecklist
    .map((item) => `
      <tr class="qa-human-row">
        <td>🧑</td>
        <td>${escapeHtml(item)}</td>
        <td class="qa-why">your checklist</td>
      </tr>`)
    .join("");

  // AI-applied rows from previous runs — already in description, just show for context
  const aiAppliedRows = lastAiApplied
    .map((item) => `
      <tr class="qa-ai-applied-row">
        <td>🤖</td>
        <td>${escapeHtml(item)}</td>
        <td class="qa-why">applied previously</td>
      </tr>`)
    .join("");

  // New AI suggestions — with checkboxes
  const aiRows = suggestions
    .map((s, i) => `
      <tr>
        <td><input type="checkbox" class="qa-row-check" data-i="${i}" checked> 🤖</td>
        <td>${escapeHtml(s.item)}</td>
        <td class="qa-why">${escapeHtml(s.why)}</td>
      </tr>`)
    .join("");

  const hasSuggestions = suggestions.length > 0;

  const headingHtml = hasSuggestions
    ? `<h4 class="qa-overlay-heading">Final checklist — 🧑 you + 🤖 AI suggestions</h4>`
    : `
      <div class="qa-overlay-heading-empty">
        <h4 class="qa-nothing-to-add">NOTHING TO ADD</h4>
        <p class="qa-nothing-sub">From the perspective of the testing knowledge base, the checklist is complete.</p>
      </div>
    `;

  const actionsHtml = hasSuggestions
    ? `
      <button id="qa-overlay-apply" class="qa-btn-primary">Apply Selected</button>
      <button id="qa-overlay-cancel" class="qa-btn-secondary">Cancel</button>
    `
    : `<button id="qa-overlay-close" class="qa-btn-primary">Close</button>`;

  overlay.innerHTML = `
    ${headingHtml}
    <div class="qa-table-scroll-container">
      <table class="qa-table">
        <thead>
          <tr>
            <th>Human/AI</th>
            <th>QA Checklist</th>
            <th>Why</th>
          </tr>
        </thead>
        <tbody>
          ${humanRows}
          ${aiAppliedRows}
          ${aiRows}
        </tbody>
      </table>
    </div>
    <div class="qa-actions">
      ${actionsHtml}
    </div>
  `;

  if (hasSuggestions) {
    document.getElementById("qa-overlay-cancel").onclick = closeOverlay;

    const applyBtn = document.getElementById("qa-overlay-apply");
    applyBtn.onclick = () => {
      const checkedEls = document.querySelectorAll(".qa-row-check:checked");
      const checked = Array.from(checkedEls).map(el => suggestions[Number(el.dataset.i)]);
      
      if (!checked.length && suggestions.length > 0) {
        alert("Select at least one recommendation to apply, or cancel.");
        return;
      }

      applyBtn.textContent = "Applying...";
      applyBtn.disabled = true;

      chrome.runtime.sendMessage({
        type: "APPLY_TO_JIRA",
        payload: {
          issue_key: issueKey,
          task_text: lastTaskText,
          tester_checklist: lastTesterChecklist,
          ai_applied: lastAiApplied,
          applied_items: checked
        }
      }, (res) => {
        if (res && res.ok && res.data && !res.data.error) {
          applyBtn.textContent = "Done! Reloading...";
          setTimeout(() => window.location.reload(), 1000);
        } else {
          applyBtn.textContent = "Error ❌";
          applyBtn.disabled = false;
          alert((res && res.error) || (res && res.data && res.data.error) || "Failed to apply checklist.");
        }
      });
    };
  } else {
    document.getElementById("qa-overlay-close").onclick = closeOverlay;
  }
}
