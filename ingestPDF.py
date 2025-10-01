from pypdf import PdfReader
from langchain_google_genai import GoogleGenerativeAIEmbeddings, GoogleGenerativeAI
from elasticsearch import Elasticsearch
from dotenv import load_dotenv
import os
import re
import time
from tqdm import tqdm


class PDFProcessor:
    def __init__(self, es_host="http://localhost:9200", dims=768):
        self.es = Elasticsearch(es_host)
        self.embeddings = GoogleGenerativeAIEmbeddings(model="models/gemini-embedding-001")
        self.summarizer = GoogleGenerativeAI(model="models/gemini-2.0-flash")  # dùng để tóm tắt
        self.dims = dims

    def create_index(self, index_name):
        if self.es.ping():
            print("Elasticsearch is running and accessible.")
        else:
            print("Elasticsearch client could not ping the server.")
            
        if not self.es.indices.exists(index=index_name):
            mapping = {
                "mappings": {
                    "properties": {
                        "raw_text": {"type": "text"},
                        "summarize_meaning_text": {"type": "text"},
                        "embedding": {
                            "type": "dense_vector",
                            "dims": self.dims,
                            "index": True,
                            "similarity": "cosine"
                        }
                    }
                }
            }
            self.es.indices.create(index=index_name, body=mapping)
            print(f"Created index: {index_name}")

    def split_by_sections(self, text: str):
        sections = re.split(r"\n([A-ZĂÂÁÀẢẠẤẦẨẬẮẰẲẶÊÉÈẺẸẾỀỂỆÔƠÓÒỎỌỐỒỔỘỚỜỞỢƯÚÙỦỤỨỪỬỰĐ\s]+)\n", text)
        
        result = []
        current_title = "INTRO"
        buffer = []

        for i, part in enumerate(sections):
            if i % 2 == 1:  # tiêu đề
                if buffer:
                    result.append((current_title, "\n".join(buffer)))
                    buffer = []
                current_title = part.strip()
            else:  # nội dung
                if part.strip():
                    buffer.append(part.strip())

        if buffer:
            result.append((current_title, "\n".join(buffer)))

        return result

    def summarize(self, text: str) -> str:
        try:
            prompt = f"Tóm tắt ngắn gọn và giữ ý chính của đoạn văn sau:\n\n{text}"
            resp = self.summarizer.invoke(prompt)
            return resp.strip()
        except Exception as e:
            print(f"Summarize error: {e}")
            return text[:500]  # fallback: lấy đoạn đầu

    def process_pdf(self, path, index_name):
        """Đọc PDF, chia section, summarize, embed và push vào Elasticsearch"""
        self.create_index(index_name)
        reader = PdfReader(path)

        full_text = ""
        for page in reader.pages:
            txt = page.extract_text()
            if txt:
                full_text += txt + "\n"

        sections = self.split_by_sections(full_text)
        print(f"Found {len(sections)} sections")

        doc_id = 0
        for title, raw_text in tqdm(sections):
            try_times = 3
            while try_times > 0:
                try:
                    summarized = self.summarize(raw_text)
                    vector = self.embeddings.embed_query(summarized, output_dimensionality=self.dims)
                    body = {
                        "raw_text": raw_text,
                        "summarize_meaning_text": summarized,
                        "embedding": vector,
                    }

                    # index
                    self.es.index(index=index_name, id=f"{doc_id}", body=body)
                    doc_id += 1
                    break 

                except Exception as e:
                    try_times -= 1
                    time.sleep(10)

        print(f"Done ingesting {doc_id} sections into {index_name}")



if __name__ == "__main__":
    load_dotenv()
    os.environ["GOOGLE_API_KEY"] = os.getenv("API_KEY")
    INDEX_NAME = os.getenv("INDEX_NAME")

    processor = PDFProcessor()
    processor.process_pdf("data/58_TU_VI_THUC_HANH.pdf", index_name=INDEX_NAME)
