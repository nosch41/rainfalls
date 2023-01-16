import datetime as dt
import logging
from typing import List, Optional
from urllib.parse import parse_qs as parse_querystring

import pandas as pd
from constants import DATASET_PATH, ONE_HOUR_IN_SECONDS
from fastapi import FastAPI, Query, Request, Response
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi_cache import FastAPICache
from fastapi_cache.backends.inmemory import InMemoryBackend
from fastapi_cache.decorator import cache
from models import DataFrameDBClient
from utils import cache_key_with_query_params, datetime_to_posix_timestamp_seconds, calc_days_in_interval, round_to_min_digits

log = logging.getLogger(__name__)
app = FastAPI(title="Gummistiefel B")
app.add_middleware(GZipMiddleware)

db_client = DataFrameDBClient()


@app.on_event("startup")
async def startup_event():
    db_client.initialize_database_from_path(dataset_path=DATASET_PATH)
    FastAPICache.init(InMemoryBackend(), prefix="cache")


@app.get("/")
async def hello_world():
    return {"Hello": "World"}


@app.get("/detail/{id}")
async def detail(id: int):
    data = db_client.get_event_by_id(event_id=id)

    if data is None:
        return Response(f"Event with ID {id} was not found", status_code=404)

    return data


@app.get("/query", response_class=JSONResponse)
@cache(expire=ONE_HOUR_IN_SECONDS, key_builder=cache_key_with_query_params)
async def query(
    request: Request,
    response: Response,
    filter_params: Optional[str] = "",
    fields: Optional[List[str]] = Query(None),
    limit: Optional[int] = None,
):
    """
    Query the Database on the Fulltext Search index and return the specified fields
    of all matching documents. Optionally limit the results.


    Example URL:
    /query?length__lte=1&severity_index__gt=0&fields=area&fields=length&limit=200

    Will parse to:
    filters = [[length, lte, 1], [severity_index, gt, 0]]
    fields  = [area, length]
    limit   = 200
    """

    query_string = filter_params or str(request.query_params)
    query_params = parse_querystring(query_string)

    query_params.pop("limit", None)
    query_params.pop("fields", None)

    fields = fields or ["event_id", "area", "length", "severity_index", "start_time"]
    filters = [key.split("__") + value for key, value in query_params.items()]

    try:
        count, data = db_client.query_events(
            filters=filters,
            limit=limit,
            fields=fields,
        )
    except Exception as exc:
        log.error(str(exc))
        response.status_code = 400
        return {"error": f"Invalid query. Check the console for details.\n{str(exc)}"}

    return {"count": count, "results": data}


@app.get("/overview")
@cache(expire=ONE_HOUR_IN_SECONDS, key_builder=cache_key_with_query_params)
async def overview(
    request: Request,
    response: Response,
    bins: Optional[int] = 20,
    filter_params: Optional[str] = "",
    fields: Optional[List[str]] = Query(None),
    limit: Optional[int] = None,
):
    query_string = filter_params or str(request.query_params)
    query_params = parse_querystring(query_string)

    query_params.pop("limit", None)
    query_params.pop("fields", None)

    fields = fields or ["start", "area", "length", "severity_index"]
    fields = [i for i in fields if i in ["area", "length", "severity_index"]]
    fields.append("start")

    filters = [key.split("__") + value for key, value in query_params.items()]

    try:
        count, data = db_client.query_events(
            filters=filters,
            limit=limit,
            fields=fields,
        )
    except Exception as exc:
        log.error(str(exc))
        response.status_code = 400
        return {"error": f"Invalid query. Check the console for details.\n{str(exc)}"}

    fields.remove("start")
    bins = bins if bins < len(data) else len(data)
    limit = count // bins
    stat_values = {}
    for field in fields: 
        stat_values[field] = []

    for i in range(bins):
        stat_data = data[i * limit : (i + 1) * limit + 1]
        stat_df = pd.DataFrame(stat_data)
        stat_mean = stat_df.mean(numeric_only=True)
        stat_q = stat_df.quantile(0.99, numeric_only=True)
        for field in fields: 
            stat_values[field].append(
                {
                    "mean": stat_mean[field],
                    "quantile": stat_q[field],
                    "start_time": stat_data[0]["start"],
                }
            )

    all_data = pd.DataFrame(data)
    outlier_q = all_data.quantile(0.999, numeric_only=True)

    outlier = {}
    for field in fields: 
        outlier[field] = all_data.loc[all_data[field] > outlier_q[field]].to_dict("records")

    return { "stat": stat_values, "outliers": outlier }


@app.get("/spider")
@cache(expire=ONE_HOUR_IN_SECONDS, key_builder=cache_key_with_query_params)
async def spider(
    request: Request,
    response: Response,
    intervalA: str,
    intervalB: str,
    filter_params: Optional[str] = "",
    limit: Optional[int] = None,
):
    intervalA = intervalA.split("--")
    intervalB = intervalB.split("--")

    if (len(intervalA) != 2 or len(intervalB) != 2):
        response.status_code = 400
        return {"error": f"Invalid query. Make sure to insert two intervals with start and end timestamp."}
    
    query_string = filter_params or str(request.query_params)
    query_params = parse_querystring(query_string)

    query_params.pop("intervalA", None)
    query_params.pop("intervalB", None)
    query_params.pop("limit", None)
    query_params.pop("fields", None)

    filters = [key.split("__") + value for key, value in query_params.items()]

    try:
        count, data = db_client.query_events(
            filters=filters,
            limit=999999,
            fields=["start_time", "area", "length", "severity_index"],
        )
    except Exception as exc:
        log.error(str(exc))
        response.status_code = 400
        return {"error": f"Invalid query. Check the console for details.\n{str(exc)}"}

    data = pd.DataFrame(data)

    intervalAData = data[data["start_time"] >= datetime_to_posix_timestamp_seconds(intervalA[0])]
    intervalAData = intervalAData[intervalAData["start_time"] < datetime_to_posix_timestamp_seconds(intervalA[1])]

    intervalBData = data[data["start_time"] >= datetime_to_posix_timestamp_seconds(intervalB[0])]
    intervalBData = intervalBData[intervalBData["start_time"] < datetime_to_posix_timestamp_seconds(intervalB[1])]

    intervalAData = intervalAData.mean(numeric_only=True).round(5)
    intervalBData = intervalBData.mean(numeric_only=True).round(5)
    
    intervalAData["events_per_day"] = round(len(intervalAData.index) / calc_days_in_interval(intervalA), 5)
    intervalBData["events_per_day"] = round(len(intervalBData.index) / calc_days_in_interval(intervalB), 5)

    totalMax = {}
    intervalASeries = []
    intervalBSeries = []

    for field in ["severity_index", "length", "area", "events_per_day"]:
        valueA = round_to_min_digits(intervalAData[field])
        valueB = round_to_min_digits(intervalBData[field])
        totalMax[field] = max(valueA, valueB)
        intervalASeries.append(valueA),
        intervalBSeries.append(valueB)
    
    return {
        "max": totalMax,
        "series": {
            "intervalA": intervalASeries,
            "intervalB": intervalBSeries
        }        
    }
