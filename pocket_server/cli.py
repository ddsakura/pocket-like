import chromadb
import click

chroma_client = chromadb.PersistentClient(path="./chroma")
collection = chroma_client.get_or_create_collection("bookmarks")


@click.group()
def cli():
    pass


@cli.command()
@click.argument("query")
@click.option("--tags", help="過濾指定標籤（用逗號分隔）", default=None)
@click.option("--limit", help="最多回傳幾筆結果", default=5)
def search(query, tags, limit):
    result = collection.query(query_texts=[query], n_results=limit)
    for doc, meta in zip(result["documents"][0], result["metadatas"][0]):
        if tags:
            tag_list = tags.split(",")
            if not any(tag in meta.get("tags", "") for tag in tag_list):
                continue
        print(f"- {meta['title']} ({meta['url']})")


@cli.command()
def dump_all():
    """列出所有書籤"""
    all_results = collection.get()
    for doc, meta in zip(all_results["documents"], all_results["metadatas"]):
        tags = ", ".join(meta.get("tags", [])) if isinstance(
            meta.get("tags"), list) else meta.get("tags", "")
        print(f"- {meta['title']} ({meta['url']}) [tags: {tags}]")


@cli.command()
@click.argument("url")
def excerpt_content(url):
    """從 Readability API 擷取主文內容"""
    import requests

    try:
        response = requests.get(f"http://localhost:3000/readability?url={url}")
        response.raise_for_status()
        data = response.json()
        print(
            f"\n✅ 擷取成功:\n\nTitle: {data.get('title')}\nContent:\n{data.get('content')[:500]}...\n"
        )
    except Exception as e:
        print(f"❌ 擷取失敗: {e}")


@cli.command()
def backfill_excerpts():
    """為尚未擷取內容的書籤補上 extract 並更新 chromadb"""
    import subprocess
    import time

    import requests
    import sqlite_utils

    try:
        import os
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


if __name__ == "__main__":
    cli()
