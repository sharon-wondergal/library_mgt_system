/* ==========================================================================
   Campus Library -- front-end behaviour
   1. Sidebar toggle (mobile / tablet)
   2. Notifications: dismiss + auto-hide
   3. Delete confirmation dialog
   4. Client-side form validation (mirrors validators.py)
   5. Live ISBN check against the server (/api/isbn-check)
   6. Quantity stepper and stock form checks
   7. Auto-submit filters
   The server validates everything again -- this layer is for convenience.
   ========================================================================== */
(function () {
  "use strict";

  const $ = (sel, root = document) => root.querySelector(sel);
  const $$ = (sel, root = document) => Array.from(root.querySelectorAll(sel));

  /* ---------------- 1. Sidebar ---------------- */
  const sidebar = $("#sidebar");
  const openBtn = $("[data-sidebar-open]");
  function setSidebar(open) {
    if (!sidebar) return;
    sidebar.classList.toggle("open", open);
    if (openBtn) openBtn.setAttribute("aria-expanded", String(open));
  }
  if (openBtn) openBtn.addEventListener("click", () => setSidebar(true));
  $$("[data-sidebar-close]").forEach((el) => el.addEventListener("click", () => setSidebar(false)));

  /* ---------------- 2. Notifications ---------------- */
  function dismiss(alert) {
    alert.classList.add("fade-out");
    setTimeout(() => alert.remove(), 300);
  }
  $$("[data-alert]").forEach((alert) => {
    const close = $("[data-alert-close]", alert);
    if (close) close.addEventListener("click", () => dismiss(alert));
    // Success and info messages fade after 6 s; errors and warnings stay.
    if (alert.classList.contains("alert-success") || alert.classList.contains("alert-info")) {
      setTimeout(() => alert.isConnected && dismiss(alert), 6000);
    }
  });

  /* ---------------- 3. Delete confirmation ---------------- */
  const modal = $("#delete-modal");
  let lastTrigger = null;
  if (modal) {
    const form = $("#delete-modal-form", modal);
    const check = $("#delete-confirm-check", modal);
    const confirmBtn = $("#delete-confirm-btn", modal);

    const close = () => {
      modal.hidden = true;
      document.body.classList.remove("modal-open");
      if (lastTrigger) lastTrigger.focus();
    };

    $$("[data-delete-trigger]").forEach((link) => {
      link.addEventListener("click", (event) => {
        event.preventDefault();
        lastTrigger = link;
        form.action = link.href;              // POST /books/<id>/delete
        $("[data-delete-title]", modal).textContent = link.dataset.title;
        $("[data-delete-isbn]", modal).textContent = link.dataset.isbn;
        check.checked = false;
        confirmBtn.disabled = true;
        modal.hidden = false;
        document.body.classList.add("modal-open");
        $("[data-modal-close]", modal).focus(); // safest default: Cancel
      });
    });

    check.addEventListener("change", () => { confirmBtn.disabled = !check.checked; });
    form.addEventListener("submit", (event) => {
      if (!check.checked) event.preventDefault();
      else confirmBtn.disabled = true;        // prevent double submission
    });
    $$("[data-modal-close]", modal).forEach((b) => b.addEventListener("click", close));
    modal.addEventListener("click", (event) => { if (event.target === modal) close(); });
    document.addEventListener("keydown", (event) => {
      if (event.key === "Escape" && !modal.hidden) close();
    });
  }
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") setSidebar(false);
  });

  /* ---------------- 4. Validation helpers ---------------- */
  function normalizeIsbn(value) {
    return (value || "").replace(/[\s-]/g, "").toUpperCase();
  }
  function isValidIsbn(isbn) {
    if (/^\d{9}[\dX]$/.test(isbn)) {
      let sum = 0;
      for (let i = 0; i < 10; i++) sum += (10 - i) * (isbn[i] === "X" ? 10 : Number(isbn[i]));
      return sum % 11 === 0;
    }
    if (/^\d{13}$/.test(isbn)) {
      let sum = 0;
      for (let i = 0; i < 13; i++) sum += Number(isbn[i]) * (i % 2 === 0 ? 1 : 3);
      return sum % 10 === 0;
    }
    return false;
  }

  function setError(form, name, message) {
    const input = form.elements[name];
    const slot = $(`[data-error-for="${name}"]`, form);
    const field = input && input.closest(".field");
    if (slot) slot.textContent = message || "";
    if (field) field.classList.toggle("has-error", Boolean(message));
    if (input) input.setAttribute("aria-invalid", message ? "true" : "false");
  }

  const LABELS = {
    title: "Title", author: "Author", isbn: "ISBN", category: "Category",
    shelf_location: "Shelf location", quantity: "Quantity",
    username: "Username", password: "Password",
  };

  function validateField(form, input) {
    const name = input.name;
    const value = input.value.trim();
    let message = "";

    if (input.required && !value) {
      message = `${LABELS[name] || "This field"} is required.`;
    } else if (input.maxLength > 0 && value.length > input.maxLength) {
      message = `Must be at most ${input.maxLength} characters.`;
    } else if (name === "isbn" && value && !isValidIsbn(normalizeIsbn(value))) {
      message = "Enter a valid ISBN-10 or ISBN-13. Check the last digit.";
    } else if (name === "publication_year" && value) {
      const year = Number(value);
      const max = Number(input.max) || new Date().getFullYear();
      if (!/^\d{4}$/.test(value)) message = "Enter a 4-digit year, e.g. 2019.";
      else if (year < 1000 || year > max) message = `Year must be between 1000 and ${max}.`;
    } else if (name === "quantity" && value) {
      if (/^-/.test(value)) message = "Quantity cannot be negative.";
      else if (!/^\d+$/.test(value)) message = "Quantity must be a whole number (0 or more).";
      else if (Number(value) > Number(input.max || 100000)) message = `Quantity cannot be more than ${input.max}.`;
    }
    setError(form, name, message);
    return !message;
  }

  $$("form[data-validate]").forEach((form) => {
    const inputs = $$("input:not([type=hidden])", form);
    inputs.forEach((input) => {
      input.addEventListener("blur", () => validateField(form, input));
      input.addEventListener("input", () => {
        if (input.closest(".field")?.classList.contains("has-error")) validateField(form, input);
      });
    });
    form.addEventListener("submit", (event) => {
      const results = inputs.map((input) => validateField(form, input));
      const isbnInput = form.elements.isbn;
      const isbnTaken = isbnInput && isbnInput.dataset.taken === "true";
      if (isbnTaken) setError(form, "isbn", "A book with this ISBN already exists in the catalogue.");
      if (results.includes(false) || isbnTaken) {
        event.preventDefault();
        const firstBad = $(".has-error input", form);
        if (firstBad) firstBad.focus();
        return;
      }
      const submit = $("button[type=submit]", form);
      if (submit) setTimeout(() => { submit.disabled = true; }, 0); // stop double submits
    });
  });

  /* ---------------- 5. Live ISBN availability check ---------------- */
  $$("form[data-book-form]").forEach((form) => {
    const input = form.elements.isbn;
    const status = $("[data-isbn-status]", form);
    if (!input || !status) return;
    const defaultHelp = status.textContent;
    let timer = null;
    let lastChecked = null;

    async function check() {
      const isbn = normalizeIsbn(input.value);
      if (isbn === lastChecked) return;
      lastChecked = isbn;
      input.dataset.taken = "false";
      status.className = "field-help";
      status.textContent = defaultHelp;
      if (!isValidIsbn(isbn)) return;
      const params = new URLSearchParams({ isbn });
      if (form.dataset.bookId) params.set("exclude", form.dataset.bookId);
      try {
        const res = await fetch(`/api/isbn-check?${params}`, { headers: { Accept: "application/json" } });
        if (!res.ok) return;
        const data = await res.json();
        if (normalizeIsbn(input.value) !== data.isbn) return; // user kept typing
        if (data.available) {
          status.className = "field-help ok";
          status.textContent = "✓ Valid ISBN and not yet in the catalogue.";
        } else {
          input.dataset.taken = "true";
          status.className = "field-help bad";
          status.textContent = "This ISBN is already registered for another book.";
        }
      } catch (_) { /* offline: the server will still check on submit */ }
    }
    input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(check, 400); });
    input.addEventListener("blur", check);
    if (input.value) check();
  });

  /* ---------------- 6. Quantity stepper + stock form ---------------- */
  $$(".stepper").forEach((stepper) => {
    const input = $("input", stepper);
    $$("[data-step]", stepper).forEach((btn) => {
      btn.addEventListener("click", () => {
        const current = parseInt(input.value, 10);
        const next = Math.max(0, (Number.isNaN(current) ? 0 : current) + Number(btn.dataset.step));
        input.value = String(next);
        input.dispatchEvent(new Event("input", { bubbles: true }));
      });
    });
  });

  $$("form[data-stock-form]").forEach((form) => {
    const current = Number(form.dataset.current);
    const input = form.elements.amount;
    form.addEventListener("submit", (event) => {
      const action = event.submitter ? event.submitter.value : "add";
      const raw = input.value.trim();
      let message = "";
      if (!/^\d+$/.test(raw)) message = raw.startsWith("-") ? "Quantities cannot be negative." : "Enter a whole number of copies.";
      else if (action !== "set" && Number(raw) < 1) message = "Enter at least 1 copy.";
      else if (action === "remove" && Number(raw) > current) message = `Only ${current} available — quantity cannot go below zero.`;
      setError(form, "amount", message);
      if (message) { event.preventDefault(); input.focus(); }
    });
  });

  /* ---------------- 7. Show / hide password ---------------- */
  $$("[data-password-toggle]").forEach((btn) => {
    const input = document.getElementById(btn.getAttribute("aria-controls"));
    if (!input) return;
    btn.addEventListener("click", () => {
      const show = input.type === "password";
      input.type = show ? "text" : "password";
      const label = show ? "Hide password" : "Show password";
      btn.setAttribute("aria-pressed", String(show));
      btn.setAttribute("aria-label", label);
      btn.title = label;
      input.focus();
      const end = input.value.length;
      input.setSelectionRange(end, end);   // keep the cursor at the end
    });
    // Always hide the password again before the form is submitted, so the
    // browser never offers to remember it as plain text in form history.
    if (input.form) input.form.addEventListener("submit", () => { input.type = "password"; });
  });

  /* ---------------- 8. Auto-submit filter dropdowns ---------------- */
  $$("[data-auto-submit]").forEach((select) => {
    select.addEventListener("change", () => select.form.submit());
  });
})();
