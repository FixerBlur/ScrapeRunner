// Small DOM and API helpers shared by the other modules.

export const $ = (selector) => document.querySelector(selector);

export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  Object.assign(node, props);
  node.append(...children);
  return node;
}

export function link(href, text = href) {
  return el("a", { href, textContent: text, target: "_blank", rel: "noopener" });
}

export function button(text, onClick, className = "") {
  return el("button", { type: "button", textContent: text, className, onclick: onClick });
}

export function when(timestamp) {
  return timestamp ? new Date(timestamp * 1000).toLocaleString() : "";
}

export async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(await describeError(response));
  return response.json();
}

async function describeError(response) {
  try {
    const body = await response.json();
    return typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}
