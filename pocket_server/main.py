import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

import chromadb
from fastapi import FastAPI
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sqlite_utils import Database


class BookmarkItem(BaseModel):
    url: str
    title: str
    excerpt: Optional[str] = ""
    tags: Optional[List[str]] = []
    id: Optional[str] = None


# 建立 FastAPI 應用，FastAPI 是一個用於建立高效能 API 的 Python 框架
app = FastAPI()

# CORS Middleware 支援，允許 Chrome Extension 或本機網頁應用發送跨來源請求
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 若要更嚴格可指定 localhost 或 extension id
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# 初始化 SQLite 資料庫，使用 sqlite_utils 方便操作 SQLite，資料庫檔案為 bookmarks.db
db = Database("bookmarks.db")

# 初始化 Chroma 客戶端，用於向向量資料庫寫入和查詢資料
# Chroma 使用 duckdb+parquet 作為儲存引擎，資料會持久化存在 ./chroma 目錄
chroma_client = chromadb.PersistentClient(path="./chroma")

# 取得或建立名為 "bookmarks" 的集合(collection)，用於管理書籤向量資料
collection = chroma_client.get_or_create_collection("bookmarks")


def ensure_bookmarks_schema():
    if "bookmarks" not in db.table_names():
        db["bookmarks"].create(
            {
                "id": "TEXT",
                "url": "TEXT",
                "title": "TEXT",
                "excerpt": "TEXT",
                "tags": "TEXT",
                "created_at": "TEXT",
            },
            pk="id")
    else:
        table = db["bookmarks"]
        columns = table.columns_dict
        if "title" not in columns:
            table.add_column("title", "TEXT")
        if "excerpt" not in columns:
            table.add_column("excerpt", "TEXT")
        if "tags" not in columns:
            table.add_column("tags", "TEXT")
        if "created_at" not in columns:
            table.add_column("created_at", "TEXT")


# 定義 POST 方法的 /sync API 路由，負責接收書籤同步的請求
@app.post("/sync")
async def sync_bookmarks(payload: List[BookmarkItem]):
    if not isinstance(payload, list) or not payload:
        return {"success": False, "message": "書籤列表為空或格式不正確"}

    ensure_bookmarks_schema()

    saved = []

    for item in payload:
        url = item.url

        # 嘗試找出資料庫中是否已有相同 URL 的紀錄
        existing_rows = list(db["bookmarks"].rows_where("url = ?", [url]))
        if existing_rows:
            continue  # 若已存在該 URL，則跳過（不覆蓋）

        title = item.title
        excerpt = item.excerpt or ""
        tags = item.tags or []
        tags_json = json.dumps(tags)
        if not isinstance(tags_json, str):
            tags_json = json.dumps(tags_json)

        id = item.id or str(uuid.uuid4())
        id = str(id)
        created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

        # 將資料寫入 SQLite 資料庫（upsert by id）
        db["bookmarks"].upsert(
            {
                "id": str(id),
                "url": str(url),
                "title": str(title),
                "excerpt": str(excerpt),
                "tags": tags_json,  # 確保為字串並且重新序列化 tags
                "created_at": created_at
            },
            pk="id")

        # 建立向量內容（標題 + 摘錄）
        content = f"{title}\n\n{excerpt}" if excerpt else title

        # 將向量與 metadata 寫入向量資料庫
        collection.upsert(documents=[content],
                          ids=[id],
                          metadatas=[{
                              "url": url,
                              "title": title,
                              "tags": json.dumps(tags),
                              "created_at": created_at
                          }])

        saved.append(id)

    return {"success": True, "synced": saved}


# 前端瀏覽頁面，提供搜尋功能
@app.get("/")
async def index_page():
    return FileResponse(BASE_DIR / "templates" / "index.html")


# 書籤資料 API，回傳 id、url、title、excerpt、tags
@app.get("/bookmarks")
async def get_bookmarks():
    ensure_bookmarks_schema()
    rows = []
    for row in db["bookmarks"].rows_where("1=1",
                                          order_by="created_at desc, rowid desc"):
        # tags 欄位可能是 JSON 字串，轉為逗號分隔字串
        tags = row.get("tags", "")
        if isinstance(tags, str):
            try:
                tags_list = json.loads(tags)
                if isinstance(tags_list, list):
                    tags = ", ".join(tags_list)
            except Exception:
                pass
        rows.append({
            "id": row.get("id"),
            "url": row.get("url"),
            "title": row.get("title"),
            "excerpt": row.get("excerpt", ""),
            "tags": tags,
            "created_at": row.get("created_at")
        })
    return JSONResponse(rows)
