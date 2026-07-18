"use strict";

const byId = (id) => document.getElementById(id);

// Softer, less medically-definitive labels for display (the API keeps ALLOW/WARN/BLOCK).
const LABELS = { ALLOW: "Lower concern", WARN: "Use caution", BLOCK: "Ask a clinician first" };

function el(tag, opts = {}, ...children) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = opts.text; // text only, never innerHTML
  if (opts.href && /^https?:\/\//i.test(opts.href)) {
    node.href = opts.href;
    node.target = "_blank";
    node.rel = opts.rel || "noopener";
  }
  for (const child of children) if (child) node.appendChild(child);
  return node;
}

function pill(status) {
  return el("span", { class: "pill pill-" + status, text: LABELS[status] || status });
}

/* Chip inputs: tokenize entries, keep free text working for unlisted meds. */

function chipInput(inputId) {
  const input = byId(inputId);
  const box = input.parentElement;
  const values = [];

  function render() {
    box.querySelectorAll(".chip").forEach((chip) => chip.remove());
    for (const value of values) {
      const remove = el("button", { text: "×" });
      remove.type = "button";
      remove.setAttribute("aria-label", "Remove " + value);
      remove.addEventListener("click", () => {
        values.splice(values.indexOf(value), 1);
        render();
      });
      box.insertBefore(el("span", { class: "chip", text: value }, remove), input);
    }
  }

  function commit() {
    for (const part of input.value.split(",")) {
      const value = part.trim();
      if (value && !values.some((v) => v.toLowerCase() === value.toLowerCase())) {
        values.push(value);
      }
    }
    input.value = "";
    render();
  }

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" || event.key === ",") {
      event.preventDefault();
      commit();
    } else if (event.key === "Backspace" && input.value === "" && values.length) {
      values.pop();
      render();
    }
  });
  input.addEventListener("change", commit); // fires on datalist pick and on blur
  box.addEventListener("click", () => input.focus());

  return {
    getValues() {
      commit(); // sweep any residual free text so submitting without Enter still works
      return [...values];
    },
    setValues(next) {
      values.length = 0;
      values.push(...next);
      input.value = "";
      render();
    },
  };
}

function fillDatalist(id, items) {
  const list = byId(id);
  list.replaceChildren();
  for (const item of items) {
    const option = document.createElement("option");
    option.value = item;
    list.appendChild(option);
  }
}

async function loadSuggestions() {
  try {
    const res = await fetch("/api/suggestions");
    if (!res.ok) return;
    const data = await res.json();
    fillDatalist("meds-list", data.medications);
    fillDatalist("supps-list", data.supplements);
  } catch (_) {
    /* autocomplete is optional; free text always works */
  }
}

/* Results rendering */

function summaryPanel(data) {
  const allow = data.recommended.filter((r) => r.status === "ALLOW").map((r) => r.supplement);
  const warn = data.recommended.filter((r) => r.status === "WARN").map((r) => r.supplement);
  const block = data.not_recommended.map((r) => r.supplement);

  const panel = el("div", { class: "summary" }, el("h2", { text: "Summary for your profile" }));
  const line = (label, names) => {
    if (!names.length) return null;
    const p = el("p", { class: "row" });
    p.appendChild(el("span", { class: "label", text: label + " " }));
    p.appendChild(document.createTextNode(names.join(", ")));
    return p;
  };
  for (const row of [
    line("Lower concern, worth discussing:", allow),
    line("Use caution:", warn),
    line("Ask a clinician before combining:", block),
  ]) {
    if (row) panel.appendChild(row);
  }

  const reasons = new Set();
  for (const r of [...data.recommended, ...data.not_recommended]) {
    for (const w of r.warnings) reasons.add(w.message);
  }
  if (reasons.size) {
    panel.appendChild(
      el("p", {
        class: "reason",
        text: "Main flags come from possible medication interactions and additive sedation. This is educational, not a diagnosis.",
      })
    );
  }
  return panel;
}

function card(rec) {
  const head = el("div", { class: "card-head" }, el("h3", { text: rec.supplement }), pill(rec.status));
  const node = el("div", { class: "card" }, head, el("p", { text: rec.summary }));
  node.appendChild(
    el("p", {
      class: "dose",
      text: "Typical dose: " + rec.dose + (rec.timing ? " · " + rec.timing : ""),
    })
  );
  if (rec.defer_to_pro) {
    node.appendChild(
      el("p", { class: "pro", text: "⚠ Talk to a clinician or pharmacist before using this." })
    );
  }
  for (const w of rec.warnings) {
    node.appendChild(el("p", { class: "warn", text: "[" + w.severity + "] " + w.message }));
  }
  for (const e of rec.rationale) {
    const p = el("p", { class: "evidence", text: e.claim + " - " });
    p.appendChild(el("a", { href: e.source_url, text: e.source }));
    node.appendChild(p);
  }
  // Buy links are de-emphasized and marked sponsored/nofollow until safety is clear.
  if (rec.buy_link) {
    const buy = el("p", { class: "buy" });
    buy.appendChild(
      el("a", { href: rec.buy_link, text: "Find this supplement", rel: "nofollow sponsored noopener" })
    );
    node.appendChild(buy);
  }
  return node;
}

function section(title, recs) {
  const sec = el("section", { class: "results" }, el("h2", { text: title }));
  for (const r of recs) sec.appendChild(card(r));
  return sec;
}

function pharmacistQuestions() {
  // Always shown: the endpoint of every result is a professional conversation.
  const box = el("div", { class: "ask" }, el("h2", { text: "Talk to a professional" }));
  const ul = el("ul");
  [
    "Are any of these reasonable to combine with my current medications?",
    "Could any of these add to drowsiness or affect my other medicines?",
    "What dose and timing would you suggest for me specifically?",
    "Is there a non-supplement step I should try first?",
  ].forEach((q) => ul.appendChild(el("li", { text: q })));
  box.appendChild(ul);
  const connect = el("p", {
    text:
      "Pharmacist consultations are free at any pharmacy, no appointment needed. " +
      "No regular clinician? ",
  });
  connect.appendChild(
    el("a", {
      href: "https://findahealthcenter.hrsa.gov/",
      text: "Find low-cost care near you (HHS)",
    })
  );
  connect.appendChild(document.createTextNode("."));
  box.appendChild(connect);
  return box;
}

/* Copy / print report ("bring this to your pharmacist") */

function reportText(profile, data) {
  const allow = data.recommended.filter((r) => r.status === "ALLOW").map((r) => r.supplement);
  const warn = data.recommended.filter((r) => r.status === "WARN").map((r) => r.supplement);
  const block = data.not_recommended.map((r) => r.supplement);
  const lines = [
    "SleepWise check (educational, not medical advice)",
    "Generated: " + new Date().toLocaleDateString(),
    "Medications: " + (profile.meds.join(", ") || "none entered"),
    "Supplements already taken: " + (profile.current_supplements.join(", ") || "none entered"),
    "Health flags: " + (profile.conditions.join(", ") || "none"),
    "",
  ];
  if (allow.length) lines.push("Lower concern: " + allow.join(", "));
  if (warn.length) lines.push("Use caution: " + warn.join(", "));
  if (block.length) lines.push("Ask a clinician first: " + block.join(", "));
  const warnings = new Set();
  for (const r of [...data.recommended, ...data.not_recommended]) {
    for (const w of r.warnings) warnings.add(w.message);
  }
  if (warnings.size) {
    lines.push("", "Warnings:");
    for (const w of warnings) lines.push("- " + w);
  }
  lines.push("", "Bring this to your pharmacist or clinician. Details: " + location.origin);
  return lines.join("\n");
}

function actionsRow(profile, data) {
  const row = el("div", { class: "result-actions" });
  const copy = el("button", { text: "Copy summary" });
  copy.type = "button";
  copy.addEventListener("click", async () => {
    try {
      await navigator.clipboard.writeText(reportText(profile, data));
      copy.textContent = "Copied";
    } catch (_) {
      copy.textContent = "Copy failed";
    }
    setTimeout(() => (copy.textContent = "Copy summary"), 2000);
  });
  const print = el("button", { text: "Print report" });
  print.type = "button";
  print.addEventListener("click", () => window.print());
  row.append(copy, print);
  return row;
}

function printHeader(profile) {
  return el(
    "div",
    { class: "print-only" },
    el("h2", { text: "SleepWise report (educational, not medical advice)" }),
    el("p", {
      text:
        "Generated " +
        new Date().toLocaleDateString() +
        ". Bring this to your pharmacist or clinician.",
    }),
    el("p", {
      text:
        "Medications: " +
        (profile.meds.join(", ") || "none entered") +
        " | Supplements: " +
        (profile.current_supplements.join(", ") || "none") +
        " | Flags: " +
        (profile.conditions.join(", ") || "none"),
    })
  );
}

/* Form flow */

let medsChips;
let suppsChips;

async function run(event) {
  if (event) event.preventDefault();
  const status = byId("status");
  const results = byId("results");
  const button = byId("go");
  status.removeAttribute("role");

  const profile = {
    goal: "sleep",
    meds: medsChips.getValues(),
    conditions: [...document.querySelectorAll(".conds input:checked")].map((c) => c.value),
    current_supplements: suppsChips.getValues(),
  };

  button.disabled = true;
  status.textContent = "Checking…";
  results.replaceChildren();

  try {
    const res = await fetch("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(profile),
    });
    if (!res.ok) throw new Error("Request failed (" + res.status + ")");
    const data = await res.json();

    const frag = document.createDocumentFragment();
    frag.appendChild(printHeader(profile));
    frag.appendChild(summaryPanel(data));
    if (data.recommended.length) frag.appendChild(section("Worth considering", data.recommended));
    if (data.not_recommended.length)
      frag.appendChild(section("Not recommended for your profile", data.not_recommended));
    frag.appendChild(pharmacistQuestions());
    frag.appendChild(actionsRow(profile, data));
    frag.appendChild(feedbackWidget());
    results.appendChild(frag);
    status.textContent = "Results ready below.";
    const noMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    results.scrollIntoView({ behavior: noMotion ? "auto" : "smooth", block: "start" });
  } catch (err) {
    status.setAttribute("role", "alert");
    status.textContent = "Something went wrong: " + err.message + ". Please try again.";
  } finally {
    button.disabled = false;
  }
}

function feedbackWidget() {
  const box = el("div", { class: "feedback" });
  box.appendChild(el("span", { text: "Was this useful?" }));
  const opts = el("div", { class: "opts" });
  const send = async (value) => {
    box.replaceChildren(el("span", { text: "Thanks for the feedback." }));
    try {
      await fetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ useful: value }),
      });
    } catch (_) {
      /* feedback is best-effort */
    }
  };
  for (const [value, label] of [
    ["yes", "Yes"],
    ["somewhat", "Somewhat"],
    ["no", "No"],
  ]) {
    const b = el("button", { text: label });
    b.type = "button";
    b.addEventListener("click", () => send(value));
    opts.appendChild(b);
  }
  box.appendChild(opts);
  return box;
}

function tryExample() {
  medsChips.setValues(["lorazepam"]);
  suppsChips.setValues(["melatonin"]);
  document.querySelectorAll(".conds input:checked").forEach((c) => (c.checked = false));
  run();
}

medsChips = chipInput("meds");
suppsChips = chipInput("supps");
byId("form").addEventListener("submit", run);
byId("example").addEventListener("click", tryExample);
loadSuggestions();
