// Helper kecil: membuat elemen dengan aman (teks selalu lewat textContent), memanggil API, dan menampilkan galat.

export function el(tag, attrs, ...children) {
  const node = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (v === null || v === undefined || v === false) continue;
      if (k === "class") node.className = v;
      else if (k === "text") node.textContent = v;
      else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
      else if (k === "value") node.value = v;
      else if (k === "style" && typeof v === "object") Object.assign(node.style, v); // CSSOM, bukan atribut style (CSP)
      else if (v === true) node.setAttribute(k, "");
      else node.setAttribute(k, String(v));
    }
  }
  append(node, children);
  return node;
}

export function append(node, children) {
  for (const c of children.flat(Infinity)) {
    if (c === null || c === undefined || c === false) continue;
    node.append(c instanceof Node ? c : document.createTextNode(String(c)));
  }
  return node;
}

export function clear(node) {
  while (node.firstChild) node.removeChild(node.firstChild);
  return node;
}

export function svg(tag, attrs, ...children) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [k, v] of Object.entries(attrs || {})) {
    if (v === null || v === undefined) continue;
    if (k === "class") node.setAttribute("class", v);
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, String(v));
  }
  append(node, children);
  return node;
}

// Pesan galat yang bisa dibaca: dari server (JSON {error}) atau dari jaringan.
export async function api(path, { method = "GET", body } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (e) {
    throw new Error("Server Puitika tidak terjangkau. Pastikan `python app.py` masih berjalan.");
  }
  let data = null;
  try {
    data = await res.json();
  } catch (e) {
    /* bukan JSON */
  }
  if (!res.ok) throw new Error((data && data.error) || `Permintaan gagal (kode ${res.status}).`);
  return data;
}

export function qs(params) {
  const u = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) if (v !== null && v !== undefined && v !== "") u.set(k, v);
  const s = u.toString();
  return s ? "?" + s : "";
}

export const TEMA = ["romansa", "alam", "sosial", "kehidupan", "religius"];
export const EMOSI = ["sedih", "rindu", "bahagia", "harapan", "tenang", "marah"];
export const cap = (s) => (s ? s[0].toUpperCase() + s.slice(1) : s);
export const nf = new Intl.NumberFormat("id-ID");
export const fmt = (n) => (n === null || n === undefined ? "–" : nf.format(n));

export function errorBox(message) {
  return el("div", { class: "error", role: "alert" }, message);
}

export function debounce(fn, ms) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

let toastTimer;
export function toast(message) {
  document.querySelectorAll(".toast").forEach((n) => n.remove());
  const t = el("div", { class: "toast", role: "status" }, message);
  document.body.append(t);
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.remove(), 2600);
}

// Tooltip untuk grafik: satu elemen bersama, mengikuti penunjuk.
let tipNode;
export function tooltip(target, textFn) {
  const show = (e) => {
    if (!tipNode) {
      tipNode = el("div", { class: "tip", role: "tooltip" });
      document.body.append(tipNode);
    }
    tipNode.textContent = textFn();
    const x = Math.min(e.clientX + 14, window.innerWidth - 220);
    tipNode.style.left = x + "px";
    tipNode.style.top = e.clientY + 16 + "px";
    tipNode.hidden = false;
  };
  const hide = () => {
    if (tipNode) tipNode.hidden = true;
  };
  target.addEventListener("pointermove", show);
  target.addEventListener("pointerleave", hide);
  target.addEventListener("focus", (e) => {
    const r = target.getBoundingClientRect();
    show({ clientX: r.left + r.width / 2, clientY: r.top - 40 });
  });
  target.addEventListener("blur", hide);
}

// Keadaan yang dibawa antarhalaman (mis. teks dari Studio ke Makna). Hilang saat halaman dimuat ulang.
export const shared = { maknaText: "", maknaTitle: "" };

// Kartu satu kata dari Ruang Diksi (dipakai di Beranda, Ruang Diksi, Teman Diksi).
export function wordItem(w, { onPick } = {}) {
  const head = el(
    "div",
    { class: "word-head" },
    onPick ? el("button", { class: "linkbtn w", type: "button", onclick: () => onPick(w.kata) }, w.kata) : el("span", { class: "w" }, w.kata),
    w.kelas_kata ? el("span", { class: "pos" }, w.kelas_kata) : null,
    w.emosi ? el("span", { class: "tag" }, w.emosi) : null,
    typeof w.skor === "number" ? el("span", { class: "score" }, `kecocokan ${Math.round(w.skor * 100)}%`) : null
  );
  return el(
    "li",
    null,
    head,
    el("p", { class: "word-mean" }, w.makna),
    w.nuansa ? el("p", { class: "word-nuance" }, "Nuansa: " + w.nuansa) : null,
    w.contoh ? el("p", { class: "word-example" }, "“" + w.contoh + "”") : null
  );
}
