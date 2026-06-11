import pytest

from stock_mcp.adapters.iwencai import IwencaiAdapter
from stock_mcp.domain.errors import DataSourceError
from stock_mcp.services.query_service import QueryService


def test_query_service_raises_when_iwencai_disabled():
    a = IwencaiAdapter()
    a.enabled = False
    svc = QueryService(a)
    import asyncio

    with pytest.raises(DataSourceError):
        asyncio.run(svc.query_stocks("ROE > 0.1"))
