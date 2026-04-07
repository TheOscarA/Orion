import os
import requests

def get_news():
    api_key = os.getenv("NEWSAPI_KEY")
    if not api_key:
        raise RuntimeError("NEWSAPI_KEY environment variable is required to fetch news.")

    news_headlines = []
    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "sources": "bbc-news",
        "apiKey": api_key,
    }
    result = requests.get(url, params=params).json()
    articles = result.get("articles", [])
    for article in articles:
        news_headlines.append(article.get("title", ""))
    return news_headlines[:6]