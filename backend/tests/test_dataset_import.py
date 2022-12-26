import json

import pytest
import pytest_asyncio

from app.constants import REDIS_TEST_URL
from app.models import RedisJSONClient, WeatherEvent


@pytest.fixture()
def json_data():
    return {
        1: {
            "id": 1,
            "area": 1,
            "length": 1,
            "si": 1,
            "start": "2022-01-01T00:00:00+00:00",
            "timeseries": [],
            "meanLat": 1,
            "meanLon": 1,
            "meanPrec": 1,
            "maxPrec": 1,
        },
        2: {
            "id": 2,
            "area": 2,
            "length": 2,
            "si": 2,
            "start": "2022-02-02T00:00:00+00:00",
            "timeseries": [],
            "meanLat": 2,
            "meanLon": 2,
            "meanPrec": 2,
            "maxPrec": 2,
        },
    }


@pytest.fixture()
def dataset(json_data):
    return (WeatherEvent.from_dict(event) for event in json_data.values())


@pytest_asyncio.fixture()
async def redis_test_client(dataset):
    client = RedisJSONClient(redis_url=REDIS_TEST_URL)

    await client.initialize_database(dataset=dataset)

    yield client

    await client.aioredis.close()


@pytest.mark.asyncio
async def test_data_import(redis_test_client, dataset):

    assert await redis_test_client.key_exists(1)
    assert await redis_test_client.key_exists(2)

    result = await redis_test_client.get_key_json(1)
    result = json.loads(result)

    assert result == {
        "event_id": 1,
        "area": 1,
        "length": 1,
        "severity_index": 1,
        "start_time": 1640995200,
        "timeseries": [],
        "mean_lat": 1,
        "mean_lon": 1,
        "mean_prec": 1,
        "max_prec": 1,
    }
