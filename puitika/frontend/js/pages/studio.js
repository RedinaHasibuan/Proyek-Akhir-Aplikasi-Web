import { api, clear, el, errorBox, cap, fmt, toast, shared, TEMA } from "../ui.js";

export async function render(root, args, alive) {
  let draftId = args[0] ? Number(args[0]) : null;
  let saved = { judul: "", isi: "", tema: "" };   // yang terakhir tersimpan, untuk menandai perubahan
  const title = el("input", { type: "text", class: "title-in", id: "s-title", maxlength: 200, placeholder: "Judul", "aria-label": "Judul puisi" });
  const body = el("textarea", { class: "body-in", id: "s-body", placeholder: "Tulis puisimu di sini…", "aria-label": "Isi puisi", maxlength: 20000 });
  const tema = el("select", { id: "s-tema" }, [el("option", { value: "" }, "Belum dipilih"), ...TEMA.map((t) => el("option", { value: t }, cap(t)))]);
  const counts = el("span", { class: "counts" });
  const state = el("span", { class: "savestate", role: "status" });
  const saveBtn = el("button", { class: "btn", type: "button" }, "Simpan draf");
  const delBtn = el("button", { class: "btn danger small", type: "button", hidden: true }, "Hapus draf");
  const checkBtn = el("button", { class: "btn ghost", type: "button" }, "Minta saran");
  const sugg = el("div", { "aria-live": "polite" });
  const draftsBox = el("div");

  const cur = () => ({ judul: title.value.trim(), isi: body.value, tema: tema.value });
  const dirty = () => { const c = cur(); return c.judul !== saved.judul || c.isi !== saved.isi || c.tema !== saved.tema; };
  const refresh = () => {
    const words = (body.value.match(/[\p{L}\p{N}'-]+/gu) || []).length;
    const lines = body.value.split("\n").filter((l) => l.trim()).length;
    counts.textContent = `${fmt(lines)} baris · ${fmt(words)} kata`;
    state.textContent = dirty() ? (draftId ? "Ada perubahan yang belum disimpan." : "Belum disimpan.") : draftId ? "Tersimpan." : "";
    delBtn.hidden = !draftId;
  };
  for (const n of [title, body, tema]) n.addEventListener("input", refresh);

  async function save() {
    const c = cur();
    if (!c.judul && !c.isi.trim()) return toast("Isi judul atau puisinya dulu.");
    saveBtn.disabled = true;
    try {
      const d = draftId
        ? await api("/api/drafts/" + draftId, { method: "PUT", body: { judul: c.judul, isi: c.isi, tema: c.tema || null } })
        : await api("/api/drafts", { method: "POST", body: { judul: c.judul, isi: c.isi, tema: c.tema || null } });
      draftId = d.id;
      saved = c;
      history.replaceState(null, "", "#/studio/" + d.id);
      toast("Draf disimpan");
      refresh();
      loadDrafts();
    } catch (e) {
      toast(e.message);
    } finally {
      saveBtn.disabled = false;
    }
  }
  saveBtn.addEventListener("click", save);
  document.addEventListener("keydown", function onKey(e) {
    if (!document.body.contains(saveBtn)) return document.removeEventListener("keydown", onKey);
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") { e.preventDefault(); save(); }
  });

  delBtn.addEventListener("click", async () => {
    if (!confirm("Hapus draf ini? Tindakan ini tidak bisa dibatalkan.")) return;
    try {
      await api("/api/drafts/" + draftId, { method: "DELETE" });
      toast("Draf dihapus");
      draftId = null; saved = { judul: "", isi: "", tema: "" };
      title.value = ""; body.value = ""; tema.value = ""; clear(sugg);
      history.replaceState(null, "", "#/studio");
      refresh(); loadDrafts();
    } catch (e) { toast(e.message); }
  });

  function openDraft(d) {
    draftId = d.id;
    title.value = d.judul; body.value = d.isi; tema.value = d.tema || "";
    saved = { judul: d.judul.trim(), isi: d.isi, tema: d.tema || "" };
    clear(sugg);
    history.replaceState(null, "", "#/studio/" + d.id);
    refresh(); loadDrafts();
  }

  async function loadDrafts() {
    try {
      const r = await api("/api/drafts?per_page=20");
      if (!alive()) return;
      clear(draftsBox).append(
        r.items.length
          ? el("ul", { class: "drafts" }, r.items.map((d) => el("li", null,
              el("button", { class: "linkbtn d-title" + (d.id === draftId ? " on" : ""), type: "button", onclick: async () => {
                if (dirty() && !confirm("Perubahan di draf yang sedang dibuka belum disimpan. Tetap buka draf lain?")) return;
                try { openDraft(await api("/api/drafts/" + d.id)); } catch (e) { toast(e.message); }
              } }, d.judul || "(tanpa judul)"),
              el("time", { datetime: d.diubah }, String(d.diubah).slice(0, 10)))))
          : el("p", { class: "muted" }, "Belum ada draf tersimpan.")
      );
    } catch (e) {
      clear(draftsBox).append(el("p", { class: "muted" }, e.message));
    }
  }

  // ---- saran
  checkBtn.addEventListener("click", async () => {
    if (!body.value.trim()) return toast("Tulis beberapa baris dulu.");
    checkBtn.disabled = true;
    clear(sugg).append(el("p", { class: "loading" }, "Membaca tulisanmu…"));
    try {
      const r = await api("/api/studio/rekomendasi", { method: "POST", body: { text: body.value } });
      clear(sugg).append(...suggestion(r));
    } catch (e) {
      clear(sugg).append(errorBox(e.message));
    } finally {
      checkBtn.disabled = false;
    }
  });

  function replaceWord(from, to) {
    const re = new RegExp("(^|[^\\p{L}])(" + from.replace(/[.*+?^${}()|[\]\\]/g, "\\$&") + ")(?![\\p{L}])", "iu");
    if (!re.test(body.value)) return toast(`Kata “${from}” sudah tidak ada di tulisanmu.`);
    body.value = body.value.replace(re, (m, pre) => pre + to);
    refresh();
    toast(`Diganti: ${from} → ${to}`);
  }

  function suggestion(r) {
    const out = [];
    const t = r.tema;
    out.push(el("div", { class: "sec" }, el("h3", null, "Saran tema"),
      !t ? el("p", { class: "muted" }, r.galat_model || "Model tema belum tersedia. Latih dulu dengan train_model.py setelah puisimu cukup berlabel.")
        : el("div", null,
            t.yakin ? null : el("p", { class: "muted" }, "Model belum yakin. Anggap ini petunjuk kasar saja."),
            el("ul", { class: "pad-list" }, t.kandidat.map((k) => el("li", null,
              el("div", { class: "bar-row", style: { gridTemplateColumns: "5.5rem minmax(0,1fr) 3rem" } },
                el("span", { class: "lab" }, cap(k.label)), el("span", { class: "track" }, el("span", { class: "fill", style: { width: Math.round(k.prob * 100) + "%" } })), el("span", { class: "val" }, Math.round(k.prob * 100) + "%")),
              el("button", { class: "linkbtn", type: "button", onclick: () => { tema.value = k.label; refresh(); toast("Tema dipilih: " + cap(k.label)); } }, "Pakai tema ini")))))));
    const d = r.diksi;
    out.push(el("div", { class: "sec" }, el("h3", null, "Pilihan kata"),
      !d ? el("p", { class: "muted" }, "Kamus belum dimuat (python load_diksi.py --init).")
        : el("div", null,
            d.padanan.length ? el("ul", { class: "pad-list" }, d.padanan.map((p) => el("li", null,
                el("span", { class: "k" }, p.kata), el("span", { class: "nu" }, ` · baris ${p.baris}`),
                el("div", { class: "alt" }, p.padanan.map((a) => el("button", { class: "chip", type: "button", title: a.nuansa || "", onclick: () => replaceWord(p.kata, a.kata) }, a.kata))),
                p.padanan.filter((a) => a.nuansa).map((a) => el("div", { class: "nu" }, `${a.kata}: ${a.nuansa}`)))))
              : el("p", { class: "muted" }, "Tidak ada kata di tulisanmu yang punya padanan di kamus."),
            d.terkait.length ? el("div", { style: { marginTop: "1rem" } }, el("p", { class: "muted" }, "Kata yang dekat dengan suasana tulisanmu:"),
              el("div", { class: "chips" }, d.terkait.map((k) => el("a", { class: "chip", href: "#/diksi/kamus/" + encodeURIComponent(k.kata), title: k.makna }, k.kata)))) : null)));
    out.push(el("p", { class: "notice" }, r.catatan + " Tombol padanan mengganti kemunculan pertama kata itu; periksa nuansanya dulu."));
    return out;
  }

  const toMakna = el("button", { class: "btn ghost", type: "button", onclick: () => {
    if (!body.value.trim()) return toast("Tulis beberapa baris dulu.");
    shared.maknaText = body.value; shared.maknaTitle = title.value.trim();
    location.hash = "#/makna";
  } }, "Lihat maknanya");

  root.append(
    el("header", { class: "page-head" }, el("span", { class: "eyebrow" }, "MEJA TULIS · DRAF PRIBADI"), el("h1", null, "Studio Puisi"), el("p", null, "Tulis, simpan draf, dan minta saran kapan pun kamu mau. Sarannya hanya usulan; keputusan tetap di tanganmu.")),
    el("div", { class: "studio" },
      el("div", { class: "editor" }, title, body,
        el("div", { class: "editor-row" },
          el("label", { class: "field" }, el("span", null, "Tema"), tema), el("span", { class: "grow" }), counts),
        el("div", { class: "editor-row" }, saveBtn, checkBtn, toMakna, delBtn, state),
        el("p", { class: "muted small ui" }, "Draf disimpan di database instalasi Puitika dan tidak muncul di Perpustakaan. Belum ada akun pengguna, jadi siapa pun yang membuka alamat ini bisa melihat draf. Pintasan: Ctrl+S untuk menyimpan.")),
      el("aside", { class: "panel" },
        el("div", null, el("h3", null, "Draf tersimpan"), draftsBox, el("div", { style: { marginTop: "0.75rem" } }, el("button", { class: "btn ghost small", type: "button", onclick: () => {
          if (dirty() && !confirm("Perubahan belum disimpan. Tetap mulai draf baru?")) return;
          draftId = null; saved = { judul: "", isi: "", tema: "" }; title.value = ""; body.value = ""; tema.value = ""; clear(sugg);
          history.replaceState(null, "", "#/studio"); refresh(); loadDrafts(); title.focus();
        } }, "Draf baru"))),
        sugg)
    )
  );
  refresh();
  loadDrafts();
  if (draftId) {
    try { openDraft(await api("/api/drafts/" + draftId)); } catch (e) { if (alive()) { draftId = null; root.prepend(errorBox(e.message)); } }
  }
}
