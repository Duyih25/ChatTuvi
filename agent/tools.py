from langchain_core.tools import tool
from elasticsearch import Elasticsearch
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from dotenv import load_dotenv
from datetime import datetime
import calendar

import os
load_dotenv()
os.environ["GOOGLE_API_KEY"] = os.getenv('API_KEY')


INDEX_NAME =  os.getenv('INDEX_NAME')
INDEX_LOGS = os.getenv('INDEX_LOGS')
es_client = Elasticsearch("http://localhost:9200")
embedding_model = GoogleGenerativeAIEmbeddings(model="gemini-embedding-001")

@tool
def retrieve_tool(query: str, k=20) -> str:
    """Tool dùng để hỏi đáp về nội dung liên quan đến tử vi và cuốn sách tử vi trong database"""
    query_vector = embedding_model.embed_query(query, output_dimensionality = 768)
    search_query = {
    "size": k,
    "knn": {
        "field": "embedding",
        "query_vector": query_vector,
        "k": k,
        "num_candidates": k * 10,
        "boost": 0.7
    },
    "post_filter": {
        "bool": {
            "must_not": [
                {"match_phrase": {"summarize_meaning_text": "tôi xin lỗi"}},
                {"match_phrase": {"summarize_meaning_text": "bạn vui lòng"}}
            ]
        }
    }
}


    res = es_client.search(index=INDEX_NAME, body=search_query)
    results = [
        {"score": hit["_score"], "summarize": hit["_source"]["summarize_meaning_text"], "raw_text": hit["_source"]["raw_text"]}
        for hit in res["hits"]["hits"]
    ]
    return results

@tool
def statistic_tool(userId: str, year: int = None, month: int = None) -> dict:
    """Tool dùng để hỏi đáp về thống kê tần suất sử dụng trong 1 tháng.
    Nếu không cung cấp year, month thì mặc định dùng tháng hiện tại.
    """
    print("tooL bắt được rồi nhé ",userId)
    # Nếu không có year, month → mặc định lấy thời gian hiện tại
    now = datetime.now()
    if year is None:
        year = now.year
    if month is None:
        month = now.month

    start_date = datetime(year, month, 1)
    last_day = calendar.monthrange(year, month)[1]
    end_date = datetime(year, month, last_day, 23, 59, 59)

    body = {
        "size": 0,
        "query": {
            "bool": {
                "filter": [
                    {"term": {"userId": userId}},
                    {"range": {"created_at": {"gte": start_date.isoformat(), "lte": end_date.isoformat()}}}
                ]
            }
        },
        "aggs": {
            "days_used": {
                "date_histogram": {
                    "field": "created_at",
                    "calendar_interval": "day"
                }
            }
        }
    }
    
    resp = es_client.search(index=INDEX_LOGS, body=body)
    

    total_queries = resp["hits"]["total"]["value"]
    days_used = len(resp["aggregations"]["days_used"]["buckets"])
    usage_ratio = days_used / last_day

    print("agg xong", {
        "userId": userId,
        "year": year,
        "month": month,
        "total_queries": total_queries,
        "days_used": days_used,
        "days_in_month": last_day,
        "usage_ratio": usage_ratio
    })
    return {
        "userId": userId,
        "year": year,
        "month": month,
        "total_queries": total_queries,
        "days_used": days_used,
        "days_in_month": last_day,
        "usage_ratio": usage_ratio
    }