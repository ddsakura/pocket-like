// readability-server.js
import express from 'express';
import fetch from 'node-fetch';
import { JSDOM } from 'jsdom';
import { Readability } from '@mozilla/readability';
import cors from 'cors';

const app = express();

app.use(cors());

app.get('/readability', async (req, res) => {
  const url = req.query.url;
  if (!url) return res.status(400).json({ error: 'Missing url parameter' });

  try {
    const html = await fetch(url, { headers: { 'User-Agent': 'Mozilla/5.0' } }).then(r => r.text());
    const dom = new JSDOM(html, { url });
    const reader = new Readability(dom.window.document);
    const article = reader.parse();

    if (!article) {
      return res.status(500).json({ error: 'Readability parse failed' });
    }

    res.json({
      url,
      title: article.title,
      excerpt: article.textContent.trim().substring(0, 200)
    });
  } catch (err) {
    console.error('❌ 解析失敗:', err);
    res.status(500).json({ error: 'Failed to parse URL' });
  }
});

app.listen(3000, () => {
  console.log('✅ Readability API server is running at http://localhost:3000');
});