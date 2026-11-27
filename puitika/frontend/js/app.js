// Router hash sederhana: #/  #/perpustakaan  #/perpustakaan/12
// #/diksi  #/studio  #/studio/5  #/makna  #/dashboard
import { api, clear, el, errorBox } from "./ui.js";

const PAGES = [
  { id: "", label: "Beranda", icon: "⌂", load: () => import("./pages/home.js") },
  { id: "perpustakaan", label: "Perpustakaan Puisi", icon: "▤", load: () => import("./pages/library.js") },
  { id: "diksi", label: "Ruang Diksi", icon: "✳", load: () => import("./pages/diksi.js") },
  { id: "studio", label: "Studio Puisi", icon: "✎", load: () => import("./pages/studio.js") },
  { id: "makna", label: "Makna Puisi", icon: "❝", load: () => import("./pages/makna.js") },
  { id: "dashboard", label: "Dashboard Sastra", icon: "▦", load: () => import("./pages/dashboard.js") },
];

const main = document.getElementById("main");
const nav = document.getElementById("nav");
const topbarTitle = document.getElementById("topbar-title");
const rail = document.getElementById("primary-rail");
const shell = document.querySelector(".shell");
const desktopToggle = document.getElementById("desktop-nav-toggle");
const mobileToggle = document.getElementById("mobile-nav-toggle");
const railBackdrop = document.getElementById("rail-backdrop");
let token = 0; // mencegah halaman lama menimpa halaman baru saat navigasi cepat

function setDesktopRail(open) {
  shell?.classList.toggle("rail-collapsed", !open);
  if (desktopToggle) {
    desktopToggle.setAttribute("aria-expanded", String(open));
    desktopToggle.setAttribute("aria-label", open ? "Sembunyikan menu navigasi" : "Tampilkan menu navigasi");
  }
}

desktopToggle?.addEventListener("click", () => {
  const isOpen = !shell?.classList.contains("rail-collapsed");
  setDesktopRail(!isOpen);
});

function setMobileNav(open) {
  document.body.classList.toggle("nav-open", open);
  if (mobileToggle) {
    mobileToggle.setAttribute("aria-expanded", String(open));
    mobileToggle.setAttribute("aria-label", open ? "Tutup menu navigasi" : "Buka menu navigasi");
  }
}

mobileToggle?.addEventListener("click", () => {
  setMobileNav(!document.body.classList.contains("nav-open"));
});
railBackdrop?.addEventListener("click", () => setMobileNav(false));
nav.addEventListener("click", (event) => {
  if (event.target.closest("a")) setMobileNav(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") setMobileNav(false);
});

nav.append(...PAGES.map((p) => el(
  "a",
  { href: p.id ? "#/" + p.id : "#/", "data-id": p.id, class: "nav-link" },
  el("span", { class: "nav-icon", "aria-hidden": "true" }, p.icon),
  el("span", { class: "nav-label" }, p.label),
  p.id === "studio" ? el("span", { class: "nav-pill" }, "Tulis") : null
)));

function parse() {
  const parts = location.hash.replace(/^#\/?/, "").split("/").filter(Boolean).map(decodeURIComponent);
  return { id: parts[0] || "", args: parts.slice(1) };
}

async function render() {
  setMobileNav(false);
  const { id, args } = parse();
  const page = PAGES.find((p) => p.id === id);
  const mine = ++token;
  document.body.classList.remove("focus-reading");
  nav.querySelectorAll("a").forEach((a) => (
    a.getAttribute("data-id") === id ? a.setAttribute("aria-current", "page") : a.removeAttribute("aria-current")
  ));
  if (topbarTitle) topbarTitle.textContent = page ? page.label : "Halaman tidak ditemukan";
  clear(main);

  if (!page) {
    document.title = "Halaman tidak ditemukan · Puitika";
    main.append(el("div", { class: "page" },
      el("div", { class: "page-head" }, el("span", { class: "eyebrow" }, "404 · RUANG TAK DITEMUKAN"), el("h1", null, "Halaman ini belum ada.")),
      el("p", { class: "muted" }, "Alamat yang kamu buka tidak dikenal oleh Puitika."),
      el("a", { class: "btn", href: "#/" }, "Kembali ke beranda")
    ));
    return;
  }

  document.title = (id === "" ? "Puitika" : page.label) + " · Puitika";
  try {
    const mod = await page.load();
    if (mine !== token) return;
    const node = el("div", { class: "page" });
    main.append(node);
    await mod.render(node, args, () => mine === token);
  } catch (e) {
    if (mine !== token) return;
    clear(main);
    main.append(el("div", { class: "page" },
      el("div", { class: "page-head" }, el("span", { class: "eyebrow" }, "TERJADI KENDALA"), el("h1", null, "Ruang ini belum dapat dibuka.")),
      errorBox("Halaman gagal dimuat: " + e.message)
    ));
  }

  if (mine === token && !args.length) main.focus({ preventScroll: true });
  window.scrollTo({ top: 0, behavior: "smooth" });
}

window.addEventListener("hashchange", render);
