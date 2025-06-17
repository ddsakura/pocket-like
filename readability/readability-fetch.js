import fetch from 'node-fetch';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';

const url = process.argv[2]; // 從命令列取得 URL
if (!url) {
  console.error('❌ 請提供一個網址，例如：node readability-fetch.js https://example.com');
  process.exit(1);
}

try {
  const res = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } });
  const html = await res.text();
  const dom = new JSDOM(html, { url }); // 要傳入 URL 讓 Readability 能正確解析 domain-relative 路徑

  const reader = new Readability(dom.window.document);
  const article = reader.parse();

  if (!article) {
    console.error('❌ Readability 解析失敗，請檢查 URL 或 HTML 結構');
    process.exit(1);
  }

  console.log(JSON.stringify({
    url,
    title: article.title,
    excerpt: article.excerpt,
    textContent: article.textContent,
    content: article.content, // HTML 格式
    siteName: article.siteName
  }, null, 2));

} catch (error) {
  console.error('❌ 錯誤發生:', error);
  process.exit(1);
}