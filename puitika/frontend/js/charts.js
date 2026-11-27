// Grafik tanpa pustaka: batang HTML (mudah diakses), kolom/garis SVG, dan tabel pengganti.
// Satu warna (--accent) karena palet cokelat-tanah tidak lolos validasi sebagai palet kategorikal
// (lihat catatan di README): identitas dibawa oleh label, bukan oleh warna.
import { el, svg, fmt, tooltip, clear } from "./ui.js";

export function barList(rows, { format = fmt, muted = [] } = {}) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  return el("div", { class: "bars", role: "list" }, rows.map((r) => {
    const fill = el("span", { class: "fill", style: { width: (100 * r.value) / max + "%" } });
    const row = el("div", { class: "bar-row" + (muted.includes(r.label) ? " muted-row" : ""), role: "listitem", tabindex: "0" },
      el("span", { class: "lab", title: r.label }, r.label), el("span", { class: "track" }, fill), el("span", { class: "val" }, format(r.value)));
    tooltip(row, () => `${r.label}: ${format(r.value)}${r.hint ? " · " + r.hint : ""}`);
    return row;
  }));
}

export function histogram(rows, { height = 190 } = {}) {
  const W = 440, padL = 34, padB = 28, padT = 10, H = height;
  const max = Math.max(1, ...rows.map((r) => r.value));
  const top = niceMax(max);
  const bw = (W - padL) / rows.length;
  const g = svg("svg", { class: "svgchart", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Histogram" });
  for (const t of [0, 0.5, 1]) {
    const y = padT + (H - padT - padB) * (1 - t);
    g.append(svg("line", { class: "grid", x1: padL, x2: W, y1: y, y2: y }), svg("text", { x: padL - 6, y: y + 4, "text-anchor": "end" }, fmt(Math.round(top * t))));
  }
  rows.forEach((r, i) => {
    const h = ((H - padT - padB) * r.value) / top;
    const x = padL + i * bw + 1;
    const rect = svg("rect", { class: "col", x, y: H - padB - h, width: Math.max(2, bw - 2), height: Math.max(h, 0), rx: 2, tabindex: "0" });
    tooltip(rect, () => `${r.label}: ${fmt(r.value)}`);
    g.append(rect, svg("text", { x: x + (bw - 2) / 2, y: H - 10, "text-anchor": "middle" }, r.label));
  });
  return g;
}

export function lineChart(points, { highlight, xTitle = "", yDigits = 2 } = {}) {
  const W = 440, H = 180, padL = 40, padB = 30, padT = 12, padR = 14;
  const xs = points.map((p) => p.x), ys = points.map((p) => p.y);
  const lo = Math.min(...ys), hi = Math.max(...ys), span = hi - lo || 0.1;
  const y0 = lo - span * 0.15, y1 = hi + span * 0.15;
  const X = (x) => padL + ((x - xs[0]) / (xs[xs.length - 1] - xs[0] || 1)) * (W - padL - padR);
  const Y = (y) => padT + (H - padT - padB) * (1 - (y - y0) / (y1 - y0));
  const g = svg("svg", { class: "svgchart", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Grafik garis" });
  for (const v of [y0 + (y1 - y0) * 0.05, (y0 + y1) / 2, y1 - (y1 - y0) * 0.05]) {
    g.append(svg("line", { class: "grid", x1: padL, x2: W - padR, y1: Y(v), y2: Y(v) }), svg("text", { x: padL - 6, y: Y(v) + 4, "text-anchor": "end" }, v.toFixed(yDigits)));
  }
  g.append(svg("polyline", { class: "ln", points: points.map((p) => `${X(p.x)},${Y(p.y)}`).join(" ") }));
  for (const p of points) {
    const c = svg("circle", { class: "pt", cx: X(p.x), cy: Y(p.y), r: p.x === highlight ? 6 : 4.5, tabindex: "0" });
    tooltip(c, () => `${xTitle} ${p.x}: ${p.y.toFixed(3)}`);
    g.append(c, svg("text", { x: X(p.x), y: H - 10, "text-anchor": "middle" }, String(p.x)));
  }
  return g;
}

// Batang dua arah dari nol: kanan = positif, kiri = negatif, dengan tanda + / − tertulis. Satu warna: pasangan sage/tembaga
// dari palet tidak lolos validasi keterbedaan (ΔE normal 8,6 < 15), jadi arah dan tanda yang membawa makna.
export function diverging(rows, { min = -1, max = 1 } = {}) {
  const W = 440, rowH = 30, padL = 116, padR = 56, H = rows.length * rowH + 22;
  const zero = padL + ((0 - min) / (max - min)) * (W - padL - padR);
  const S = (v) => (v / (max - min)) * (W - padL - padR);
  const g = svg("svg", { class: "svgchart", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": "Skor suasana per bait" });
  g.append(svg("line", { class: "zero", x1: zero, x2: zero, y1: 0, y2: rows.length * rowH + 4 }));
  rows.forEach((r, i) => {
    const y = i * rowH + 6;
    g.append(svg("text", { x: 0, y: y + 12 }, r.label));
    if (r.value === null || r.value === undefined) {
      g.append(svg("text", { x: zero + 8, y: y + 12 }, "tidak cukup sinyal"));
      return;
    }
    const w = Math.abs(S(r.value));
    const rect = svg("rect", { class: r.value >= 0 ? "pos" : "neg", x: r.value >= 0 ? zero : zero - w, y, width: Math.max(w, 2), height: 14, rx: 3, tabindex: "0" });
    tooltip(rect, () => r.hint || `${r.label}: ${r.value}`);
    g.append(rect, svg("text", { x: r.value >= 0 ? zero + w + 6 : zero - w - 6, y: y + 12, "text-anchor": r.value >= 0 ? "start" : "end" }, (r.value > 0 ? "+" : r.value < 0 ? "−" : "") + Math.abs(r.value).toFixed(2)));
  });
  g.append(svg("text", { x: padL, y: H - 4 }, "← negatif"), svg("text", { x: W - padR, y: H - 4, "text-anchor": "end" }, "positif →"));
  return g;
}

export function dataTable(cols, rows) {
  return el("table", { class: "dtable" },
    el("thead", null, el("tr", null, cols.map((c, i) => el("th", { class: i ? "num" : "", scope: "col" }, c)))),
    el("tbody", null, rows.map((r) => el("tr", null, r.map((v, i) => el("td", { class: i ? "num" : "" }, typeof v === "number" ? fmt(v) : v))))));
}

// Pembungkus: judul, catatan, grafik, dan tombol untuk beralih ke tabel yang sama.
export function chartCard({ title, note, chart, cols, rows, wide }) {
  const holder = el("div", null, chart);
  let showTable = false;
  const btn = el("button", { class: "linkbtn small ui", type: "button", "aria-pressed": "false", onclick: () => {
    showTable = !showTable;
    btn.setAttribute("aria-pressed", String(showTable));
    btn.textContent = showTable ? "Lihat grafik" : "Lihat tabel";
    clear(holder).append(showTable ? dataTable(cols, rows) : chart);
  } }, "Lihat tabel");
  return el("section", { class: "chart" + (wide ? " wide" : "") }, el("div", { class: "chart-head" }, el("h2", null, title), cols ? btn : null), note ? el("p", { class: "chart-note" }, note) : null, holder);
}

function niceMax(v) {
  const p = Math.pow(10, Math.floor(Math.log10(v)));
  const n = v / p;
  return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * p;
}
