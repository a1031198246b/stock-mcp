import pytest
import respx
from stock_mcp.adapters.eastmoney import EastmoneyAdapter


@pytest.mark.asyncio
async def test_get_news_eastmoney():
    """模拟东财公告 API (np-anotice-stock 端点)

    真实响应字段:
    - art_code: 公告 ID
    - title: 公告标题
    - notice_date / display_time: 发布时间
    - columns: 栏目分类
    - codes: 关联股票
    """
    sample = {
        "data": {
            "list": [
                {
                    "art_code": "AN202606021823168597",
                    "title": "贵州茅台2025年度股东会会议资料",
                    "notice_date": "2026-06-03 00:00:00",
                    "display_time": "2026-06-02 20:07:18",
                    "columns": [{"column_name": "股东大会资料"}],
                    "codes": [{"short_name": "贵州茅台"}],
                },
                {
                    "art_code": "AN202606021823168600",
                    "title": "贵州茅台关于回购股份的公告",
                    "notice_date": "2026-05-28 00:00:00",
                    "display_time": "2026-05-28 18:00:00",
                    "columns": [{"column_name": "股份变动"}],
                    "codes": [{"short_name": "贵州茅台"}],
                },
            ]
        }
    }
    with respx.mock() as router:
        router.get(url__regex=r".*np-anotice-stock\.eastmoney\.com.*").respond(200, json=sample)
        a = EastmoneyAdapter()
        news = await a.get_news("600519", limit=10)
        assert len(news) == 2
        assert news[0].title == "贵州茅台2025年度股东会会议资料"
        # source 现在来自 columns[0].column_name
        assert news[0].source == "股东大会资料"
        # URL 应该是 detail 页
        assert "AN202606021823168597" in news[0].url
        # 时间
        assert news[0].publish_time.year == 2026
