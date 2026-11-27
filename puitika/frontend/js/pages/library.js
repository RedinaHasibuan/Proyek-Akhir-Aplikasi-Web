import { api, clear, el, errorBox, fmt, cap, qs, debounce } from "../ui.js";

const SORTS = [["title", "Judul A–Z"], ["poet", "Nama penyair"], ["words", "Puisi terpanjang"], ["newest", "Terbaru ditambahkan"]];
const state = { q: "", tema: "", periode: "", sort: "title", page: 1, view: "grid" };

export async function render(root, args, alive) {
  if (args[0]) return renderDetail(root, args[0], alive);

  let filters;
  try {
    filters = await api("/api/filters");
  } catch (e) {
    root.append(
      pageHead(),
      errorBox(e.message)
    );
    return;
  }
  if (!alive()) return;

  const list = el("div", { "aria-live": "polite" });
  const qIn = el("input", { type: "search", id: "f-q", maxlength: 100, placeholder: "Cari judul, penyair, atau kata…", value: state.q });
  const select = (id, label, opts, key) => {
    const s = el("select", {
      id,
      onchange: () => {
        state[key] = s.value;
        state.page = 1;
        if (key === "tema" && typeof drawThemeTabs === "function") drawThemeTabs();
        load();
      },
    }, opts.map(([v, t]) => el("option", { value: v, selected: v === state[key] }, t)));
    return el("label", { class: "field", for: id }, el("span", null, label), s);
  };

  const temaOpts = [["", "Semua tema"], ...filters.tema.map((t) => [t.label, `${cap(t.label)} · ${fmt(t.count)}`])];
  const periodeOpts = [["", "Semua periode"], ...(filters.periode || []).map((p) => [p.label, `${p.label} · ${fmt(p.count)}`])];
  const temaField = select("f-tema", "Tema puisi", temaOpts, "tema");
  const temaSelect = temaField.querySelector("select");
  const categoryTabs = el("div", { class: "category-tabs", "aria-label": "Pilih tema puisi" });

  function drawThemeTabs() {
    clear(categoryTabs).append(
      el("span", { class: "category-tabs-label" }, "PILIH RAK"),
      el("button", {
        class: "category-tab" + (!state.tema ? " active" : ""),
        type: "button",
        "aria-pressed": String(!state.tema),
        onclick: () => setTema(""),
      }, "Semua tema"),
      ...filters.tema.map((t) => el("button", {
        class: "category-tab" + (state.tema === t.label ? " active" : ""),
        type: "button",
        "aria-pressed": String(state.tema === t.label),
        onclick: () => setTema(t.label),
      }, cap(t.label)))
    );
  }

  function setTema(value) {
    state.tema = value;
    state.page = 1;
    temaSelect.value = value;
    drawThemeTabs();
    load();
  }

  drawThemeTabs();
  root.append(
    pageHead(filters),
    el("section", { class: "filter-panel" },
      el("div", { class: "filter-search" },
        el("span", { class: "search-icon", "aria-hidden": "true" }, "⌕"),
        qIn
      ),
      el("div", { class: "filters" },
        temaField,
        select("f-periode", "Periode sastra", periodeOpts, "periode"),
        select("f-sort", "Urutkan", SORTS, "sort")
      )
    ),
    categoryTabs,
    el("div", { class: "library-list-wrap" }, list)
  );

  qIn.addEventListener("input", debounce(() => {
    state.q = qIn.value.trim();
    state.page = 1;
    load();
  }, 300));

  async function load() {
    clear(list).append(el("p", { class: "loading" }, "Membuka rak puisi…"));
    try {
      const r = await api("/api/poems" + qs({
        q: state.q, tema: state.tema, periode: state.periode,
        sort: state.sort, page: state.page, per_page: 12,
      }));
      if (!alive()) return;
      clear(list);
      if (!r.items.length) {
        list.append(el("div", { class: "empty-card" },
          el("span", { class: "empty-mark" }, "✳"),
          el("h2", null, "Rak ini belum menemukan judul yang cocok."),
          el("p", null, "Coba ganti kata pencarian atau longgarkan filter tema dan periode.")
        ));
        return;
      }
      const grid = el("div", { class: "library-grid" + (state.view === "list" ? " list-mode" : "") }, r.items.map(poemCard));
      const gridBtn = el("button", {
        class: "view-toggle" + (state.view === "grid" ? " active" : ""),
        type: "button",
        "aria-pressed": String(state.view === "grid"),
        onclick: () => { state.view = "grid"; grid.classList.remove("list-mode"); gridBtn.classList.add("active"); listBtn.classList.remove("active"); gridBtn.setAttribute("aria-pressed", "true"); listBtn.setAttribute("aria-pressed", "false"); },
      }, "▦");
      const listBtn = el("button", {
        class: "view-toggle" + (state.view === "list" ? " active" : ""),
        type: "button",
        "aria-pressed": String(state.view === "list"),
        onclick: () => { state.view = "list"; grid.classList.add("list-mode"); listBtn.classList.add("active"); gridBtn.classList.remove("active"); listBtn.setAttribute("aria-pressed", "true"); gridBtn.setAttribute("aria-pressed", "false"); },
      }, "☷");
      list.append(
        el("div", { class: "library-results-head" },
          el("div", { class: "results-count" },
            el("p", { class: "result-meta" }, `${fmt(r.total)} puisi ditemukan`),
            el("span", { class: "result-meta" }, `Halaman ${r.page} dari ${r.pages}`)
          ),
          el("div", { class: "view-switch", "aria-label": "Tampilan koleksi" }, gridBtn, listBtn)
        ),
        grid,
        pager(r)
      );
    } catch (e) {
      clear(list).append(errorBox(e.message));
    }
  }

  function poemCard(p) {
    return el("article", { class: "library-card" },
      el("span", { class: "bookmark-ribbon", "aria-hidden": "true" }),
      el("a", { href: "#/perpustakaan/" + p.id, class: "library-card-link" },
        el("div", { class: "card-meta-top" },
          el("span", { class: "tag" }, p.tema ? cap(p.tema.label) : "Belum bertema"),
          el("span", { class: "hand-date" }, `${fmt(p.n_words)} kata`)
        ),
        el("h2", null, p.title),
        el("p", { class: "card-excerpt poem-body" }, p.excerpt || "Tidak ada kutipan untuk puisi ini."),
        el("div", { class: "card-author" },
          el("span", { class: "author-mark" }, initials(p.poet ? p.poet.name : "Penyair")),
          el("span", null,
            el("strong", null, p.poet ? p.poet.name : "Penyair tidak tercatat"),
            el("small", null, p.poet && p.poet.periode ? p.poet.periode : "Periode belum tercatat")
          ),
          el("span", { class: "card-arrow", "aria-hidden": "true" }, "↗")
        )
      )
    );
  }

  function pager(r) {
    if (r.pages <= 1) return null;
    const go = (d) => {
      state.page += d;
      load();
      list.scrollIntoView({ block: "start", behavior: "smooth" });
    };
    return el("div", { class: "pager" },
      el("button", { class: "btn btn-outline small", type: "button", disabled: r.page <= 1, onclick: () => go(-1) }, "← Sebelumnya"),
      el("span", null, `Halaman ${r.page} dari ${r.pages}`),
      el("button", { class: "btn btn-outline small", type: "button", disabled: r.page >= r.pages, onclick: () => go(1) }, "Berikutnya →")
    );
  }

  load();
}

function pageHead(filters) {
  const total = filters ? fmt(filters.total_public) : "";
  const unlabeled = filters && filters.tema_unlabeled ? `${fmt(filters.tema_unlabeled)} puisi belum memiliki label tema.` : "Koleksi puisi domain publik untuk dibaca dan ditelusuri.";
  return el("header", { class: "page-head" },
    el("span", { class: "eyebrow" }, "RAK BACA · WIKISUMBER"),
    el("h1", null, "Perpustakaan Puisi"),
    el("p", null, filters ? `${total} puisi publik tersimpan di dalam korpus. ${unlabeled}` : "Jelajahi puisi Indonesia dari korpus Puitika.")
  );
}

function initials(name) {
  return String(name || "P").split(/\s+/).filter(Boolean).slice(0, 2).map((part) => part[0].toUpperCase()).join("");
}

async function renderDetail(root, id, alive) {
  root.append(
    el("a", { class: "back", href: "#/perpustakaan" }, "← Kembali ke rak"),
    el("p", { class: "loading" }, "Membuka halaman puisi…")
  );
  let p;
  try {
    p = await api("/api/poems/" + encodeURIComponent(id));
  } catch (e) {
    if (!alive()) return;
    clear(root).append(el("a", { class: "back", href: "#/perpustakaan" }, "← Kembali ke rak"), errorBox(e.message));
    return;
  }
  if (!alive()) return;
  document.title = p.title + " · Puitika";

  const stanzas = p.body.replace(/\r\n?/g, "\n").split(/\n\s*\n/)
    .map((b) => b.split("\n").map((l) => l.trim()).filter((l) => l && !/^\.+$/.test(l)))
    .filter((b) => b.length);

  const focusBtn = el("button", { class: "btn btn-outline small", type: "button", "aria-pressed": "false" }, "Mode fokus baca");
  focusBtn.addEventListener("click", () => {
    const enabled = document.body.classList.toggle("focus-reading");
    focusBtn.setAttribute("aria-pressed", String(enabled));
    focusBtn.textContent = enabled ? "Keluar mode fokus" : "Mode fokus baca";
  });

  const side = el("aside", { class: "poem-side catalog-note" },
    el("span", { class: "eyebrow" }, "CATATAN KATALOG"),
    el("dl", null,
      el("div", null, el("dt", null, "Penyair"), el("dd", null, p.poet ? p.poet.name : "Tidak tercatat")),
      el("div", null, el("dt", null, "Tema"), el("dd", null, p.tema ? cap(p.tema.label) : "Belum diberi tema")),
      el("div", null, el("dt", null, "Sumber"), el("dd", null, p.source_url
        ? el("a", { href: p.source_url, rel: "noopener noreferrer", target: "_blank" }, "Buka Wikisumber ↗")
        : "Sumber tidak tersedia"))
    ),
    el("a", { class: "btn", href: "#/makna/puisi/" + p.id }, "Baca analisis makna")
  );

  clear(root).append(
    el("div", { class: "detail-toolbar" },
      el("a", { class: "back", href: "#/perpustakaan" }, "← Kembali ke rak"),
      focusBtn
    ),
    el("div", { class: "poem-detail-layout" },
      el("article", { class: "poem-paper" },
        el("header", { class: "poem-head" },
          el("span", { class: "eyebrow" }, "PUISI · KOLEKSI PUBLIK"),
          el("h1", null, p.title),
          el("p", { class: "by" }, p.poet ? p.poet.name : "Penyair tidak tercatat")
        ),
        el("div", { class: "poem-body" }, stanzas.map((lines) =>
          el("p", { class: "stanza" }, lines.map((line) => el("span", { class: "line" }, line)))
        )),
        el("div", { class: "poem-endmark", "aria-hidden": "true" }, "❧")
      ),
      side
    )
  );
}
