# Pocket-like 書籤系統

這是一個類似 Pocket 的個人書籤儲存和管理系統，包含 Chrome 擴充功能和本地伺服器，使用向量資料庫進行全文搜尋。

## 專案架構

本專案包含三個主要組件：

1. **Chrome 擴充功能** - 快速儲存和管理書籤
2. **Python 同步伺服器** - 處理書籤資料的儲存和查詢
3. **Readability 伺服器** - 擷取網頁主要內容的 Node.js 服務

## 功能特點

- 📌 快速儲存當前瀏覽頁面的標題和網址
- 🔍 使用向量資料庫進行高效全文搜尋
- 🏷️ 支援標籤分類和管理
- 🤖 使用 Ollama 模型自動生成標籤推薦
- 📱 簡潔且固定高度的使用者介面
- 📊 本地 Web 界面查看和搜尋所有書籤
- 💾 使用 SQLite 和 Chroma 向量資料庫進行持久化存儲

## 安裝說明

### 1. 後端服務器

#### 安裝 Python 伺服器

```bash
cd pocket_server
pip install -r requirements.txt
```

#### 啟動 Python 伺服器

```bash
cd pocket_server
uvicorn main:app --reload --port 8000
```

#### 安裝和啟動 Readability 伺服器

```bash
cd readability
npm install
node readability-server.js
```

#### 安裝 Ollama (用於標籤生成功能)

若要使用自動標籤生成功能，需安裝 Ollama：

```bash
# macOS
brew install ollama

# 下載 gemma3 模型
ollama pull gemma3:latest
```

詳細安裝說明可參考 [Ollama 官方文件](https://ollama.com/download)。

### 2. Chrome 擴充功能

1. 開啟 Chrome 瀏覽器，前往 `chrome://extensions/`
2. 開啟「開發人員模式」
3. 點選「載入未封裝項目」
4. 選取 `pocket_chrome_extension` 資料夾

## 使用方式

### Chrome 擴充功能

- 點擊工具列中的擴充功能圖示，開啟彈出視窗
- 點擊「儲存目前頁面」將目前頁面加入書籤
- 使用搜尋框快速尋找已儲存的書籤
- 點擊「同步」將本地書籤上傳至伺服器

### 命令列工具

以下是可用的 CLI 命令：

```bash
cd pocket_server
python -m cli search "關鍵字" --tags "標籤" --limit 10  # 搜尋書籤
python -m cli dump-all                                 # 列出所有書籤
python -m cli excerpt-content "https://example.com"     # 擷取指定網頁的內容
python -m cli backfill-excerpts                        # 為已存在但沒有內容的書籤補充摘要
python -m cli backfill-tags                            # 為沒有標籤的書籤自動生成標籤
python -m cli suggest-tags "標題" "摘要"                # 使用 Ollama 模型為指定內容生成標籤建議
```

### 本地 Web 介面

開啟瀏覽器訪問 http://localhost:8000 查看和搜尋所有書籤。

## 技術棧

- **前端**: HTML, CSS, JavaScript (Chrome 擴充功能)
- **後端**:
  - Python (FastAPI)
  - Node.js (Readability 服務)
- **資料庫**:
  - SQLite (結構化資料存儲)
  - Chroma (向量資料庫，用於語義搜尋)
- **AI/ML**:
  - Ollama (本地 LLM 服務，用於自動標籤生成)
- **其他工具**:
  - Mozilla Readability (網頁內容提取)
  - Click (Python CLI 工具)

## 文件說明

### pocket_server/

- `main.py` - FastAPI 服務器，處理 API 請求
- `cli.py` - 命令行工具，提供本地操作功能，包括搜尋、內容擷取和自動標籤生成
- `requirements.txt` - Python 依賴列表
- `bookmarks.db` - SQLite 數據庫文件（自動創建）
- `chroma/` - Chroma 向量資料庫存儲目錄

### readability/

- `readability-server.js` - 提供網頁內容擷取服務
- `readability-fetch.js` - 命令行工具，用於測試內容擷取
- `package.json` - Node.js 依賴列表

### pocket_chrome_extension/

- `manifest.json` - Chrome 擴充功能定義
- `popup/` - 擴充功能彈出窗口的 HTML、CSS 和 JavaScript
- `icon.png` - 擴充功能圖標

## 開發說明

### 本地開發環境設置

1. 克隆倉庫
2. 安裝 Python 依賴
3. 安裝 Node.js 依賴
4. 啟動兩個服務器
5. 載入 Chrome 擴充功能

### 注意事項

- 確保 Python 伺服器在 8000 埠運行
- Readability 伺服器在 3000 埠運行
- Chrome 擴充功能同步時會連接 Python 伺服器
- CLI 命令使用 kebab-case 命名規範（例如 `backfill-excerpts` 而非 `backfill_excerpts`）
- 使用標籤生成功能前需確保 Ollama 已安裝並拉取必要的模型
