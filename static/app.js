"use strict";

const byId = (id) => document.getElementById(id);

// Softer, less medically-definitive labels for display (the API keeps ALLOW/WARN/BLOCK).
const LABELS = { ALLOW: "Lower concern", WARN: "Use caution", BLOCK: "Ask a clinician first" };
// Plain-language prefixes for warning lines (no raw status tokens in prose).
const WARN_PREFIX = { WARN: "Caution: ", BLOCK: "Important: " };

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

/* Scenarios.
 *
 * The checker runs fixed demonstration profiles. There is deliberately no free-text
 * entry, so the page cannot be used to get guidance about a real person's medications.
 */

function setButtonsDisabled(disabled) {
  for (const b of document.querySelectorAll(".scenario-btn")) b.disabled = disabled;
}

async function loadScenarios() {
  const grid = byId("scenarios");
  let scenarios;
  try {
    const res = await fetch("/api/scenarios");
    scenarios = (await res.json()).scenarios;
  } catch (_) {
    grid.replaceChildren(
      el("p", { class: "status-line", text: "Could not load scenarios. Please reload the page." })
    );
    return;
  }
  for (const scenario of scenarios) {
    const b = el("button", { class: "scenario-btn" });
    b.type = "button";
    b.appendChild(el("span", { class: "scenario-label", text: scenario.label }));
    b.appendChild(el("span", { class: "scenario-desc", text: scenario.description }));
    b.addEventListener("click", () => run(scenario));
    grid.appendChild(b);
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

function card(rec, hidePill) {
  const head = el("div", { class: "card-head" }, el("h3", { text: rec.supplement }));
  if (!hidePill) head.appendChild(pill(rec.status));
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
    const line = el("p", { class: "warn", text: (WARN_PREFIX[w.severity] || "") + w.message });
    // A warning we have not confirmed against its source still shows - hiding a
    // plausible caution would be less safe - but it is labelled, not dressed up as
    // substantiated.
    if (w.verified === false) {
      line.appendChild(
        el("span", {
          class: "unconfirmed",
          text: " (precautionary: not yet confirmed against a source)",
        })
      );
    }
    node.appendChild(line);
  }
  for (const e of rec.rationale) {
    const p = el("p", { class: "evidence", text: e.claim + " - " });
    p.appendChild(el("a", { href: e.source_url, text: e.source }));
    node.appendChild(p);
  }
  // Only source-confirmed evidence reaches the client, so an empty list means we have
  // nothing substantiated to say - which is stated rather than papered over.
  if (!rec.rationale.length) {
    node.appendChild(
      el("p", {
        class: "evidence",
        text:
          "No source-confirmed evidence to show for this supplement yet. Statements we " +
          "could not confirm against their cited source have been withheld pending review.",
      })
    );
  }
  // Commerce is switched off in the checker: a buying prompt does not belong next to
  // guidance that has not been clinician-reviewed.
  return node;
}

function section(title, recs, hidePill) {
  const heading = el("h2", { text: title });
  heading.tabIndex = -1; // focus target so keyboard/SR users land on the results
  const sec = el("section", { class: "results" }, heading);
  for (const r of recs) sec.appendChild(card(r, hidePill));
  return sec;
}

function noticeBanner(data) {
  const box = el("div", { class: "notice" });
  if (data.profile_status === "incomplete" && data.unrecognized_meds.length) {
    box.appendChild(
      el("p", { class: "notice-head", text: "Not recognized: " + data.unrecognized_meds.join(", ") })
    );
  }
  box.appendChild(el("p", { text: data.notice }));
  return box;
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
      "Many pharmacists can answer medication questions, though availability and any fee " +
      "vary - contact your pharmacy to confirm. No regular clinician? ",
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

/* Scenario flow */

async function run(scenario) {
  const status = byId("status");
  const results = byId("results");
  status.removeAttribute("role");

  const profile = scenario.profile;

  setButtonsDisabled(true);
  status.textContent = "Running scenario: " + scenario.label + "...";
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
    const personalized = data.profile_status === "personalized";
    if (data.notice) frag.appendChild(noticeBanner(data));
    if (personalized) {
      frag.appendChild(printHeader(profile));
      frag.appendChild(summaryPanel(data));
      if (data.recommended.length) frag.appendChild(section("Worth considering", data.recommended));
      if (data.not_recommended.length)
        frag.appendChild(section("Not recommended for your profile", data.not_recommended));
    } else {
      // Incomplete or empty profile: clearly labeled general education with no
      // personalized classification pills.
      frag.appendChild(
        section(
          "General information about sleep supplements",
          [...data.recommended, ...data.not_recommended],
          true
        )
      );
    }
    frag.appendChild(pharmacistQuestions());
    if (personalized) frag.appendChild(actionsRow(profile, data));
    frag.appendChild(feedbackWidget());
    results.appendChild(frag);
    status.textContent =
      data.profile_status === "incomplete"
        ? "Some medications were not recognized. Showing general information only."
        : data.profile_status === "general"
          ? "General overview ready below."
          : "Results ready below.";
    const noMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    results.scrollIntoView({ behavior: noMotion ? "auto" : "smooth", block: "start" });
    const firstHeading = results.querySelector("h2");
    if (firstHeading) firstHeading.focus({ preventScroll: true });
  } catch (err) {
    status.setAttribute("role", "alert");
    status.textContent = "Something went wrong: " + err.message + ". Please try again.";
  } finally {
    setButtonsDisabled(false);
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

loadScenarios();
