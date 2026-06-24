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
  panel.appendChild(line("Lower concern, worth discussing:", allow));
  panel.appendChild(line("Use caution:", warn));
  panel.appendChild(line("Ask a clinician before combining:", block));

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

function pharmacistQuestions(data) {
  const hasFlags =
    data.not_recommended.length ||
    data.recommended.some((r) => r.status === "WARN" || r.defer_to_pro);
  if (!hasFlags) return null;
  const box = el("div", { class: "ask" }, el("h2", { text: "Questions to ask your pharmacist" }));
  const ul = el("ul");
  [
    "Are any of these safe to combine with my current medications?",
    "Could any of these add to drowsiness or affect my other medicines?",
    "What dose and timing would you suggest for me specifically?",
    "Is there a non-supplement step I should try first?",
  ].forEach((q) => ul.appendChild(el("li", { text: q })));
  box.appendChild(ul);
  return box;
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

async function run(event) {
  if (event) event.preventDefault();
  const status = byId("status");
  const results = byId("results");
  const button = byId("go");
  status.removeAttribute("role");

  const meds = byId("meds").value.split(",").map((s) => s.trim()).filter(Boolean);
  const current_supplements = byId("supps").value.split(",").map((s) => s.trim()).filter(Boolean);
  const conditions = [...document.querySelectorAll(".conds input:checked")].map((c) => c.value);

  button.disabled = true;
  status.textContent = "Checking…";
  results.replaceChildren();

  try {
    const res = await fetch("/recommend", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ goal: "sleep", meds, conditions, current_supplements }),
    });
    if (!res.ok) throw new Error("Request failed (" + res.status + ")");
    const data = await res.json();

    const frag = document.createDocumentFragment();
    frag.appendChild(summaryPanel(data));
    if (data.recommended.length) frag.appendChild(section("Worth considering", data.recommended));
    if (data.not_recommended.length)
      frag.appendChild(section("Not recommended for your profile", data.not_recommended));
    const ask = pharmacistQuestions(data);
    if (ask) frag.appendChild(ask);
    frag.appendChild(feedbackWidget());
    results.appendChild(frag);
    status.textContent = "";
    results.scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (err) {
    status.setAttribute("role", "alert");
    status.textContent = "Something went wrong: " + err.message + ". Please try again.";
  } finally {
    button.disabled = false;
  }
}

function tryExample() {
  byId("meds").value = "lorazepam";
  byId("supps").value = "melatonin";
  document.querySelectorAll(".conds input:checked").forEach((c) => (c.checked = false));
  run();
}

byId("form").addEventListener("submit", run);
byId("example").addEventListener("click", tryExample);
