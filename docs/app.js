const CATEGORIES = ["すべて", "経済", "業界", "採用・キャリア", "時事"];
const READ_KEY = "shukatsu-times-read-v1";

function loadReadUrls() {
  try {
    const values = JSON.parse(localStorage.getItem(READ_KEY) || "[]");
    return new Set(Array.isArray(values) ? values : []);
  } catch (_) {
    return new Set();
  }
}

const state = {
  dates: [],
  currentDate: null,
  data: null,
  category: "すべて",
  readUrls: loadReadUrls(),
};

const elements = {
  date: document.querySelector("#current-date"),
  updateTime: document.querySelector("#update-time"),
  older: document.querySelector("#older-button"),
  newer: document.querySelector("#newer-button"),
  digest: document.querySelector("#daily-digest"),
  filters: document.querySelector("#category-filter"),
  articles: document.querySelector("#articles"),
  count: document.querySelector("#article-count"),
  status: document.querySelector("#status"),
};

function formatDate(value) {
  const date = new Date(`${value}T00:00:00+09:00`);
  return new Intl.DateTimeFormat("ja-JP", {
    month: "long",
    day: "numeric",
    weekday: "short",
  }).format(date);
}

function saveReadState() {
  localStorage.setItem(READ_KEY, JSON.stringify([...state.readUrls].slice(-500)));
}

function setStatus(message, kind = "") {
  elements.status.textContent = message;
  elements.status.className = `status ${kind}`.trim();
}

async function fetchJson(path) {
  const response = await fetch(path, { cache: "no-cache" });
  if (!response.ok) throw new Error(`データを取得できませんでした（${response.status}）`);
  return response.json();
}

function createElement(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function renderFilters() {
  elements.filters.replaceChildren();
  for (const category of CATEGORIES) {
    const button = createElement("button", "chip", category);
    button.type = "button";
    button.dataset.category = category;
    button.setAttribute("aria-pressed", String(state.category === category));
    if (state.category === category) button.classList.add("active");
    button.addEventListener("click", () => {
      state.category = category;
      renderFilters();
      renderArticles();
    });
    elements.filters.append(button);
  }
}

function toggleRead(url, card) {
  if (state.readUrls.has(url)) {
    state.readUrls.delete(url);
    card.classList.remove("read");
    card.setAttribute("aria-pressed", "false");
  } else {
    state.readUrls.add(url);
    card.classList.add("read");
    card.setAttribute("aria-pressed", "true");
  }
  saveReadState();
}

function renderArticles() {
  const allArticles = Array.isArray(state.data?.articles) ? state.data.articles : [];
  const articles = state.category === "すべて"
    ? allArticles
    : allArticles.filter((article) => article.category === state.category);
  elements.articles.replaceChildren();
  elements.count.textContent = `${articles.length}件`;

  if (!articles.length) {
    const empty = createElement("div", "empty-state");
    empty.append(
      createElement("strong", "", state.category === "すべて" ? "本日の対象記事はありません" : "このカテゴリの記事はありません"),
      createElement("p", "", "別の日付やカテゴリも確認してみてください。"),
    );
    elements.articles.append(empty);
    return;
  }

  for (const article of articles) {
    const card = createElement("article", "news-card");
    card.tabIndex = 0;
    card.setAttribute("role", "button");
    card.setAttribute("aria-label", `${article.title}を既読にする`);
    card.setAttribute("aria-pressed", String(state.readUrls.has(article.url)));
    if (state.readUrls.has(article.url)) card.classList.add("read");

    const meta = createElement("div", "card-meta");
    meta.append(createElement("span", `category category-${article.category}`, article.category));
    meta.append(createElement("span", "source", article.source));

    const title = createElement("h3", "", article.title);
    const summary = createElement("p", "summary", article.summary);
    const point = createElement("div", "point");
    point.append(createElement("span", "point-label", "就活生ポイント"));
    point.append(createElement("p", "", article.why_important));

    const link = createElement("a", "source-link", "出典を読む ↗");
    link.href = article.url;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    link.addEventListener("click", (event) => event.stopPropagation());

    card.append(meta, title, summary, point, link);
    card.addEventListener("click", () => toggleRead(article.url, card));
    card.addEventListener("keydown", (event) => {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        toggleRead(article.url, card);
      }
    });
    elements.articles.append(card);
  }
}

function renderPage() {
  elements.date.textContent = formatDate(state.data.date);
  elements.date.dateTime = state.data.date;
  const generated = new Date(state.data.generated_at);
  elements.updateTime.textContent = Number.isNaN(generated.getTime())
    ? ""
    : `${generated.toLocaleTimeString("ja-JP", { hour: "2-digit", minute: "2-digit" })} 更新`;

  const lines = Array.isArray(state.data.daily_digest)
    ? state.data.daily_digest
    : String(state.data.daily_digest || "").split("\n");
  elements.digest.replaceChildren(...lines.filter(Boolean).map((line) => createElement("li", "", line)));
  renderArticles();
  updateNavigation();
}

function updateNavigation() {
  const index = state.dates.indexOf(state.currentDate);
  elements.older.disabled = index < 0 || index >= state.dates.length - 1;
  elements.newer.disabled = index <= 0;
}

async function loadDate(date) {
  setStatus("ニュースを読み込んでいます…");
  try {
    const path = date ? `./data/news-${date}.json` : "./data/latest.json";
    state.data = await fetchJson(path);
    state.currentDate = state.data.date;
    history.replaceState(null, "", `#${state.currentDate}`);
    renderPage();
    setStatus("");
  } catch (error) {
    setStatus(`${error.message}。通信環境を確認して再読み込みしてください。`, "error");
  }
}

async function initialize() {
  renderFilters();
  try {
    const indexData = await fetchJson("./data/index.json");
    state.dates = Array.isArray(indexData) ? indexData : indexData.dates || [];
  } catch (error) {
    state.dates = [];
  }

  const requested = location.hash.slice(1);
  await loadDate(state.dates.includes(requested) ? requested : null);
  if (!state.dates.includes(state.currentDate)) state.dates.unshift(state.currentDate);
  updateNavigation();
}

elements.older.addEventListener("click", () => {
  const index = state.dates.indexOf(state.currentDate);
  if (index >= 0 && index < state.dates.length - 1) loadDate(state.dates[index + 1]);
});

elements.newer.addEventListener("click", () => {
  const index = state.dates.indexOf(state.currentDate);
  if (index > 0) loadDate(state.dates[index - 1]);
});

window.addEventListener("hashchange", () => {
  const date = location.hash.slice(1);
  if (state.dates.includes(date) && date !== state.currentDate) loadDate(date);
});

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => navigator.serviceWorker.register("./sw.js"));
}

initialize();
