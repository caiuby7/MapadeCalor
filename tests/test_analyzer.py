import unittest

from backend.analyzer import SentimentAnalyzer, local_analysis


class LocalAnalysisTests(unittest.TestCase):
    def test_detects_positive_sentiment_and_capital(self) -> None:
        result = local_analysis("Excelente, adorei! Um abraço de São Paulo.")

        self.assertEqual(result.sentiment_label, "positivo")
        self.assertGreater(result.sentiment_score, 0)
        self.assertEqual(result.detected_location, "São Paulo, SP")
        self.assertAlmostEqual(result.lat, -23.5505)

    def test_detects_negative_sentiment_and_accented_capital(self) -> None:
        result = local_analysis("Que vergonha, péssimo. Estou em Belém.")

        self.assertEqual(result.sentiment_label, "negativo")
        self.assertLess(result.sentiment_score, 0)
        self.assertEqual(result.detected_location, "Belém, PA")

    def test_uses_brasilia_as_safe_default(self) -> None:
        result = local_analysis("Ainda estou pensando sobre o assunto.")

        self.assertEqual(result.sentiment_label, "neutro")
        self.assertEqual(result.detected_location, "Brasília, DF")


class AnalyzerTests(unittest.IsolatedAsyncioTestCase):
    async def test_works_without_llm_key(self) -> None:
        result = await SentimentAnalyzer(api_key=None).analyze(
            "Ótimo trabalho em Curitiba"
        )

        self.assertEqual(result.sentiment_label, "positivo")
        self.assertEqual(result.detected_location, "Curitiba, PR")


if __name__ == "__main__":
    unittest.main()
