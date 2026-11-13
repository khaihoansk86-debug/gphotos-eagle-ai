const fs = require('node:fs');
const path = require('node:path');

const pause = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const profileDir = process.argv[2];
  const action = process.argv[3] || 'list'; // 'list' or 'items'
  const targetUrl = process.argv[4] || 'https://photos.google.com/albums';

  const portFile = path.join(profileDir, 'DevToolsActivePort');
  if (!fs.existsSync(portFile)) {
    console.error(JSON.stringify({ error: 'DevToolsActivePort not found' }));
    process.exit(1);
  }

  const lines = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
  const port = lines[0];
  const browserPath = lines[1];

  const ws = new WebSocket(`ws://127.0.0.1:${port}${browserPath}`);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = reject;
  });

  let seq = 0;
  const pending = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    const p = pending.get(m.id);
    if (p) {
      pending.delete(m.id);
      clearTimeout(p.timer);
      if (m.error) p.reject(Error(m.error.message));
      else p.resolve(m.result);
    }
  };

  const call = (method, params = {}, sessionId) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(Error('timeout'));
      }, 20000);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ id, method, params, sessionId }));
    });

  let targetId = null;
  try {
    const target = await call('Target.createTarget', {
      url: targetUrl,
      background: true
    });
    targetId = target.targetId;
    const { sessionId } = await call('Target.attachToTarget', {
      targetId,
      flatten: true
    });

    await pause(3500);

    if (action === 'list') {
      // Scroll to load all albums
      let prevCount = 0;
      let stableLoops = 0;
      for (let i = 0; i < 15; i++) {
        await call('Runtime.evaluate', { expression: `window.scrollBy(0, 4000)` }, sessionId);
        await pause(1000);

        const cur = await call(
          'Runtime.evaluate',
          { expression: `document.querySelectorAll('a[href*="/album/"]').length` },
          sessionId
        );
        const count = cur.result?.value || 0;
        if (count === prevCount && count > 0) {
          stableLoops++;
          if (stableLoops >= 2) break;
        } else {
          stableLoops = 0;
          prevCount = count;
        }
      }

      const result = await call(
        'Runtime.evaluate',
        {
          expression: `
          (function() {
            const list = [];
            document.querySelectorAll('a[href*="/album/"]').forEach(a => {
              const fullText = (a.innerText || '').trim();
              const lines = fullText.split('\\n').map(s => s.trim()).filter(Boolean);
              const title = a.getAttribute('aria-label') || lines[0] || 'Chưa đặt tên';
              
              // Extract item count (e.g. "15 mục" or "3 items")
              let count = null;
              for (const l of lines) {
                const m = l.match(/(\\d+)\\s*(mục|mục ảnh|items?)/i);
                if (m) {
                  count = parseInt(m[1], 10);
                  break;
                }
              }

              // Extract cover image
              const img = a.querySelector('img,[data-latest-bg],[style*="background-image"]');
              const bg = img?.getAttribute('data-latest-bg') || img?.style?.backgroundImage || img?.src || '';
              const cover_url = bg.match(/url\\(["']?(.*?)["']?\\)/)?.[1] || bg;

              list.push({
                title: title.split('\\n')[0].trim(),
                album_url: a.href,
                item_count: count,
                cover_url
              });
            });

            // Deduplicate by album_url
            const seen = new Set();
            const unique = [];
            for (const it of list) {
              if (!seen.has(it.album_url)) {
                seen.add(it.album_url);
                unique.push(it);
              }
            }
            return {
              total_albums: unique.length,
              albums: unique
            };
          })()
        `,
          returnByValue: true
        },
        sessionId
      );

      console.log(JSON.stringify(result.result.value));
    } else if (action === 'items') {
      // Extract photos/videos within a specific album
      for (let i = 0; i < 5; i++) {
        await call('Runtime.evaluate', { expression: `window.scrollBy(0, 3000)` }, sessionId);
        await pause(800);
      }

      const result = await call(
        'Runtime.evaluate',
        {
          expression: `
          (function() {
            const items = [];
            const albumTitle = document.querySelector('h1, [role="heading"], input[aria-label]')?.innerText || 
                               document.title.replace(' - Google Photos', '');

            document.querySelectorAll('a[href*="/photo/"]').forEach(a => {
              const label = (a.getAttribute('aria-label') || a.innerText || '').trim();
              const isVideo = /video/i.test(label) || a.querySelector('[data-video-duration]');
              const img = a.querySelector('img,[data-latest-bg]');
              const thumb = img?.src || img?.getAttribute('data-latest-bg') || '';
              items.push({
                photo_url: a.href,
                label,
                kind: isVideo ? 'video' : 'photo',
                thumbnail_url: thumb
              });
            });

            const seen = new Set();
            const unique = [];
            for (const it of items) {
              if (!seen.has(it.photo_url)) {
                seen.add(it.photo_url);
                unique.push(it);
              }
            }

            return {
              album_title: albumTitle.trim(),
              total_items: unique.length,
              items: unique
            };
          })()
        `,
          returnByValue: true
        },
        sessionId
      );

      console.log(JSON.stringify(result.result.value));
    }
  } finally {
    if (targetId) {
      try {
        await call('Target.closeTarget', { targetId });
      } catch (e) {}
    }
    ws.close();
  }
}

main().catch(err => {
  console.error(JSON.stringify({ error: err.message }));
  process.exit(1);
});
