(function () {
  function ensureSidebarToggle() {
    const sidebar = document.querySelector(".app-sidebar");
    const main = document.querySelector(".app-main");
    const brandCard = document.querySelector(".brand-card");
    if (!sidebar || !main || !brandCard) return;

    let toggle = document.querySelector(".sidebar-toggle");
    if (!toggle) {
      toggle = document.createElement("button");
      toggle.type = "button";
      toggle.className = "sidebar-toggle";
      toggle.setAttribute("aria-label", "Toggle sidebar");
      toggle.innerHTML = '<span></span><span></span><span></span>';
      brandCard.appendChild(toggle);
    }

    const stored = window.localStorage.getItem("sgiSidebarCollapsed");
    if (stored === "1") {
      document.body.classList.add("sidebar-collapsed");
    }

    toggle.addEventListener("click", function () {
      document.body.classList.toggle("sidebar-collapsed");
      window.localStorage.setItem(
        "sgiSidebarCollapsed",
        document.body.classList.contains("sidebar-collapsed") ? "1" : "0"
      );
    });
  }

  function ensureToastContainer() {
    let container = document.querySelector(".toast-stack");
    if (!container) {
      container = document.createElement("div");
      container.className = "toast-stack";
      document.body.appendChild(container);
    }
    return container;
  }

  window.showToast = function (message, type) {
    if (!message) return;
    const container = ensureToastContainer();
    const toast = document.createElement("div");
    toast.className = "toast toast-" + (type || "info");
    toast.innerHTML = `
      <div class="toast-glow"></div>
      <div class="toast-body">
        <strong>${type === "error" ? "Error" : type === "success" ? "Success" : "Notice"}</strong>
        <span>${String(message)
          .replace(/&/g, "&amp;")
          .replace(/</g, "&lt;")
          .replace(/>/g, "&gt;")
          .replace(/"/g, "&quot;")
          .replace(/'/g, "&#39;")}</span>
      </div>
      <button type="button" class="toast-close" aria-label="Close notification">x</button>
    `;

    const close = function () {
      toast.classList.add("leaving");
      window.setTimeout(function () {
        toast.remove();
      }, 360);
    };

    toast.querySelector(".toast-close").addEventListener("click", close);
    container.appendChild(toast);
    window.setTimeout(close, 5000);
  };

  function hydrateServerMessages() {
    document.querySelectorAll(".page-banner, .auth-message").forEach(function (node) {
      const text = node.textContent.trim();
      if (!text) return;
      let type = "info";
      if (node.classList.contains("error")) type = "error";
      if (node.classList.contains("success")) type = "success";
      node.style.display = "none";
      window.showToast(text, type);
    });
  }

  ensureSidebarToggle();
  ensureToastContainer();
  hydrateServerMessages();
})();
