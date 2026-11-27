import { api, clear, el, errorBox, wordItem } from "../ui.js";

const ROOMS = [
  { id: "perpustakaan", no: "01", title: "Perpustakaan", desc: "Jelajahi puisi Indonesia.", icon: "▤", tone: "sage" },
  { id: "diksi", no: "02", title: "Ruang Diksi", desc: "Temukan kata dan nuansanya.", icon: "✳", tone: "caramel" },
  { id: "studio", no: "03", title: "Studio Puisi", desc: "Tulis dan simpan drafmu.", icon: "✎", tone: "sage" },
  { id: "makna", no: "04", title: "Makna Puisi", desc: "Baca lapisan sebuah puisi.", icon: "❝", tone: "caramel" },
  { id: "dashboard", no: "05", title: "Dashboard Sastra", desc: "Amati pola dalam korpus.", icon: "▦", tone: "sage" },
];

const EXAMPLES = [
  "sedih yang lembut dan redup",
  "ingin bertemu seseorang yang jauh",
  "suka sekaligus tidak suka",
];

export async function render(root) {
  const input = el("textarea", {
    id: "home-diksi-query",
    rows: 1,
    maxlength: 300,
    placeholder: "Ceritakan rasa atau makna yang sedang kamu cari…",
    "aria-label": "Deskripsi makna kata yang dicari",
  });
  const out = el("div", { class: "home-search-results", "aria-live": "polite" });

  async function search(text) {
    text = text.trim();
    clear(out);
    if (!text) {
      out.append(el("p", { class: "empty" }, "Tuliskan dulu gambaran maknanya."));
      return;
    }
    out.append(el("p", { class: "loading" }, "Mencari kata yang mendekati…"));
    try {
      const r = await api("/api/diksi/search", { method: "POST", body: { deskripsi: text, top_k: 5 } });
      clear(out);
      if (!r.hasil.length) {
        out.append(el("p", { class: "empty" }, "Belum ada kata yang cocok. Coba uraikan maknanya dengan cara lain."));
        return;
      }
      out.append(
        el("div", { class: "result-heading" },
          el("span", { class: "eyebrow" }, "KATA YANG MUNGKIN KAMU CARI"),
          el("a", { class: "text-link", href: "#/diksi/cari" }, "Lihat semua")
        ),
        el("ul", { class: "word-list reveal" }, r.hasil.map((w) => wordItem(w, {
          onPick: (k) => { location.hash = "#/diksi/kamus/" + encodeURIComponent(k); },
        }))),
        el("p", { class: "notice" }, r.catatan)
      );
    } catch (e) {
      clear(out).append(errorBox(e.message));
    }
  }

  const form = el("form", {
    class: "hero-search-form",
    onsubmit: (e) => { e.preventDefault(); search(input.value); },
  },
    el("label", { class: "sr-only", for: "home-diksi-query" }, "Ceritakan makna yang dicari"),
    el("div", { class: "search-field" },
      el("span", { class: "search-icon", "aria-hidden": "true" }, "⌕"),
      input,
      el("button", { class: "btn", type: "submit" }, "Temukan kata")
    ),
    el("div", { class: "example-row" },
      el("span", { class: "example-label" }, "Misalnya:"),
      ...EXAMPLES.map((text) => el("button", {
        class: "example-chip",
        type: "button",
        onclick: () => { input.value = text; search(text); },
      }, text))
    )
  );

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      search(input.value);
    }
  });

  root.append(
    el("section", { class: "home-hero home-hero-compact" },
      el("div", { class: "hero-copy" },
        el("span", { class: "eyebrow" }, "ARSIP SASTRA INDONESIA"),
        el("h1", null, "Membaca lebih dekat. ", el("em", null, "Menulis lebih jujur.")),
        el("p", { class: "hero-lede" }, "Ruang untuk menjelajahi puisi, menemukan diksi, dan memahami lapisan makna."),
        form,
        out
      ),
      el("div", { class: "hero-art hero-art-compact", "aria-hidden": "true" },
        el("div", { class: "art-orbit orbit-one" }),
        el("div", { class: "art-orbit orbit-two" }),
        el("div", { class: "book-stack stack-back" }),
        el("div", { class: "book-stack stack-front" },
          el("span", { class: "book-mark" }, "P"),
          el("span", { class: "book-title" }, "Ruang"),
          el("span", { class: "book-title book-title-second" }, "untuk kata"),
          el("span", { class: "book-rule" }),
          el("span", { class: "book-small" }, "baca perlahan")
        ),
        el("span", { class: "art-leaf leaf-one" }, "✳"),
        el("span", { class: "art-leaf leaf-two" }, "❧"),
        el("span", { class: "art-caption" }, "Temukan kata yang tepat.")
      )
    ),
    el("section", { class: "home-rooms" },
      el("div", { class: "home-rooms-head" },
        el("div", null,
          el("span", { class: "eyebrow" }, "JELAJAHI PUITIKA"),
          el("h2", null, "Pilih ruangmu")
        ),
        el("span", { class: "hand-note" }, "lima cara mendekati puisi")
      ),
      el("div", { class: "feature-grid feature-grid-compact" }, ROOMS.map((room) =>
        el("a", { class: "feature-card feature-card-compact " + room.tone, href: "#/" + room.id },
          el("div", { class: "feature-top" },
            el("span", { class: "feature-no" }, room.no),
            el("span", { class: "feature-icon", "aria-hidden": "true" }, room.icon)
          ),
          el("h3", null, room.title),
          el("p", null, room.desc),
          el("span", { class: "feature-arrow", "aria-hidden": "true" }, "↗")
        )
      ))
    ),
    el("aside", { class: "home-note", "aria-label": "Catatan Puitika" },
      el("span", { class: "home-note-mark", "aria-hidden": "true" }, "“"),
      el("div", { class: "home-note-copy" },
        el("span", { class: "home-note-label" }, "CATATAN PUITIKA"),
        el("p", null, "Kata yang tepat dapat memberi bentuk pada perasaan yang belum bernama.")
      ),
      el("span", { class: "home-note-sign" }, "— Puitika")
    )
  );
}
