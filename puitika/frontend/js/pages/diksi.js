import { api, clear, el, errorBox, fmt, cap, qs, debounce, wordItem, EMOSI } from "../ui.js";

const TABS = [["chat", "Teman Diksi"], ["cari", "Cari dari makna"], ["kamus", "Kamus"]];
const chatLog = []; // {who: "you"|"bot", text, data} — bertahan selama halaman tidak dimuat ulang
const kamus = { q: "", emosi: "", page: 1 };

export async function render(root, args, alive) {
  const tab = TABS.some(([id]) => id === args[0]) ? args[0] : "chat";
  const body = el("div");
  root.append(
    el("header", { class: "page-head" }, el("span", { class: "eyebrow" }, "KAMUS · PADANAN · TEMAN DIKSI"), el("h1", null, "Ruang Diksi"),
      el("p", null, "Pilih kata dengan tahu nuansanya: tanya Teman Diksi, cari kata dari maknanya, atau buka kamus.")),
    el("div", { class: "tabs", role: "tablist" }, TABS.map(([id, label]) =>
      el("button", { type: "button", role: "tab", "aria-selected": String(id === tab), onclick: () => { location.hash = "#/diksi/" + id; } }, label))),
    body
  );
  if (tab === "chat") chat(body);
  else if (tab === "cari") cari(body);
  else await kamusTab(body, args[1], alive);
}

// ------------------------------------------------------------------ Teman Diksi
function chat(root) {
  const log = el("div", {
    class: "teman-chat-log",
    role: "log",
    "aria-live": "polite",
    "aria-relevant": "additions text",
    "aria-label": "Riwayat percakapan Teman Diksi",
  });
  const input = el("textarea", {
    class: "teman-chat-input",
    rows: 1,
    id: "chat-in",
    maxlength: 300,
    placeholder: "Tulis pertanyaanmu di sini…",
    "aria-label": "Pesan untuk Teman Diksi",
    autocomplete: "off",
  });
  const send = el("button", {
    class: "teman-send",
    type: "submit",
    "aria-label": "Kirim pesan",
  }, el("span", null, "Kirim"), el("span", { class: "teman-send-arrow", "aria-hidden": "true" }, "↑"));
  const reset = el("button", {
    class: "teman-reset",
    type: "button",
    onclick: () => {
      if (pending) return;
      chatLog.splice(0, chatLog.length);
      renderEmpty();
    },
  }, "Percakapan baru");
  const logHeader = el("div", { class: "teman-chat-heading" },
    el("div", { class: "teman-chat-identity" },
      el("div", { class: "teman-chat-avatar", "aria-hidden": "true" }, "T"),
      el("div", { class: "teman-chat-title-wrap" },
        el("div", { class: "teman-chat-title-line" },
          el("h2", null, "Teman Diksi"),
          el("span", { class: "teman-chat-state" }, el("span", { class: "teman-state-dot" }), "Siap membantu")
        ),
        el("p", null, "Asisten kosakata untuk menemukan arti dan nuansa kata.")
      )
    ),
    el("div", { class: "teman-chat-tools" },
      el("span", { class: "teman-source-badge" }, "Berbasis kamus Puitika"),
      reset
    )
  );
  const composer = el("form", {
    class: "teman-composer",
    onsubmit: (event) => { event.preventDefault(); ask(input.value); },
  },
    el("div", { class: "teman-composer-field" }, input, send),
    el("div", { class: "teman-composer-meta" },
      el("span", null, "Enter untuk mengirim · Shift + Enter untuk baris baru"),
      el("span", null, "Maks. 300 karakter")
    )
  );
  const disclaimer = el("p", { class: "teman-disclaimer" },
    "Jawaban disusun dari aturan percakapan dan kamus terkurasi Puitika. Periksa kembali nuansa kata sesuai konteks puisimu."
  );

  let pending = false;
  let typingNode = null;

  const scrollToLatest = () => {
    requestAnimationFrame(() => { log.scrollTop = log.scrollHeight; });
  };

  const renderEmpty = () => {
    clear(log);
    reset.hidden = true;
    const prompts = [
      "arti lara",
      "kata lain untuk sedih",
      "lawan kata gelisah",
      "kata yang menggambarkan perasaan suka dan tidak suka sekaligus",
    ];
    const empty = el("div", { class: "teman-empty-state" },
      el("div", { class: "teman-empty-mark", "aria-hidden": "true" }, "✳"),
      el("span", { class: "teman-empty-kicker" }, "MEJA DIKSI PUITIKA"),
      el("h3", null, "Halo, apa yang sedang kamu cari?"),
      el("p", null, "Tanyakan arti sebuah kata, cari padanan yang lebih pas, atau ceritakan perasaan yang belum kamu temukan namanya."),
      el("div", { class: "teman-prompt-label" }, "MULAI DARI PERTANYAAN INI"),
      el("div", { class: "teman-prompts" }, prompts.map((prompt) =>
        el("button", { class: "teman-prompt", type: "button", onclick: () => ask(prompt) },
          el("span", { class: "teman-prompt-arrow", "aria-hidden": "true" }, "↗"), prompt
        )
      ))
    );
    log.append(empty);
  };

  const addBot = (r) => {
    const bubble = el("div", { class: "teman-bubble teman-bubble-bot" },
      el("p", { class: "teman-bubble-text" }, r.balasan || "Maaf, aku belum menemukan jawaban yang sesuai."),
      r.kandidat && r.kandidat.length
        ? el("div", { class: "teman-answer-section" },
            el("div", { class: "teman-answer-label" }, "KATA YANG MUNGKIN SESUAI"),
            el("ul", { class: "word-list teman-answer-words" }, r.kandidat.map((w) => wordItem(w, {
              onPick: (word) => { location.hash = "#/diksi/kamus/" + encodeURIComponent(word); },
            })))
          )
        : null,
      r.saran && r.saran.length
        ? el("div", { class: "teman-followups" },
            el("span", { class: "teman-answer-label" }, "COBA TANYAKAN JUGA"),
            el("div", { class: "chips" }, r.saran.map((s) =>
              el("button", { class: "chip", type: "button", onclick: () => ask(s) }, s)
            ))
          )
        : null
    );
    const row = el("div", { class: "teman-message teman-message-bot" },
      el("div", { class: "teman-message-avatar teman-avatar-bot", "aria-hidden": "true" }, "T"),
      el("div", { class: "teman-message-content" },
        el("div", { class: "teman-message-meta" },
          el("strong", null, "Teman Diksi"),
          el("span", null, "Asisten kosakata")
        ),
        bubble
      )
    );
    log.append(row);
    return row;
  };

  const addYou = (text) => {
    const row = el("div", { class: "teman-message teman-message-you" },
      el("div", { class: "teman-message-content" },
        el("div", { class: "teman-message-meta teman-user-meta" }, el("strong", null, "Kamu")),
        el("div", { class: "teman-bubble teman-bubble-you" }, el("p", null, text))
      ),
      el("div", { class: "teman-message-avatar teman-avatar-you", "aria-hidden": "true" }, "K")
    );
    log.append(row);
    return row;
  };

  const addTyping = () => {
    typingNode = el("div", { class: "teman-message teman-message-bot teman-typing-row", "aria-label": "Teman Diksi sedang menyiapkan jawaban" },
      el("div", { class: "teman-message-avatar teman-avatar-bot", "aria-hidden": "true" }, "T"),
      el("div", { class: "teman-message-content" },
        el("div", { class: "teman-message-meta" }, el("strong", null, "Teman Diksi")),
        el("div", { class: "teman-typing-bubble" },
          el("span", null), el("span", null), el("span", null),
          el("span", { class: "teman-typing-label" }, "Sedang menyiapkan jawaban…")
        )
      )
    );
    log.append(typingNode);
  };

  async function ask(text) {
    text = String(text || "").trim();
    if (!text || pending) return;
    if (!chatLog.length) clear(log);
    chatLog.push({ who: "you", text });
    addYou(text);
    input.value = "";
    pending = true;
    send.disabled = true;
    input.disabled = true;
    reset.hidden = false;
    addTyping();
    scrollToLatest();
    try {
      const result = await api("/api/diksi/chat", { method: "POST", body: { pesan: text } });
      typingNode?.remove();
      typingNode = null;
      chatLog.push({ who: "bot", data: result });
      addBot(result);
    } catch (error) {
      typingNode?.remove();
      typingNode = null;
      log.append(el("div", { class: "teman-error-row" }, errorBox(error.message)));
    } finally {
      pending = false;
      send.disabled = false;
      input.disabled = false;
      input.focus({ preventScroll: true });
      scrollToLatest();
    }
  }

  input.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      composer.requestSubmit();
    }
  });

  root.append(el("section", { class: "chat teman-chat", "aria-label": "Percakapan Teman Diksi" },
    logHeader,
    log,
    el("div", { class: "teman-composer-wrap" }, composer, disclaimer)
  ));

  if (chatLog.length) {
    reset.hidden = false;
    for (const message of chatLog) {
      if (message.who === "you") addYou(message.text);
      else addBot(message.data);
    }
    scrollToLatest();
  } else {
    renderEmpty();
  }
}

// ------------------------------------------------------------------ Cari dari makna
function cari(root) {
  const text = el("textarea", { rows: 3, maxlength: 300, id: "c-in", placeholder: "mis. menunggu dengan penuh harapan", "aria-label": "Deskripsi makna" });
  const emosi = el("select", { id: "c-emosi" }, [el("option", { value: "" }, "Semua suasana"), ...EMOSI.map((e) => el("option", { value: e }, cap(e)))]);
  const out = el("div", { "aria-live": "polite" });
  const run = async () => {
    const t = text.value.trim();
    clear(out);
    if (!t) return out.append(el("p", { class: "empty" }, "Tulis dulu gambaran maknanya."));
    out.append(el("p", { class: "loading" }, "Mencari kata…"));
    try {
      const r = await api("/api/diksi/search", { method: "POST", body: { deskripsi: t, emosi: emosi.value || undefined, top_k: 8 } });
      clear(out);
      if (!r.hasil.length) return out.append(el("p", { class: "empty" }, "Belum ada kata yang cocok. Coba pakai kata lain dalam gambaranmu."));
      out.append(el("ul", { class: "word-list reveal" }, r.hasil.map((w) => wordItem(w, { onPick: (k) => { location.hash = "#/diksi/kamus/" + encodeURIComponent(k); } }))), el("p", { class: "notice" }, r.catatan));
    } catch (e) {
      clear(out).append(errorBox(e.message));
    }
  };
  root.append(
    el("form", { class: "makna-in", onsubmit: (e) => { e.preventDefault(); run(); } },
      el("label", { class: "field", for: "c-in" }, el("span", null, "Gambarkan maknanya"), text),
      el("label", { class: "field", for: "c-emosi" }, el("span", null, "Batasi suasana (opsional)"), emosi),
      el("div", null, el("button", { class: "btn", type: "submit" }, "Cari kata"))
    ),
    out
  );
}

// ------------------------------------------------------------------ Kamus
async function kamusTab(root, word, alive) {
  if (word) return entry(root, word, alive);
  const list = el("div", { "aria-live": "polite" });
  const qIn = el("input", { type: "search", id: "k-q", maxlength: 100, placeholder: "awalan atau bagian kata", value: kamus.q });
  const emo = el("select", { id: "k-e", onchange: () => { kamus.emosi = emo.value; kamus.page = 1; load(); } },
    [el("option", { value: "" }, "Semua suasana"), ...EMOSI.map((e) => el("option", { value: e, selected: e === kamus.emosi }, cap(e)))]);
  qIn.addEventListener("input", debounce(() => { kamus.q = qIn.value.trim(); kamus.page = 1; load(); }, 300));
  root.append(
    el("div", { class: "filters", style: { gridTemplateColumns: "minmax(10rem, 2fr) minmax(8rem, 1fr)" } },
      el("label", { class: "field", for: "k-q" }, el("span", null, "Cari kata"), qIn),
      el("label", { class: "field", for: "k-e" }, el("span", null, "Suasana"), emo)
    ),
    list
  );
  async function load() {
    clear(list).append(el("p", { class: "loading" }, "Memuat kata…"));
    try {
      const r = await api("/api/diksi/words" + qs({ q: kamus.q, emosi: kamus.emosi, page: kamus.page, per_page: 20 }));
      if (!alive()) return;
      clear(list);
      if (!r.items.length) return list.append(el("p", { class: "empty" }, "Tidak ada kata yang cocok."));
      list.append(
        el("p", { class: "result-meta" }, `${fmt(r.total)} kata`),
        el("ul", { class: "word-list" }, r.items.map((w) => wordItem(w, { onPick: (k) => { location.hash = "#/diksi/kamus/" + encodeURIComponent(k); } }))),
        r.pages > 1 ? el("div", { class: "pager" },
          el("button", { class: "btn ghost small", type: "button", disabled: r.page <= 1, onclick: () => { kamus.page--; load(); } }, "Sebelumnya"),
          el("span", null, `Halaman ${r.page} dari ${r.pages}`),
          el("button", { class: "btn ghost small", type: "button", disabled: r.page >= r.pages, onclick: () => { kamus.page++; load(); } }, "Berikutnya")) : null
      );
    } catch (e) {
      clear(list).append(errorBox(e.message));
    }
  }
  load();
}

async function entry(root, word, alive) {
  const back = el("a", { class: "back", href: "#/diksi/kamus" }, "Kembali ke kamus");
  root.append(back, el("p", { class: "loading" }, "Memuat kata…"));
  try {
    const e = await api("/api/diksi/words/" + encodeURIComponent(word));
    if (!alive()) return;
    const relBlock = (key, title) => e.relasi && e.relasi[key] && e.relasi[key].length
      ? el("div", { class: "rel" }, el("h3", null, title), el("div", { class: "chips" }, e.relasi[key].map((r) =>
          el("a", { class: "chip", href: "#/diksi/kamus/" + encodeURIComponent(r.kata), title: r.nuansa || r.makna }, r.kata)))) : null;
    const nuances = ["sinonim", "terkait"].flatMap((k) => (e.relasi && e.relasi[k]) || []).filter((r) => r.nuansa);
    clear(root).append(back, el("article", { class: "entry" },
      el("h2", null, e.kata),
      el("div", { class: "word-head" }, e.kelas_kata ? el("span", { class: "pos" }, e.kelas_kata) : null, e.emosi ? el("span", { class: "tag" }, e.emosi) : null),
      el("p", { class: "word-mean" }, e.makna),
      e.nuansa ? el("p", { class: "word-nuance" }, "Nuansa: " + e.nuansa) : null,
      e.contoh ? el("p", { class: "word-example" }, "“" + e.contoh + "”") : null,
      relBlock("sinonim", "Sinonim"), relBlock("antonim", "Antonim"), relBlock("terkait", "Kata terkait"),
      nuances.length ? el("div", { class: "rel" }, el("h3", null, "Beda nuansa"), el("ul", { class: "figlist" }, nuances.map((r) =>
        el("li", null, el("a", { href: "#/diksi/kamus/" + encodeURIComponent(r.kata) }, r.kata), ": ", r.nuansa)))) : null,
      e.sumber ? el("p", { class: "muted small ui", style: { marginTop: "1.5rem" } }, "Sumber: " + e.sumber) : null
    ));
  } catch (err) {
    clear(root).append(back, errorBox(err.message));
  }
}
