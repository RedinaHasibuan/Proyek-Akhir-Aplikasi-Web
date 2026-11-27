import { api, clear, el, errorBox, cap, shared } from "../ui.js";
import { barList, diverging } from "../charts.js";

export async function render(root, args, alive) {
  const out = el("div", { "aria-live": "polite" });
  const head = el("header", { class: "page-head" }, el("span", { class: "eyebrow" }, "ANALISIS TEKS · EKSPLORASI MAKNA"), el("h1", null, "Makna Puisi"),
    el("p", null, "Kata penting, frasa kiasan, dan kecenderungan suasana dari sebuah puisi."));
  const warn = el("p", { class: "notice warn" }, "Ini analisis berbasis aturan dan daftar kata, bukan pemahaman makna. Penanda kiasan bisa meleset, dan skor suasana belum diuji terhadap penilaian pembaca. Pakai sebagai bahan berpikir, bukan sebagai tafsir.");

  if (args[0] === "puisi" && args[1]) {
    root.append(el("a", { class: "back", href: "#/perpustakaan/" + encodeURIComponent(args[1]) }, "Kembali ke puisi"), head, warn, out);
    out.append(el("p", { class: "loading" }, "Menganalisis…"));
    try {
      const r = await api("/api/poems/" + encodeURIComponent(args[1]) + "/makna");
      if (!alive()) return;
      clear(out).append(el("h2", { style: { marginBottom: "1.5rem" } }, r.title), result(r));
    } catch (e) {
      clear(out).append(errorBox(e.message));
    }
    return;
  }

  const text = el("textarea", { id: "m-in", maxlength: 20000, placeholder: "Tempel puisimu atau puisi lain di sini…", "aria-label": "Teks puisi" });
  text.value = shared.maknaText || "";
  const btn = el("button", { class: "btn", type: "submit" }, "Analisis puisi");
  async function run() {
    if (!text.value.trim()) return clear(out).append(el("p", { class: "empty" }, "Tempel dulu teks puisinya."));
    btn.disabled = true;
    clear(out).append(el("p", { class: "loading" }, "Menganalisis…"));
    try {
      const r = await api("/api/makna", { method: "POST", body: { text: text.value } });
      clear(out).append(result(r));
    } catch (e) {
      clear(out).append(errorBox(e.message));
    } finally {
      btn.disabled = false;
    }
  }
  root.append(head, warn,
    el("form", { class: "makna-in", onsubmit: (e) => { e.preventDefault(); shared.maknaText = text.value; run(); } },
      el("label", { class: "field", for: "m-in" }, el("span", null, shared.maknaTitle ? `Teks dari Studio: ${shared.maknaTitle}` : "Teks puisi"), text), el("div", null, btn)),
    out);
  if (text.value.trim()) run();
}

function result(r) {
  const sen = r.sentimen, dp = r.diksi_penting || {}, tema = r.tema;
  // API dapat mengirim null untuk bagian kamus bila tabel kamus belum tersedia.
  const kataMenonjol = Array.isArray(dp.kata_menonjol) ? dp.kata_menonjol : [];
  const kataKamus = Array.isArray(dp.kata_kamus) ? dp.kata_kamus : [];
  const sections = [];

  sections.push(el("p", { class: "summary" }, r.ringkasan));

  if (r.baris_kunci && r.baris_kunci.teks) {
    sections.push(el("blockquote", { class: "keyline" }, r.baris_kunci.teks, el("small", null, `Baris ${r.baris_kunci.baris}: baris dengan paling banyak kata yang menonjol di puisi ini`)));
  }

  // diksi penting
  const dk = [];
  if (kataMenonjol.length) {
    dk.push(el("p", { class: "chart-note" }, "Kata yang menonjol di puisi ini dibanding korpus Perpustakaan (sering di sini, jarang di tempat lain). Panjang batang = bobot kemenonjolan."),
      barList(kataMenonjol.map((k) => ({ label: k.kata, value: k.bobot, hint: `muncul ${k.jumlah}× di puisi ini` })), { format: (v) => v.toFixed(2) }));
  }
  if (kataKamus.length) {
    dk.push(el("h3", { style: { margin: "1.5rem 0 0.4rem" } }, "Kata yang ada di kamus Ruang Diksi"),
      el("ul", { class: "figlist" }, kataKamus.map((k) => el("li", null, el("a", { href: "#/diksi/kamus/" + encodeURIComponent(k.kata), class: "phrase" }, k.kata), el("div", { class: "why" }, k.makna + (k.nuansa ? " — " + k.nuansa : ""))))));
  }
  sections.push(el("section", { class: "block" }, el("h2", null, "Diksi penting"), dk.length ? dk : el("p", { class: "empty" }, "Belum ada kata yang menonjol.")));

  // frasa kiasan
  sections.push(el("section", { class: "block" }, el("h2", null, "Frasa kiasan yang terdeteksi"),
    r.frasa_kiasan.length
      ? el("ul", { class: "figlist" }, r.frasa_kiasan.map((f) => el("li", null,
          el("div", { class: "phrase" }, "“" + f.frasa + "”"),
          el("div", { class: "why" }, `${cap(f.jenis)} · baris ${f.baris} · penanda “${f.penanda}” · keyakinan ${f.keyakinan}`))))
      : el("p", { class: "empty" }, "Tidak ada penanda perumpamaan atau kiasan yang dikenali. Itu tidak berarti puisinya tanpa kiasan: pendeteksi ini hanya mengenali pola sederhana (seperti, bagai, “A adalah B”).")));

  // sentimen
  const sb = [];
  sb.push(el("p", null, sen.label === "tidak cukup sinyal" ? "Daftar kata tidak menangkap cukup banyak kata bermuatan di puisi ini, jadi tidak ada kesimpulan suasana."
    : `Secara keseluruhan ${sen.label} (skor ${sen.skor > 0 ? "+" : ""}${sen.skor}; ${sen.kata_positif} kata positif, ${sen.kata_negatif} kata negatif).`));
  if (sen.per_bait && sen.per_bait.length > 1) {
    sb.push(diverging(sen.per_bait.map((b) => ({ label: "Bait " + b.bait, value: b.skor, hint: `Bait ${b.bait}: ${b.label} (${b.positif} positif, ${b.negatif} negatif)` }))));
  }
  const ev = [...sen.bukti_positif.map((w) => ["+", w]), ...sen.bukti_negatif.map((w) => ["−", w])];
  if (ev.length) sb.push(el("div", { class: "chips", style: { marginTop: "0.75rem" } }, ev.map(([s, w]) => el("span", { class: "chip static" }, `${s} ${w}`))));
  sb.push(el("p", { class: "notice", style: { marginTop: "1rem" } }, sen.catatan));
  sections.push(el("section", { class: "block" }, el("h2", null, "Kecenderungan suasana"), sb));

  // tema
  sections.push(el("section", { class: "block" }, el("h2", null, "Saran tema"),
    tema && tema.kandidat.length
      ? [tema.yakin ? null : el("p", { class: "muted" }, "Model belum yakin; anggap ini petunjuk kasar."), barList(tema.kandidat.map((k) => ({ label: cap(k.label), value: Math.round(k.prob * 100) })), { format: (v) => v + "%" })]
      : el("p", { class: "empty" }, "Model tema belum dilatih, jadi belum ada saran.")));

  sections.push(el("p", { class: "notice" }, r.catatan));
  return el("div", { class: "makna-out" }, sections);
}
