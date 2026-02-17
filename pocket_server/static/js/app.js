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
    const filtered = bookmarks.filter((b) =>
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
            .map((tag) => `<button class="tag" data-tag="${escapeHtml(tag)}">${escapeHtml(tag)}</button>`)
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

    results.querySelectorAll(".tag").forEach((btn) => {
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
