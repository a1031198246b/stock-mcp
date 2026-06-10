import pytest
import respx
from stock_mcp.adapters.eastmoney import EastmoneyAdapter


@pytest.mark.asyncio
async def test_get_news_eastmoney():
    # 模拟东财新闻 API
    sample = {
        "data": {
            "list": [
                {
                    "title": "贵州茅台发布分红公告",
                    "url": "https://example.com/news/1",
                    "showTime": "2026-06-10 10:30:00",
                    "mediaName": "证券时报",
                },
                {
                    "title": "白酒板块走强",
                    "url": "https://example.com/news/2",
                    "showTime": "2026-06-10 09:15:00",
                    "mediaName": "上海证券报",
                },
            ]
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*push2.*eastmoney.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        news = await a.get_news("600519", limit=10)
        assert len(news) == 2
        assert news[0].title == "贵州茅台发布分红公告"
        assert news[0].source == "证券时报"
