// Form, job lifecycle, progress, history and schedules.

import { $, api, button, el, when } from "./dom.js";
import { renderResults, showTab } from "./results.js";

const form = $("#crawl-form");
const POLL_MS = 1000;
const SELECTOR_FIELDS = ["card", "title", "price", "old_price", "link", "image"];

let jobId = null;
let timer = null;

function readForm() {
  const data = new FormData(form);
  const text = (name) => (data.get(name) || "").trim() || null;
  const number = (name) => Number(data.get(name));
  const selectors = Object.fromEntries(SELECTOR_FIELDS.map((name) => [name, text(`sel_${name}`)]));
  return {
    url: text("url"),
    depth: number("depth"),
    max_pages: number("max_pages"),
    mode: data.get("mode"),
    delay: number("delay"),
    timeout: number("timeout"),
    retries: number("retries"),
    concurrency: number("concurrency"),
    pages: text("pages"),
    page_pattern: text("page_pattern"),
    proxy: text("proxy"),
    extract_text: data.has("extract_text"),
    download_images: data.has("download_images"),
    same_domain: data.has("same_domain"),
    respect_robots: data.has("respect_robots"),
    selectors,
    repeat_hours: text("repeat_hours") ? Number(text("repeat_hours")) : null,
    keep_runs: number("keep_runs"),
  };
}

// --- theme -----------------------------------------------------------------

function applyTheme(theme) {
  document.documentElement.dataset.theme = theme;
  localStorage.setItem("theme", theme);
  $("#theme-toggle").textContent = theme === "dark" ? "Light" : "Dark";
}

applyTheme(document.documentElement.dataset.theme);
$("#theme-toggle").addEventListener("click", () => {
  applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark");
});

// --- job lifecycle ---------------------------------------------------------

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  $("#form-error").textContent = "";
  try {
    const job = await api("/api/jobs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(readForm()),
    });
    watch(job.id);
    if (job.schedule) loadSchedules();
  } catch (error) {
    $("#form-error").textContent = error.message;
  }
});

$("#cancel").addEventListener("click", () => {
  if (jobId) fetch(`/api/jobs/${jobId}/cancel`, { method: "POST" });
});

function watch(id) {
  jobId = id;
  clearInterval(timer);
  $("#progress").hidden = false;
  $("#results").hidden = true;
  $("#cancel").hidden = false;
  $("#start").disabled = true;
  timer = setInterval(poll, POLL_MS);
  poll();
}

async function poll() {
  const job = await api(`/api/jobs/${jobId}`);
  renderProgress(job);
  if (job.state === "running" || job.state === "downloading") return;
  clearInterval(timer);
  $("#cancel").hidden = true;
  $("#start").disabled = false;
  await renderResults(jobId);
  loadHistory();
}

// --- progress --------------------------------------------------------------

function renderProgress(job) {
  $("#stat-state").textContent = job.state;
  $("#stat-pages").textContent = job.pages_done;
  $("#stat-items").textContent = job.items;
  $("#stat-links").textContent = job.links;
  $("#stat-images").textContent = job.images;
  $("#stat-downloaded").textContent = job.downloaded;
  $("#recent").replaceChildren(...job.recent.map((url) => el("li", { textContent: url })));
  $("#job-error").textContent = job.error || "";
}

// --- history and schedules -------------------------------------------------

async function loadHistory() {
  const jobs = await api("/api/jobs");
  const box = $("#history");
  if (!jobs.length) {
    box.replaceChildren(el("p", { className: "empty", textContent: "No runs yet." }));
    return;
  }
  box.replaceChildren(el("table", { className: "compact" }, [
    el("thead", {}, [el("tr", {}, ["When", "URL", "State", "Items", ""].map((h) => el("th", { textContent: h })))]),
    el("tbody", {}, jobs.slice(0, 30).map((job) =>
      el("tr", { className: job.id === jobId ? "current" : "" }, [
        el("td", { textContent: when(job.created_at) }),
        el("td", { className: "url", textContent: job.start_url }),
        el("td", { textContent: job.state + (job.schedule_id ? " ⏱" : "") }),
        el("td", { className: "num", textContent: job.items ?? "" }),
        el("td", { className: "row-actions" }, [
          button("Open", () => watch(job.id), "small"),
          button("Delete", () => deleteJob(job), "small"),
        ]),
      ])
    )),
  ]));
}

async function deleteJob(job) {
  if (job.state === "running" || job.state === "downloading") return;
  await api(`/api/jobs/${job.id}`, { method: "DELETE" });
  if (job.id === jobId) {
    $("#results").hidden = true;
    $("#progress").hidden = true;
    jobId = null;
  }
  loadHistory();
}

async function loadSchedules() {
  const schedules = await api("/api/schedules");
  const box = $("#schedules");
  if (!schedules.length) {
    box.replaceChildren(el("p", { className: "empty", textContent: "No schedules. Pick a Repeat interval in the form to track a listing over time; every run can then be compared with the previous one in the Changes tab." }));
    return;
  }
  box.replaceChildren(el("table", { className: "compact" }, [
    el("thead", {}, [el("tr", {}, ["URL", "Every", "Next run", ""].map((h) => el("th", { textContent: h })))]),
    el("tbody", {}, schedules.map((schedule) =>
      el("tr", {}, [
        el("td", { className: "url", textContent: schedule.start_url }),
        el("td", { textContent: `${schedule.interval_hours} h` }),
        el("td", { textContent: when(schedule.next_run) }),
        el("td", { className: "row-actions" }, [
          button("Run now", async () => { const job = await api(`/api/schedules/${schedule.id}/run`, { method: "POST" }); watch(job.id); loadSchedules(); }, "small"),
          button("Delete", async () => { await api(`/api/schedules/${schedule.id}`, { method: "DELETE" }); loadSchedules(); }, "small"),
        ]),
      ])
    )),
  ]));
}

loadHistory();
loadSchedules();
