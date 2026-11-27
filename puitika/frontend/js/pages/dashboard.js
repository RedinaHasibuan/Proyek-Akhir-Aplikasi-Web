import { api, clear, el, errorBox, fmt, cap } from "../ui.js";
import { barList, histogram, lineChart, chartCard } from "../charts.js";

let wantK = ""; // kosong = otomatis

export async function render(root, args, alive) {
  root.append(
    pageHead(),
    el("p", { class: "loading" }, "Menyusun statistik korpus…")
  );
  let d;
  try {
    d = await api("/api/dashboard" + (wantK ? "?k=" + wantK : ""));
  } catch (e) {
    if (!alive()) return;
    clear(root).append(pageHead(), errorBox(e.message));
    return;
  }
  if (!alive()) return;

  const k = d.korpus;
  clear(root);
  root.append(pageHead());

  if (!k.n_puisi) {
    root.append(el("div", { class: "empty-card" },
      el("span", { class: "empty-mark" }, "▦"),
      el("h2", null, "Korpus belum memiliki puisi publik."),
      el("p", null, "Jalankan proses pemuatan dataset ke database terlebih dahulu.")
    ));
    return;
  }

  root.append(
    el("section", { class: "stats-grid" },
      metric("Jumlah puisi", fmt(k.n_puisi), "koleksi publik", "01"),
      metric("Penyair", fmt(k.n_penyair), `${fmt(k.n_tanpa_penyair)} tanpa nama penyair`, "02"),
      metric("Total kata", fmt(k.total_kata), "di seluruh korpus publik", "03"),
      metric("Rata-rata panjang", fmt(k.kata_per_puisi.rata_rata), "kata per puisi", "04")
    ),
    el("div", { class: "dash-intro" },
      el("p", null,
        "Korpus memuat ",
        el("strong", null, `${fmt(k.n_puisi)} puisi`),
        " dari ",
        el("strong", null, `${fmt(k.n_penyair)} penyair`),
        ". Median panjang puisi adalah ",
        el("strong", null, `${fmt(k.kata_per_puisi.median)} kata`),
        "."
      ),
      el("p", { class: "notice" }, d.catatan)
    )
  );

  const charts = el("div", { class: "charts" });
  root.append(charts);

  const temaRows = d.tema.distribusi.map((t) => ({ label: cap(t.label), value: t.count }));
  charts.append(chartCard({
    title: "Sebaran tema puisi",
    note: d.tema.belum_berlabel ? `${fmt(d.tema.belum_berlabel)} puisi belum diberi tema.` : "Jumlah puisi berdasarkan tema yang tersimpan.",
    chart: barList(temaRows),
    cols: ["Tema", "Jumlah puisi"],
    rows: temaRows.map((r) => [r.label, r.value]),
  }));

  const per = d.periode.distribusi.map((p) => ({ label: p.label, value: p.count }));
  charts.append(chartCard({
    title: "Periode penyair",
    note: d.periode.tanpa_periode ? `${fmt(d.periode.tanpa_periode)} puisi belum memiliki periode penyair.` : "Jumlah puisi berdasarkan periode penyair.",
    chart: per.length ? barList(per) : el("p", { class: "empty" }, "Belum ada periode yang diisi."),
    cols: ["Periode", "Jumlah puisi"],
    rows: per.map((r) => [r.label, r.value]),
  }));

  const hist = k.sebaran_panjang.map((h) => ({ label: h.rentang, value: h.jumlah }));
  charts.append(chartCard({
    title: "Panjang puisi",
    note: "Sebaran jumlah kata pada setiap puisi.",
    chart: histogram(hist),
    cols: ["Rentang kata", "Jumlah puisi"],
    rows: hist.map((r) => [r.label, r.value]),
  }));

  const poets = d.penyair_teratas.map((p) => ({ label: p.name, value: p.poem_count }));
  charts.append(chartCard({
    title: "Penyair paling produktif",
    note: "Sepuluh penyair dengan jumlah puisi publik terbanyak.",
    chart: barList(poets),
    cols: ["Penyair", "Jumlah puisi"],
    rows: poets.map((r) => [r.label, r.value]),
  }));

  const words = d.frekuensi_kata.slice(0, 20).map((w) => ({
    label: w.kata, value: w.jumlah, hint: `muncul di ${fmt(w.jumlah_puisi)} puisi`,
  }));
  charts.append(chartCard({
    title: "Kata yang sering muncul",
    note: "Frekuensi setelah kata umum dibuang melalui praproses korpus.",
    wide: true,
    chart: barList(words),
    cols: ["Kata", "Jumlah kemunculan", "Jumlah puisi"],
    rows: d.frekuensi_kata.slice(0, 20).map((w) => [w.kata, w.jumlah, w.jumlah_puisi]),
  }));

  charts.append(clusterSection(d.clustering, root));
}

function pageHead() {
  return el("header", { class: "page-head" },
    el("span", { class: "eyebrow" }, "PETA KORPUS · EKSPLORASI DATA"),
    el("h1", null, "Dashboard Sastra"),
    el("p", null, "Melihat pola koleksi puisi Indonesia melalui tema, penyair, kosakata, dan kemiripan teks.")
  );
}

function metric(label, value, note, no) {
  return el("article", { class: "metric-card" },
    el("span", { class: "metric-no" }, no),
    el("span", { class: "metric-label" }, label),
    el("strong", { class: "metric-value" }, value),
    el("span", { class: "metric-note" }, note)
  );
}

function clusterSection(c, root) {
  const sec = el("section", { class: "chart wide cluster-chart" },
    el("div", { class: "chart-head" },
      el("div", null, el("span", { class: "eyebrow" }, "EKSPLORASI TANPA LABEL"), el("h2", null, "Kelompok puisi"))
    )
  );

  if (!c.tersedia) {
    sec.append(el("p", { class: "empty" }, c.alasan));
    return sec;
  }

  const pick = el("select", { id: "kpick", onchange: () => {
    wantK = pick.value;
    const page = root;
    clear(page);
    render(page, [], () => true);
  } }, [
    el("option", { value: "", selected: !wantK }, "Otomatis (silhouette)"),
    ...[3, 4, 5, 6, 7, 8].map((n) => el("option", { value: n, selected: String(n) === wantK }, String(n))),
  ]);

  sec.append(
    el("div", { class: "k-pick" },
      el("label", { for: "kpick" }, "Jumlah kelompok"),
      pick,
      el("span", null, `Dipakai: ${c.k}`)
    ),
    el("p", { class: "chart-note" }, c.catatan),
    el("ul", { class: "clusters" }, c.klaster.map((cluster, i) =>
      el("li", null,
        el("div", { class: "cn" },
          el("span", { class: "cluster-index" }, `0${i + 1}`),
          el("b", null, `Kelompok ${i + 1}`),
          el("small", null, `${fmt(cluster.ukuran)} puisi`)
        ),
        el("div", null,
          el("p", { class: "kw" }, cluster.kata_khas.join(", ")),
          el("p", { class: "ex" }, "Contoh judul: " + cluster.contoh_judul.join("; ")),
          Object.keys(cluster.tema_berlabel || {}).length
            ? el("p", { class: "ex" }, "Tema berlabel di dalam kelompok: " + Object.entries(cluster.tema_berlabel).map(([t, n]) => `${t} ${n}`).join(", "))
            : null
        )
      )
    ))
  );

  const pts = Object.entries(c.silhouette_per_k || {})
    .map(([x, y]) => ({ x: Number(x), y: y === null ? null : Number(y) }))
    .filter((p) => Number.isFinite(p.x) && Number.isFinite(p.y))
    .sort((a, b) => a.x - b.x);

  if (pts.length > 1) {
    sec.append(
      el("div", { class: "silhouette-panel" },
        el("h3", null, "Skor silhouette menurut jumlah kelompok"),
        el("p", { class: "chart-note" }, "Nilai yang lebih tinggi umumnya menunjukkan kelompok yang lebih rapat dan terpisah. Nilai rendah berarti hasil pengelompokan masih lemah."),
        lineChart(pts, { highlight: c.k, xTitle: "k =" })
      )
    );
  }

  const ks = c.kesesuaian_dengan_tema;
  if (ks) {
    sec.append(el("p", { class: "chart-note cluster-note" },
      `Perbandingan dengan tema manual/pengguna (${fmt(ks.n_berlabel)} puisi): ARI ${Number(ks.ARI).toFixed(2)}, NMI ${Number(ks.NMI).toFixed(2)}. ${ks.catatan}`
    ));
  }
  return sec;
}
