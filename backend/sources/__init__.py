"""Coletores por fonte de dados."""

from sources.bluesky import collect_bluesky
from sources.news import collect_news
from sources.reddit import collect_reddit
from sources.youtube import collect_youtube

__all__ = ["collect_youtube", "collect_bluesky", "collect_reddit", "collect_news"]
