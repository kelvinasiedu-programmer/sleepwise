"use strict";

/* Symptom organizer.
 *
 * Answers live only in this variable for the life of the tab. Nothing is written to
 * localStorage, sessionStorage, or a cookie, and nothing is sent anywhere until the
 * user finishes the deck.
 */

const byId = (id) => document.getElementById(id);
const stage = () => byId("stage");

let cards = [];
let index = 0;
const answers = {};

function el(tag, opts = {}, ...children) {
  const node = document.createElement(tag);
  if (opts.class) node.className = opts.class;
  if (opts.text != null) node.textContent = opts.text; // text only, never innerHTML
  for (const child of children) if (child) node.appendChild(child);
  return node;
}

/* Deck */

function answer(value) {
  const card = cards[index];
  if (!card) return;
  answers[card.id] = value;
  index += 1;
  if (index >= cards.length) {
    submit();
  } else {
    renderCard();
  }
}

function back() {
  if (index === 0) return;
  index -= 1;
  delete answers[cards[index].id];
  renderCard();
}

function renderCard() {
  const card = cards[index];
  const wrap = el("div", { class: "deck" });

  const progress = el("p", {
    class: "deck-progress",
    text: `Card ${index + 1} of ${cards.length} · ${card.group}`,
  });
  wrap.appendChild(progress);

  const face = el("div", { class: "deck-card" }, el("p", { class: "deck-prompt", text: card.prompt }));
  wrap.appendChild(face);

  const row = el("div", { class: "deck-actions" });
  const buttons = [
    ["not_applies", "Doesn't apply", "btn-secondary"],
    ["unsure", "Not sure", "btn-secondary"],
    ["applies", "Applies to me", "btn-primary"],
  ];
  for (const [value, label, cls] of buttons) {
    const b = el("button", { class: "btn " + cls, text: label });
    b.type = "button";
    b.addEventListener("click", () => answer(value));
    row.appendChild(b);
  }
  wrap.appendChild(row);

  const hint = el("p", {
    class: "deck-hint",
    text: "Swipe right for applies, left for doesn't apply. Or use the arrow keys: left, right, down for not sure.",
  });
  wrap.appendChild(hint);

  if (index > 0) {
    const b = el("button", { class: "btn-link", text: "Back to previous card" });
    b.type = "button";
    b.addEventListener("click", back);
    wrap.appendChild(b);
  }

  stage().replaceChildren(wrap);
  attachSwipe(face);
  // Move focus to the prompt so screen-reader and keyboard users land on the new card.
  face.tabIndex = -1;
  face.focus({ preventScroll: true });
}

/* Swipe, with a click fallback that is already covered by the buttons above. */

function attachSwipe(node) {
  let startX = null;
  node.addEventListener(
    "touchstart",
    (e) => {
      startX = e.changedTouches[0].clientX;
    },
    { passive: true }
  );
  node.addEventListener(
    "touchend",
    (e) => {
      if (startX === null) return;
      const dx = e.changedTouches[0].clientX - startX;
      startX = null;
      if (Math.abs(dx) < 60) return;
      answer(dx > 0 ? "applies" : "not_applies");
    },
    { passive: true }
  );
}

function onKey(event) {
  if (!cards.length || index >= cards.length) return;
  if (event.key === "ArrowRight") answer("applies");
  else if (event.key === "ArrowLeft") answer("not_applies");
  else if (event.key === "ArrowDown") answer("unsure");
}

/* Results */

function list(className, items) {
  const ul = el("ul", { class: className });
  for (const item of items) ul.appendChild(el("li", { text: item }));
  return ul;
}

function renderResults(data) {
  const frag = document.createDocumentFragment();

  const heading = el("h2", { text: "What you selected" });
  heading.tabIndex = -1;
  frag.appendChild(heading);
  frag.appendChild(el("p", { class: "muted-note", text: data.intro }));

  // Escalation first, before anything that could read as reassurance.
  for (const flag of data.red_flags) {
    const box = el("div", { class: "redflag redflag-" + flag.urgency });
    box.appendChild(
      el("p", {
        class: "redflag-head",
        text: flag.urgency === "urgent" ? "Please act on this first" : "Worth raising soon",
      })
    );
    box.appendChild(el("p", { text: flag.message }));
    frag.appendChild(box);
  }

  if (data.selected.length) {
    frag.appendChild(el("h3", { text: "Applies to me" }));
    frag.appendChild(list("summary-list", data.selected));
  }
  if (data.unsure.length) {
    frag.appendChild(el("h3", { text: "Not sure" }));
    frag.appendChild(list("summary-list", data.unsure));
  }

  if (data.notice) {
    frag.appendChild(el("div", { class: "notice" }, el("p", { text: data.notice })));
  }

  if (data.topics.length) {
    frag.appendChild(el("h2", { text: "Possible topics to discuss with a clinician" }));
    frag.appendChild(
      el("p", {
        class: "muted-note",
        text: "Listed in no particular order. These are topics to raise, not conclusions.",
      })
    );
    for (const topic of data.topics) {
      const card = el("div", { class: "card" }, el("h3", { text: topic.topic }));
      card.appendChild(el("p", { text: topic.summary }));
      card.appendChild(el("p", { class: "dose", text: "Why this appeared:" }));
      card.appendChild(list("evidence-list", topic.because));
      card.appendChild(el("p", { class: "dose", text: "Questions to bring to an appointment:" }));
      card.appendChild(list("evidence-list", topic.discuss));
      frag.appendChild(card);
    }
  }

  frag.appendChild(el("p", { class: "muted-note", text: data.closing }));

  const actions = el("div", { class: "result-actions" });
  const printBtn = el("button", { class: "btn btn-secondary", text: "Print or save summary" });
  printBtn.type = "button";
  printBtn.addEventListener("click", () => window.print());
  actions.appendChild(printBtn);

  const again = el("button", { class: "btn btn-secondary", text: "Start over" });
  again.type = "button";
  again.addEventListener("click", () => {
    for (const key of Object.keys(answers)) delete answers[key];
    index = 0;
    renderCard();
  });
  actions.appendChild(again);
  frag.appendChild(actions);

  stage().replaceChildren(frag);
  heading.focus({ preventScroll: true });
}

async function submit() {
  stage().replaceChildren(el("p", { class: "status-line", text: "Organizing your answers..." }));
  try {
    const res = await fetch("/symptoms", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ answers }),
    });
    if (!res.ok) throw new Error("Request failed (" + res.status + ")");
    renderResults(await res.json());
  } catch (err) {
    const p = el("p", { class: "status-line", text: "Something went wrong: " + err.message + "." });
    p.setAttribute("role", "alert");
    stage().replaceChildren(p);
  }
}

async function start() {
  try {
    const res = await fetch("/api/symptom-cards");
    const data = await res.json();
    cards = data.cards;
    index = 0;
    renderCard();
  } catch (_) {
    stage().replaceChildren(
      el("p", { class: "status-line", text: "Could not load the cards. Please reload the page." })
    );
  }
}

byId("start").addEventListener("click", start);
document.addEventListener("keydown", onKey);
