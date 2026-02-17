import json
import uuid
from typing import List, Optional

import chromadb
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
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

# 初始化 SQLite 資料庫，使用 sqlite_utils 方便操作 SQLite，資料庫檔案為 bookmarks.db
db = Database("bookmarks.db")

# 初始化 Chroma 客戶端，用於向向量資料庫寫入和查詢資料
# Chroma 使用 duckdb+parquet 作為儲存引擎，資料會持久化存在 ./chroma 目錄
chroma_client = chromadb.PersistentClient(path="./chroma")

# 取得或建立名為 "bookmarks" 的集合(collection)，用於管理書籤向量資料
collection = chroma_client.get_or_create_collection("bookmarks")


# 定義 POST 方法的 /sync API 路由，負責接收書籤同步的請求
@app.post("/sync")
async def sync_bookmarks(payload: List[BookmarkItem]):
    if not isinstance(payload, list) or not payload:
        return {"success": False, "message": "書籤列表為空或格式不正確"}

    if "bookmarks" not in db.table_names():
        db["bookmarks"].create(
            {
                "id": "TEXT",
                "url": "TEXT",
                "title": "TEXT",
                "excerpt": "TEXT",
                "tags": "TEXT"
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

        # 將資料寫入 SQLite 資料庫（upsert by id）
        db["bookmarks"].upsert(
            {
                "id": str(id),
                "url": str(url),
                "title": str(title),
                "excerpt": str(excerpt),
                "tags": tags_json  # 確保為字串並且重新序列化 tags
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
                              "tags": json.dumps(tags)
                          }])

        saved.append(id)

    return {"success": True, "synced": saved}


# 前端瀏覽頁面，提供搜尋功能
@app.get("/", response_class=HTMLResponse)
async def index_page():
    return """
    <!DOCTYPE html>
    <html lang="zh-Hant">
    <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Pocket-Like Bookmarks</title>
        <style>
            @import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;600;700;800&family=Space+Grotesk:wght@500;700&display=swap');

            :root {
                --bg: #f5f7fa;
                --card: #ffffffcc;
                --card-solid: #ffffff;
                --text: #101827;
                --muted: #506072;
                --accent: #1266f1;
                --accent-soft: #e9f0ff;
                --line: #d6dfeb;
                --ring: #9bc2ff;
                --chip: #eef4ff;
                --shadow: 0 14px 36px rgba(20, 38, 78, 0.08);
            }

            * { box-sizing: border-box; }

            body {
                margin: 0;
                color: var(--text);
                font-family: 'Manrope', sans-serif;
                background:
                    radial-gradient(circle at 12% 8%, #d6e7ff 0%, transparent 35%),
                    radial-gradient(circle at 88% 2%, #ffe8cd 0%, transparent 30%),
                    var(--bg);
                min-height: 100vh;
            }

            .shell {
                width: min(1080px, 94vw);
                margin: 28px auto 64px;
            }

            .hero {
                background: linear-gradient(120deg, #ffffffdd, #f4f8ffdd);
                border: 1px solid #ffffff;
                box-shadow: var(--shadow);
                border-radius: 24px;
                padding: 28px;
                backdrop-filter: blur(5px);
            }

            .title {
                margin: 0 0 8px;
                font-family: 'Space Grotesk', sans-serif;
                font-size: clamp(26px, 4vw, 40px);
                letter-spacing: -0.02em;
            }

            .subtitle {
                margin: 0;
                color: var(--muted);
                font-size: 15px;
            }

            .search-wrap {
                margin-top: 18px;
                display: grid;
                grid-template-columns: 1fr auto;
                gap: 10px;
            }

            #searchInput {
                width: 100%;
                border: 1px solid var(--line);
                border-radius: 14px;
                background: var(--card-solid);
                padding: 13px 14px;
                font-size: 15px;
                outline: none;
                transition: border-color .18s ease, box-shadow .18s ease;
            }

            #searchInput:focus {
                border-color: var(--accent);
                box-shadow: 0 0 0 4px var(--ring);
            }

            .clear-btn {
                border: 0;
                border-radius: 14px;
                background: var(--accent-soft);
                color: var(--accent);
                padding: 0 14px;
                font-weight: 700;
                cursor: pointer;
            }

            .stats {
                margin-top: 16px;
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
            }

            .stat-chip {
                background: var(--chip);
                color: #21457f;
                border-radius: 999px;
                padding: 7px 12px;
                font-size: 13px;
                font-weight: 700;
            }

            .grid {
                margin-top: 20px;
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
                gap: 14px;
            }

            .bookmark {
                background: var(--card);
                border: 1px solid #ffffff;
                box-shadow: var(--shadow);
                border-radius: 18px;
                padding: 16px;
                display: flex;
                flex-direction: column;
                gap: 10px;
                animation: rise .32s ease both;
            }

            .bookmark h3 {
                margin: 0;
                font-size: 18px;
                line-height: 1.35;
            }

            .url a {
                color: var(--accent);
                text-decoration: none;
                font-size: 13px;
                word-break: break-all;
            }

            .url a:hover { text-decoration: underline; }

            .excerpt {
                margin: 0;
                color: #34455a;
                font-size: 14px;
                line-height: 1.55;
            }

            .tags {
                display: flex;
                flex-wrap: wrap;
                gap: 8px;
            }

            button.tag {
                background: #f3f8ff;
                color: #31588f;
                border: 1px solid #d7e6ff;
                border-radius: 999px;
                padding: 5px 10px;
                cursor: pointer;
                font-size: 12px;
                font-weight: 700;
                transition: transform .12s ease, background .12s ease;
            }

            button.tag:hover {
                transform: translateY(-1px);
                background: #e6f0ff;
            }

            .empty {
                grid-column: 1 / -1;
                text-align: center;
                background: #ffffffb0;
                border: 1px dashed #bfd0e8;
                border-radius: 18px;
                padding: 26px 20px;
                color: var(--muted);
                font-weight: 600;
            }

            @keyframes rise {
                from { opacity: 0; transform: translateY(6px); }
                to { opacity: 1; transform: translateY(0); }
            }

            @media (max-width: 700px) {
                .shell { margin-top: 16px; }
                .hero { border-radius: 18px; padding: 18px; }
                .search-wrap { grid-template-columns: 1fr; }
                .clear-btn { padding: 10px; }
            }
        </style>
    </head>
    <body>
        <main class="shell">
            <section class="hero">
                <h1 class="title">My Reading Vault</h1>
                <p class="subtitle">收藏、搜尋、用標籤快速回到你最重要的內容。</p>

                <div class="search-wrap">
                    <input type="text" id="searchInput" placeholder="搜尋標題、摘要或標籤..." />
                    <button class="clear-btn" id="clearBtn" type="button">清除</button>
                </div>

                <div class="stats">
                    <span class="stat-chip" id="totalCount">共 0 筆</span>
                    <span class="stat-chip" id="shownCount">顯示 0 筆</span>
                </div>
            </section>

            <section class="grid" id="results"></section>
        </main>

        <script>
            let bookmarks = [];
            const searchInput = document.getElementById("searchInput");
            const clearBtn = document.getElementById("clearBtn");
            const totalCount = document.getElementById("totalCount");
            const shownCount = document.getElementById("shownCount");
            const results = document.getElementById("results");

            function normalizeTags(rawTags) {
                if (!rawTags) return [];
                return String(rawTags)
                    .split(',')
                    .map(tag => tag.trim())
                    .filter(Boolean);
            }

            function escapeHtml(str) {
                return String(str || "")
                    .replaceAll("&", "&amp;")
                    .replaceAll("<", "&lt;")
                    .replaceAll(">", "&gt;")
                    .replaceAll('"', "&quot;")
                    .replaceAll("'", "&#39;");
            }

            async function fetchBookmarks() {
                const res = await fetch('/bookmarks');
                bookmarks = await res.json();
                totalCount.textContent = `共 ${bookmarks.length} 筆`;
                render();
            }

            function render() {
                const q = searchInput.value.toLowerCase();
                const filtered = bookmarks.filter(b =>
                    b.title.toLowerCase().includes(q) ||
                    (b.excerpt || '').toLowerCase().includes(q) ||
                    (b.tags || '').toLowerCase().includes(q)
                );
                shownCount.textContent = `顯示 ${filtered.length} 筆`;

                if (!filtered.length) {
                    results.innerHTML = '<div class="empty">沒有符合條件的書籤，試試別的關鍵字。</div>';
                    return;
                }

                results.innerHTML = filtered.map((b, i) => {
                    const tagsHtml = normalizeTags(b.tags)
                        .map(tag => `<button class="tag" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`)
                        .join('');

                    return `
                        <article class="bookmark" style="animation-delay:${Math.min(i * 0.03, 0.4)}s">
                            <h3>${escapeHtml(b.title || "Untitled")}</h3>
                            <div class="url"><a href="${escapeHtml(b.url)}" target="_blank" rel="noopener noreferrer">${escapeHtml(b.url)}</a></div>
                            <p class="excerpt">${escapeHtml(b.excerpt || "沒有摘要")}</p>
                            <div class="tags">${tagsHtml}</div>
                        </article>
                    `;
                }).join('');

                results.querySelectorAll(".tag").forEach(btn => {
                    btn.addEventListener("click", () => {
                        searchInput.value = btn.dataset.tag || "";
                        render();
                    });
                });
            }

            searchInput.addEventListener("input", render);
            clearBtn.addEventListener("click", () => {
                searchInput.value = "";
                render();
            });
            fetchBookmarks();
        </script>
    </body>
    </html>
    """


# 書籤資料 API，回傳 id、url、title、excerpt、tags
@app.get("/bookmarks")
async def get_bookmarks():
    rows = []
    for row in db["bookmarks"].rows:
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
            "tags": tags
        })
    return JSONResponse(rows)
