"""Uji sederhana modul sentiment lexicon Puitika."""
from sentiment_analysis import analyze_sentiment


def test_positive():
    result = analyze_sentiment("Aku bahagia, senang, bersyukur dan tersenyum")
    assert result["polarity"] == "positif", result


def test_negative():
    result = analyze_sentiment("Aku sedih, terluka, kecewa dan menangis")
    assert result["polarity"] == "negatif", result


def test_mixed():
    result = analyze_sentiment("Aku bahagia namun terluka dan kecewa")
    assert result["polarity"] == "campuran", result


def test_neutral():
    result = analyze_sentiment("Burung terbang di atas pohon dekat sungai")
    assert result["polarity"] == "tidak_terdeteksi", result
    assert result["has_lexicon_evidence"] is False


def test_negation():
    result = analyze_sentiment("Aku tidak bahagia")
    assert result["polarity"] == "negatif", result


def test_stanzas():
    result = analyze_sentiment("Aku bahagia\n\nAku sedih")
    assert len(result["stanzas"]) == 2, result


if __name__ == "__main__":
    tests = [test_positive, test_negative, test_mixed, test_neutral, test_negation, test_stanzas]
    for test in tests:
        test()
        print(f"LULUS: {test.__name__}")
    print("Semua uji sentiment analysis lulus.")
