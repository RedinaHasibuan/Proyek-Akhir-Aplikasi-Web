"""Daftar label FINAL Puitika dan kata kunci bantu pengambilan sampel.

Perubahan dari PDF ide awal (alasannya ada di LABEL_GUIDE.md):
  - Tema: "Filosofis" digabung ke "Kehidupan" (tumpang tindih besar, data terlalu sedikit untuk memisahkan).
  - Emosi: "Takut" dibuang (jarang di puisi), sisanya 6 emosi. "Rindu" tetap sebagai EMOSI,
    sedangkan tema asmara bernama "Romansa", jadi keduanya tidak bertabrakan.
"""

SKIP = "skip"  # puisi yang tidak cocok dengan label mana pun: JANGAN dipaksa, lewati saja

TEMA = {
    "romansa": "cinta, asmara, hubungan dengan kekasih/pasangan (termasuk patah hati)",
    "alam": "alam sebagai pokok puisi (laut, hujan, gunung, musim, hutan), bukan sekadar latar",
    "sosial": "masyarakat, politik, kemiskinan, perjuangan, kebangsaan, kritik",
    "kehidupan": "renungan hidup, keseharian, keluarga, waktu, makna dan pertanyaan filosofis",
    "religius": "Tuhan, doa, iman, dosa, kematian dalam kerangka agama",
}

EMOSI = {
    "sedih": "duka, kehilangan, kecewa, luka",
    "rindu": "kerinduan pada seseorang/tempat/masa lalu",
    "bahagia": "senang, syukur, kehangatan, jatuh cinta",
    "harapan": "optimis, tekad, semangat, menatap ke depan",
    "tenang": "damai, teduh, pasrah, hening, merenung tenang",
    "marah": "amarah, protes, getir, perlawanan",
}

TEMA_LIST = list(TEMA)
EMOSI_LIST = list(EMOSI)

# Kata kunci HANYA untuk membantu pengambilan sampel yang beragam (bukan label!).
KEYWORDS = {
    "religius": set("""tuhan allah doa berdoa surga neraka iman takdir ampun rahmat sujud shalat salat
        dosa akhirat ibadah ayat nabi zikir syukur illahi ilahi gusti rabb amin""".split()),
    "sosial": set("""rakyat negeri bangsa merdeka perang miskin penguasa lapar buruh korupsi kemerdekaan
        pahlawan pemerintah politik rezim petani nelayan tanah-air tanah air derita penjajah""".split()),
    "alam": set("""hujan laut gunung angin senja pohon sungai bulan bintang hutan embun fajar ombak pantai
        langit awan daun bunga sawah kabut musim""".split()),
    "romansa": set("""cinta kekasih sayang kasih mencintai cintaku merindukan kecup pelukan hatiku jatuh
        pacar rindu mantan kenangan""".split()),
}
