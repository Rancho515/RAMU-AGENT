(function () {
  const SUPPORT_NUMBER = "918826219600";
  const pageName = document.body.dataset.supportPage || "dashboard";

  const issueOptions = {
    dashboard: [
      "Dashboard data not updating",
      "Call stats look wrong",
      "Cannot see approved agent",
      "Need help understanding call status"
    ],
    outbound: [
      "Call is not starting",
      "Bulk upload issue",
      "Phone number format problem",
      "Realtime call status not updating"
    ],
    settings: [
      "Credential approval failed",
      "agent_checker credential not matching",
      "SIP or assigned number missing",
      "Need help activating outbound"
    ],
    cdr: [
      "Call detail record not loading",
      "Wallet balance calculation issue",
      "Minutes or billing amount looks wrong",
      "Customer record filter mismatch"
    ]
  };

  const outcomeOptions = [
    "Need quick troubleshooting",
    "Need account verification",
    "Need outbound to start working",
    "Need someone from support to contact me"
  ];

  const issueList = issueOptions[pageName] || issueOptions.dashboard;

  const fab = document.createElement("button");
  fab.type = "button";
  fab.className = "support-fab";
  fab.setAttribute("aria-label", "Open WhatsApp support");
  fab.innerHTML = `
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M20.52 3.48A11.8 11.8 0 0 0 12.12 0C5.49 0 .12 5.37.12 12c0 2.11.55 4.17 1.59 5.99L0 24l6.2-1.63A11.9 11.9 0 0 0 12.12 24h.01c6.62 0 11.99-5.37 11.99-12a11.85 11.85 0 0 0-3.6-8.52ZM12.13 21.9a9.9 9.9 0 0 1-5.06-1.39l-.36-.22-3.68.97.98-3.59-.23-.37a9.84 9.84 0 0 1-1.52-5.3c0-5.43 4.42-9.85 9.87-9.85 2.63 0 5.1 1.02 6.96 2.89A9.8 9.8 0 0 1 21.98 12c0 5.43-4.42 9.9-9.85 9.9Zm5.4-7.43c-.3-.15-1.78-.88-2.06-.98-.27-.1-.47-.15-.67.15-.2.3-.77.98-.95 1.18-.17.2-.35.23-.65.08-.3-.15-1.25-.46-2.38-1.46a8.9 8.9 0 0 1-1.65-2.05c-.17-.3-.02-.46.13-.6.13-.13.3-.35.45-.52.15-.18.2-.3.3-.5.1-.2.05-.38-.03-.53-.08-.15-.67-1.61-.92-2.21-.24-.58-.48-.5-.67-.5h-.57c-.2 0-.52.08-.8.38s-1.04 1.01-1.04 2.46 1.07 2.85 1.22 3.05c.15.2 2.11 3.21 5.1 4.5.71.31 1.27.5 1.7.64.72.23 1.37.2 1.89.12.58-.08 1.78-.73 2.03-1.43.25-.7.25-1.31.18-1.43-.08-.12-.28-.2-.58-.35Z"></path>
    </svg>
  `;

  const panel = document.createElement("div");
  panel.className = "support-panel";
  panel.innerHTML = `
    <h3>WhatsApp Support</h3>
    <p>Tell us the issue and the expected outcome. We will prepare a short message for support on +91 88262 19600.</p>
    <label for="supportIssue">Possible issue</label>
    <select id="supportIssue">
      ${issueList.map((item) => `<option value="${item}">${item}</option>`).join("")}
    </select>
    <label for="supportOutcome">Expected outcome</label>
    <select id="supportOutcome">
      ${outcomeOptions.map((item) => `<option value="${item}">${item}</option>`).join("")}
    </select>
    <label for="supportNote">Short note</label>
    <textarea id="supportNote" placeholder="Add any small detail here..."></textarea>
    <div class="support-preview" id="supportPreview"></div>
    <div class="support-actions">
      <button type="button" class="support-btn secondary" id="supportCancel">Close</button>
      <button type="button" class="support-btn primary" id="supportSend">Send to WhatsApp</button>
    </div>
  `;

  document.body.appendChild(fab);
  document.body.appendChild(panel);

  const issueSelect = panel.querySelector("#supportIssue");
  const outcomeSelect = panel.querySelector("#supportOutcome");
  const noteField = panel.querySelector("#supportNote");
  const preview = panel.querySelector("#supportPreview");
  const cancel = panel.querySelector("#supportCancel");
  const send = panel.querySelector("#supportSend");

  function buildMessage() {
    const note = noteField.value.trim();
    const lines = [
      `Hello support team,`,
      `We are facing an AI agent issue from the ${pageName} page.`,
      `Issue: ${issueSelect.value}.`,
      `Expected outcome: ${outcomeSelect.value}.`
    ];

    if (note) {
      lines.push(`Note: ${note}.`);
    }

    lines.push(`Please help us resolve this as soon as possible.`);
    return lines.join(" ");
  }

  function refreshPreview() {
    preview.textContent = buildMessage();
  }

  fab.addEventListener("click", function () {
    panel.classList.toggle("open");
    refreshPreview();
  });

  cancel.addEventListener("click", function () {
    panel.classList.remove("open");
  });

  send.addEventListener("click", function () {
    const message = encodeURIComponent(buildMessage());
    window.open(`https://wa.me/${SUPPORT_NUMBER}?text=${message}`, "_blank");
  });

  issueSelect.addEventListener("change", refreshPreview);
  outcomeSelect.addEventListener("change", refreshPreview);
  noteField.addEventListener("input", refreshPreview);
  refreshPreview();
})();
