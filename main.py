from elasticsearch import Elasticsearch
from datetime import datetime
from langchain_core.messages import HumanMessage
from graph import build_graph
import uuid
from dotenv import load_dotenv
import os
load_dotenv()

es = Elasticsearch("http://localhost:9200")
INDEX_LOGS = os.getenv('INDEX_LOGS')

# Tạo index mapping nếu chưa có
if not es.indices.exists(index=INDEX_LOGS):
    mapping = {
        "mappings": {
            "properties": {
                "userId": {"type": "keyword"},
                "sessionId": {"type": "keyword"},
                "question": {"type": "text"},
                "created_at": {
                    "type": "date",
                    "format": "strict_date_optional_time||epoch_millis"
                }
            }
        }
    }
    es.indices.create(index=INDEX_LOGS, body=mapping)
    print(f"Created index {INDEX_LOGS}")


def log_query(userId: str, sessionId: str, question: str):
    """Ghi log câu hỏi vào Elasticsearch"""
    body = {
        "userId": userId,
        "sessionId": sessionId,
        "question": question,
        "created_at": datetime.utcnow()
    }
    es.index(index=INDEX_LOGS, document=body)


app = build_graph()

user_id = input("userId của bạn: ")
session_id = str(uuid.uuid4())

state = {"messages": [], "userId": user_id, "sessionId": session_id}

print(f"Bắt đầu chat (userId={user_id}, sessionId={session_id}), gõ 'exit chat' để thoát:")

while True:
    string_input = input("Bạn: ").strip()
    if string_input.lower() == "exit chat":
        print("Kết thúc chat.")
        break

    # Thêm message mới vào state
    state["messages"].append(HumanMessage(content=string_input))

    # Gọi app với state hiện tại
    state = app.invoke(state)

    # Log lại vào Elasticsearch
    log_query(user_id, session_id, string_input)

    # Lấy câu trả lời cuối cùng
    print("Bot:", state["messages"][-1].content)
