// Rendering of a finished run: items, changes, pages, links, images, text.

import { $, api, el, link, when } from "./dom.js";

let lastItems = { items: [], localImages: {} };

const EXPORTS = [["xlsx", "items.xlsx"], ["items-csv", "items.csv"], ["items-json", "items.json"], ["pages", "pages.json"], ["links", "links.csv"]];

export async function renderResults(jobId) {
  const [{ pages, local_images }, diff] = await Promise.all([
    api(`/api/jobs/${jobId}/pages`),
    api(`/api/jobs/${jobId}/changes`),
  ]);
  for (const [id, name] of EXPORTS) $(`#dl-${id}`).href = `/api/jobs/${jobId}/files/${name}`;
  renderItems(pages, local_images);
  $("#tab-changes").replaceChildren(changesView(diff));
  $("#tab-pages").replaceChildren(pagesTable(pages));
  $("#tab-links").replaceChildren(linkList(pages));
  $("#tab-images").replaceChildren(gallery(pages, local_images));
  $("#tab-text").replaceChildren(textBlocks(pages));
  $("#results").hidden = false;
  showTab(pages.some((page) => page.items.length) ? "items" : "pages");
}

function renderItems(pages, localImages) {
  lastItems = { items: pages.flatMap((page) => page.items.map((item) => ({ ...item, page: page.url }))), localImages };
  $("#dl-xlsx").hidden = !lastItems.items.length;
  if (!lastItems.items.length) {
    $("#items-view").replaceChildren(el("p", { className: "empty", textContent: "No repeated cards found. Listing pages (catalogues, search results) produce items; use custom selectors if detection misses them." }));
    return;
  }
  $("#items-view").replaceChildren($("#items-table").checked ? itemsTable(lastItems) : itemCards(lastItems));
}

function thumb(item, localImages) {
  return item.image ? el("img", { src: localImages[item.image] || item.image, loading: "lazy", alt: "" }) : el("div", { className: "no-image" });
}

function priceCell(item) {
  const parts = [];
  if (item.price) parts.push(el("b", { textContent: item.price }));
  if (item.old_price) parts.push(el("s", { textContent: item.old_price }));
  return parts;
}

function itemCards({ items, localImages }) {
  return el("div", { className: "cards" }, items.map((item) =>
    el("article", { className: "card" }, [
      thumb(item, localImages),
      el("h3", { textContent: item.title || "(no title)" }),
      el("div", { className: "price" }, priceCell(item)),
      item.link ? link(item.link, "Open") : el("span"),
    ])
  ));
}

function itemsTable({ items, localImages }) {
  const header = el("tr", {}, ["#", "Photo", "Title", "Price", "Old price", "Group", "Link", "Page"].map((h) => el("th", { textContent: h })));
  const rows = items.map((item, index) =>
    el("tr", {}, [
      el("td", { className: "num", textContent: index + 1 }),
      el("td", { className: "thumb" }, [thumb(item, localImages)]),
      el("td", { textContent: item.title || "" }),
      el("td", { className: "num", textContent: item.price || "" }),
      el("td", { className: "num old", textContent: item.old_price || "" }),
      el("td", { className: "num", textContent: item.group }),
      el("td", {}, item.link ? [link(item.link, "Open")] : []),
      el("td", {}, [link(item.page, new URL(item.page).pathname)]),
    ])
  );
  return el("table", { className: "items-table" }, [el("thead", {}, [header]), el("tbody", {}, rows)]);
}

$("#items-table").addEventListener("change", (event) => {
  localStorage.setItem("itemsTable", event.target.checked ? "1" : "");
  if (lastItems.items.length) {
    $("#items-view").replaceChildren(event.target.checked ? itemsTable(lastItems) : itemCards(lastItems));
  }
});
$("#items-table").checked = localStorage.getItem("itemsTable") === "1";

function changesView({ against, changes }) {
  if (!against) {
    return el("p", { className: "empty", textContent: "No previous run of this URL to compare with. Run it again later, or set Repeat to track prices over time." });
  }
  const summary = el("p", { className: "summary", textContent:
    `Compared with the run from ${when(against.created_at)}: ${changes.price_changes.length} price changes, ` +
    `${changes.added.length} new, ${changes.removed.length} gone, ${changes.unchanged} unchanged.` });
  const blocks = [summary];
  if (changes.price_changes.length) {
    const header = el("tr", {}, ["Title", "Before", "After", "Change"].map((h) => el("th", { textContent: h })));
    const rows = changes.price_changes.map((change) =>
      el("tr", {}, [
        el("td", {}, [change.link ? link(change.link, change.title || change.link) : el("span", { textContent: change.title || "" })]),
        el("td", { className: "num old", textContent: change.before || "" }),
        el("td", { className: "num", textContent: change.after || "" }),
        el("td", { className: `num ${deltaClass(change.delta_pct)}`, textContent: change.delta_pct == null ? "" : `${change.delta_pct > 0 ? "+" : ""}${change.delta_pct}%` }),
      ])
    );
    blocks.push(el("h3", { textContent: "Price changes" }), el("table", {}, [el("thead", {}, [header]), el("tbody", {}, rows)]));
  }
  for (const [title, items] of [["New items", changes.added], ["Gone items", changes.removed]]) {
    if (!items.length) continue;
    blocks.push(el("h3", { textContent: title }), el("ul", { className: "link-list" }, items.map((item) =>
      el("li", {}, [link(item.link, item.title || item.link), el("span", { className: "muted", textContent: item.price ? `  ${item.price}` : "" })])
    )));
  }
  return el("div", {}, blocks);
}

function deltaClass(delta) {
  if (delta == null || delta === 0) return "";
  return delta < 0 ? "down" : "up";
}

function pagesTable(pages) {
  const header = el("tr", {}, ["URL", "Status", "Title", "Items", "Links", "Images"].map((h) => el("th", { textContent: h })));
  const rows = pages.map((page) =>
    el("tr", {}, [
      el("td", {}, [link(page.url)]),
      el("td", { textContent: page.error ? `error: ${page.error}` : page.status }),
      el("td", { textContent: page.title }),
      el("td", { className: "num", textContent: page.items.length }),
      el("td", { className: "num", textContent: page.links.length }),
      el("td", { className: "num", textContent: page.images.length }),
    ])
  );
  return el("table", {}, [el("thead", {}, [header]), el("tbody", {}, rows)]);
}

function unique(items) {
  return [...new Set(items)];
}

function linkList(pages) {
  const links = unique(pages.flatMap((page) => page.links));
  if (!links.length) return el("p", { className: "empty", textContent: "No links found." });
  return el("ul", { className: "link-list" }, links.map((url) => el("li", {}, [link(url)])));
}

function gallery(pages, localImages) {
  const images = unique(pages.flatMap((page) => page.images));
  if (!images.length) return el("p", { className: "empty", textContent: "No images found." });
  return el("div", { className: "gallery" }, images.map((url) =>
    el("figure", {}, [
      el("img", { src: localImages[url] || url, loading: "lazy", alt: "" }),
      el("figcaption", {}, [link(url, url.split("/").pop() || url)]),
    ])
  ));
}

function textBlocks(pages) {
  const withText = pages.filter((page) => page.text);
  if (!withText.length) {
    return el("p", { className: "empty", textContent: "No text captured. Enable \"Extract text\" before crawling." });
  }
  return el("div", {}, withText.map((page) =>
    el("details", {}, [el("summary", { textContent: page.title || page.url }), el("pre", { textContent: page.text })])
  ));
}

export function showTab(name) {
  document.querySelectorAll(".tabs button").forEach((tab) => tab.classList.toggle("active", tab.dataset.tab === name));
  document.querySelectorAll(".tab").forEach((tab) => { tab.hidden = tab.id !== `tab-${name}`; });
}

document.querySelectorAll(".tabs button").forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));

