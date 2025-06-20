import os

os.environ["TOKENIZERS_PARALLELISM"] = "false"
#!/usr/bin/env python3
"""
CLI 工具，用於操作和管理書籤資料庫
"""

import json
import subprocess
import time

import chromadb
import click
import requests
import sqlite_utils

# 初始化 Chroma 客戶端並連接至書籤集合
chroma_client = chromadb.PersistentClient(path="./chroma")
collection = chroma_client.get_or_create_collection("bookmarks")


@click.group()
def cli():
    """書籤管理系統命令行工具"""
    pass


@cli.command()
@click.argument("query")
@click.option("--tags", help="過濾指定標籤（用逗號分隔）", default=None)
@click.option("--limit", help="最多回傳幾筆結果", default=5)
def search(query, tags, limit):
    """以關鍵字和標籤搜尋書籤"""
    result = collection.query(query_texts=[query], n_results=limit)
    for doc, meta in zip(result["documents"][0], result["metadatas"][0]):
        if tags:
            tag_list = tags.split(",")
            if not any(tag in meta.get("tags", "") for tag in tag_list):
                continue
        print(f"- {meta['title']} ({meta['url']})")


@cli.command(name="dump-all")
def dump_all():
    """列出所有書籤"""
    all_results = collection.get()
    for doc, meta in zip(all_results["documents"], all_results["metadatas"]):
        tags = ", ".join(meta.get("tags", [])) if isinstance(
            meta.get("tags"), list) else meta.get("tags", "")
        print(f"- {meta['title']} ({meta['url']}) [tags: {tags}]")


@cli.command(name="excerpt-content")
@click.argument("url")
def excerpt_content(url):
    """從 Readability API 擷取主文內容"""
    try:
        response = requests.get(f"http://localhost:3000/readability?url={url}")
        response.raise_for_status()
        data = response.json()
        print(
            f"\n✅ 擷取成功:\n\nTitle: {data.get('title')}\nContent:\n{data.get('content')[:500]}...\n"
        )
    except Exception as e:
        print(f"❌ 擷取失敗: {e}")


@cli.command(name="backfill-excerpts")
def backfill_excerpts():
    """為尚未擷取內容的書籤補上 extract 並更新 chromadb"""
    try:
        script_path = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "readability",
                         "readability-server.js"))
        process = subprocess.Popen(["node", script_path])
        print("🚀 已啟動 readability-server.js，稍候啟動完成…")
        time.sleep(2)

        db = sqlite_utils.Database("bookmarks.db")
        table = db["bookmarks"]

        rows = list(table.rows_where("excerpt IS NULL OR excerpt = ''"))
        print(f"🔍 發現 {len(rows)} 筆待補內容的書籤")

        try:
            for row in rows:
                url = row["url"]
                id = row["id"]
                try:
                    response = requests.get(
                        f"http://localhost:3000/readability?url={url}")
                    response.raise_for_status()
                    data = response.json()
                    content = data.get("excerpt", "").strip()

                    if not content:
                        print(f"⚠️  {url} 擷取結果為空，略過")
                        continue

                    # 更新 SQLite
                    table.update(id, {"excerpt": content})

                    # 更新 ChromaDB
                    collection.upsert(documents=[content],
                                      ids=[id],
                                      metadatas=[{
                                          "url": url,
                                          "title": row["title"],
                                          "tags": row.get("tags", [])
                                      }])
                    print(f"✅ 已更新: {url}")
                except Exception as e:
                    print(f"❌ 擷取失敗 {url}: {e}")
        finally:
            process.terminate()
            print("🛑 已關閉 readability-server.js")
    except Exception as e:
        print(f"⚠️ 無法啟動 readability server: {e}")


def generate_tags_with_ollama(title, excerpt):
    """使用 Ollama 模型生成標籤，返回標籤列表"""
    import json
    import re
    import socket
    import subprocess
    import time

    def is_ollama_running():
        try:
            with socket.create_connection(("localhost", 11434), timeout=1):
                return True
        except OSError:
            return False

    if not is_ollama_running():
        print("Ollama not running, attempting to start it...")
        subprocess.Popen(["ollama", "serve"])
        time.sleep(3)  # wait a moment to let it start

    prompt = f"""
請根據下列標題與摘要建議 1 到 3 個標籤。請僅回傳一組結果，格式為 JSON 陣列（例如 ["AI", "教育"]），不要提供其他說明、文字或多組範例。

Title: {title}
Excerpt: {excerpt}
"""

    try:
        result = subprocess.run(["ollama", "run", "gemma3:latest"],
                                input=prompt.encode("utf-8"),
                                capture_output=True,
                                check=True)
        output = result.stdout.decode("utf-8").strip()
        match = re.search(r"\[.*?\]", output, re.DOTALL)
        if match:
            tags_json = match.group(0)
            tags = json.loads(tags_json)
            return tags
        else:
            print(f"⚠️ 無法解析標籤 JSON 陣列，原始輸出: {output}")
            return []
    except Exception as e:
        print(f"❌ 擷取標籤失敗: {e}")
        return []


@cli.command(name="backfill-tags")
def backfill_tags():
    """為尚未生成標籤的書籤補上 tag 並更新 chromadb"""
    db = sqlite_utils.Database("bookmarks.db")
    table = db["bookmarks"]
    rows = list(
        table.rows_where(
            "((tags IS NULL OR tags = '' OR tags = '[]') AND (excerpt IS NOT NULL AND excerpt != ''))"
        ))

    print(f"🔍 發現 {len(rows)} 筆待補標籤的書籤")

    for row in rows:
        tags = generate_tags_with_ollama(row['title'], row['excerpt'])
        if tags:
            # 更新 SQLite
            table.update(row["id"], {"tags": tags})

            # 更新 Chroma
            collection.upsert(documents=[row["excerpt"]],
                              ids=[row["id"]],
                              metadatas=[{
                                  "url": row["url"],
                                  "title": row["title"],
                                  "tags": ", ".join(tags)
                              }])
            print(f"✅ 已為 {row['url']} 建立標籤: {tags}")
        else:
            print(f"⚠️ 無法為 {row['url']} 生成標籤，略過")


@cli.command(name="suggest-tags")
@click.argument("title")
@click.argument("excerpt")
def suggest_tags(title, excerpt):
    """使用 Ollama 的 mixtral 模型建議標籤"""
    tags = generate_tags_with_ollama(title, excerpt)
    if tags:
        print("📌 建議標籤:")
        print(json.dumps(tags, ensure_ascii=False))
    else:
        print("⚠️ 無法產生有效標籤。")


if __name__ == "__main__":
    # 執行命令列介面
    cli()
