"""Testes rápidos do analisador (sem chaves de API)."""

from analyzer import analyze_comment, resolve_coordinates, to_heatmap_point


def test_positive_sao_paulo():
    result = analyze_comment("Aqui em São Paulo a galera apoia demais!", use_llm=False)
    assert result["sentiment_label"] == "positivo"
    assert result["sentiment_score"] > 0.2
    assert "São Paulo" in result["detected_location"]
    assert result["lat"] == -23.5505


def test_uf_abbreviation():
    result = analyze_comment("Em SP apoiei demais!", use_llm=False)
    assert "São Paulo" in result["detected_location"]


def test_negative_sentiment():
    result = analyze_comment("Que vergonha, absurdo total em Curitiba.", use_llm=False)
    assert result["sentiment_label"] == "negativo"
    assert "Curitiba" in result["detected_location"]


def test_default_coordinates():
    coords = resolve_coordinates(None)
    assert coords["lat"] == -15.8267
    assert coords["lng"] == -47.9218


def test_heatmap_point_shape():
    analysis = analyze_comment("Recife torcendo! Excelente.", use_llm=False)
    point = to_heatmap_point({"text": "Recife torcendo! Excelente.", "author": "A"}, analysis)
    assert set(point) >= {"lat", "lng", "intensity", "sentiment", "text"}
    assert 0 <= point["intensity"] <= 1


if __name__ == "__main__":
    test_positive_sao_paulo()
    test_uf_abbreviation()
    test_negative_sentiment()
    test_default_coordinates()
    test_heatmap_point_shape()
    print("all tests passed")
