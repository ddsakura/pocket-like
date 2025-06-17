document.getElementById("save-button").addEventListener("click", async () => {
  chrome.tabs.query({ active: true, currentWindow: true }, async (tabs) => {
    const tab = tabs[0];
    const url = tab.url;
    let title = tab.title;
    let excerpt = "";

    // try {
    //   const res = await fetch("http://localhost:3000/readability?url=" + encodeURIComponent(url));
    //   const data = await res.json();
    //   title = data.title || title;
    //   excerpt = data.excerpt || "";
    // } catch (e) {
    //   excerpt = "(⚠️ 無法取得主文內容，只儲存網址與標題)";
    //   alert("⚠️ 無法取得文章全文，僅儲存標題與網址。如需全文摘要，請啟動本機 Readability server。");
    // }

    chrome.storage.local.get(["bookmarks"], (result) => {
      let bookmarks = result.bookmarks || [];
      if (bookmarks.some(b => b.url === url)) {
        alert("⚠️ 這個網址已經儲存過了！");
        return;
      }
      bookmarks.unshift({ url, title, excerpt, tags: [], created_at: new Date().toISOString() });
      chrome.storage.local.set({ bookmarks }, () => renderBookmarks(bookmarks));
    });
  });
});

document.getElementById("search-box").addEventListener("input", () => {
  const query = document.getElementById("search-box").value.toLowerCase();
  chrome.storage.local.get(["bookmarks"], (result) => {
    const bookmarks = result.bookmarks || [];
    const filtered = bookmarks.filter(b =>
      b.title.toLowerCase().includes(query) || b.excerpt.toLowerCase().includes(query)
    );
    renderBookmarks(filtered);
  });
});

function renderBookmarks(bookmarks) {
  const list = document.getElementById("bookmark-list");
  list.innerHTML = "";
  bookmarks.forEach((b, index) => {
    const div = document.createElement("div");
    div.className = "bookmark";
    div.innerHTML = `
      <h4><a href="${b.url}" target="_blank">${b.title}</a></h4>
      <button data-index="${index}" class="delete-button">🗑️ 刪除</button>
    `;
    list.appendChild(div);
  });

  document.querySelectorAll(".delete-button").forEach(btn => {
    btn.addEventListener("click", () => {
      const index = parseInt(btn.getAttribute("data-index"));
      chrome.storage.local.get(["bookmarks"], (result) => {
        let bookmarks = result.bookmarks || [];
        bookmarks.splice(index, 1);
        chrome.storage.local.set({ bookmarks }, () => renderBookmarks(bookmarks));
      });
    });
  });
}


chrome.storage.local.get(["bookmarks"], (result) => renderBookmarks(result.bookmarks || []));

// 新增「同步」按鈕事件處理
document.getElementById("sync-button").addEventListener("click", async () => {
  chrome.storage.local.get(["bookmarks"], async (result) => {
    const bookmarks = result.bookmarks || [];
    try {
      const res = await fetch("http://localhost:8000/sync", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify(bookmarks.map(b => ({
          url: b.url,
          title: b.title,
          excerpt: b.excerpt,
          tags: b.tags || []
        })))
      });
      if (res.ok) {
        alert(`✅ 同步完成，共 ${bookmarks.length} 筆書籤已上傳`);
        chrome.storage.local.remove("bookmarks", () => {
          renderBookmarks([]);
        });
      } else {
        const err = await res.text();
        alert("❌ 同步失敗：" + err);
      }
    } catch (e) {
      console.error("同步失敗：", e);
      alert("❌ 發生錯誤，請確認 API 是否啟動");
    }
  });
});
