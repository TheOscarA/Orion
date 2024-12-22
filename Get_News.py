import requests

def get_news():
    news_hedline = []
    result = requests.get(f"https://newsapi.org/v2/top-headlines?country=us&category=general&apiKey=dd6b5daf6cf94451b0d01b24101e3b0c").json()
    articles = result["articles"]
    for article in articles:
        news_hedline.append(article["title"])
    return news_hedline[:6]
