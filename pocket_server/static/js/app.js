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
        .map((tag) => tag.trim())
        .filter(Boolean);
}

function escapeHtml(str) {
    return String(str || "")
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#39;");
}

function sanitizeUrl(url) {
    const value = String(url || "").trim();
    if (!value) return "";
    try {
        const parsed = new URL(value);
        if (parsed.protocol === "http:" || parsed.protocol === "https:") {
            return value;
        }
        return "";
    } catch {
        return "";
    }
}

async function fetchBookmarks() {
    try {
        const res = await fetch('/bookmarks');
        if (!res.ok) {
            throw new Error(`Failed to load bookmarks: ${res.status} ${res.statusText}`);
        }
        bookmarks = await res.json();
        totalCount.textContent = `共 ${bookmarks.length} 筆`;
        render();
    } catch (err) {
        console.error("Error fetching bookmarks:", err);
        bookmarks = [];
        totalCount.textContent = "共 0 筆";
        shownCount.textContent = "顯示 0 筆";
        results.innerHTML = '<div class="empty">無法載入書籤，請稍後再試或檢查伺服器狀態。</div>';
    }
}

function render() {
    const q = searchInput.value.toLowerCase();
    const filtered = bookmarks.filter((b) =>
        (b.title || "").toLowerCase().includes(q) ||
        (b.excerpt || '').toLowerCase().includes(q) ||
        (b.tags || '').toLowerCase().includes(q)
    );
    shownCount.textContent = `顯示 ${filtered.length} 筆`;

    if (!filtered.length) {
        results.innerHTML = '<div class="empty">沒有符合條件的書籤，試試別的關鍵字。</div>';
        return;
    }

    results.innerHTML = filtered.map((b, i) => {
        const safeUrl = sanitizeUrl(b.url);
        const tagsHtml = normalizeTags(b.tags)
            .map((tag) => `<button class="tag" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`)
            .join('');

        return `
            <article class="bookmark" style="animation-delay:${Math.min(i * 0.03, 0.4)}s">
                <h3>${escapeHtml(b.title || "Untitled")}</h3>
                <div class="url">
                    ${safeUrl
            ? `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noopener noreferrer">${escapeHtml(safeUrl)}</a>`
            : `<span>${escapeHtml(b.url || "")}</span>`}
                </div>
                <p class="excerpt">${escapeHtml(b.excerpt || "沒有摘要")}</p>
                <div class="tags">${tagsHtml}</div>
            </article>
        `;
    }).join('');
}

searchInput.addEventListener("input", render);
clearBtn.addEventListener("click", () => {
    searchInput.value = "";
    render();
});
results.addEventListener("click", (event) => {
    const btn = event.target.closest(".tag");
    if (!btn) return;
    searchInput.value = btn.dataset.tag || "";
    render();
});

fetchBookmarks();
