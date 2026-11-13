const fs = require('node:fs');
const path = require('node:path');

const pause = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const profileDir = process.argv[2];
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
      }, 15000);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify({ id, method, params, sessionId }));
    });

  let targetId = null;
  try {
    // 1. Create a background target tab for /albums
    const target = await call('Target.createTarget', {
      url: 'https://photos.google.com/albums',
      background: true
    });
    targetId = target.targetId;

    // 2. Attach to target
    const { sessionId } = await call('Target.attachToTarget', {
      targetId,
      flatten: true
    });

    // 3. Wait for albums page to load
    await pause(3500);

    // 4. Extract album cards
    const result = await call(
      'Runtime.evaluate',
      {
        expression: `
        (function() {
          const albums = [];
          // Look for album links
          const links = document.querySelectorAll('a[href*="/album/"]');
          links.forEach(a => {
            const titleEl = a.querySelector('[title], div[dir="auto"], span');
            const title = a.getAttribute('aria-label') || titleEl?.innerText || a.innerText || '';
            const href = a.href;
            // look for count like 'xx mục' or 'xx items'
            const textNodes = Array.from(a.querySelectorAll('*'))
              .map(e => e.innerText)
              .filter(Boolean);
            albums.push({
              title: title.split('\\n')[0].trim(),
              href,
              details: textNodes.slice(0, 3).join(' • ')
            });
          });

          // Also look for grid items in albums view
          const cards = document.querySelectorAll('div[data-id], [role="listitem"]');
          cards.forEach(card => {
            const a = card.querySelector('a');
            if (a && a.href.includes('/album/')) {
              const text = card.innerText.trim();
              if (!albums.some(al => al.href === a.href)) {
                albums.push({
                  title: text.split('\\n')[0] || 'Chưa đặt tên',
                  href: a.href,
                  details: text.replace(/\\n/g, ' • ')
                });
              }
            }
          });

          // Deduplicate by href
          const seen = new Set();
          const unique = [];
          for (const item of albums) {
            if (!seen.has(item.href)) {
              seen.add(item.href);
              unique.push(item);
            }
          }

          return {
            page_title: document.title,
            current_url: location.href,
            album_count: unique.length,
            albums: unique
          };
        })()
      `,
        returnByValue: true
      },
      sessionId
    );

    console.log(JSON.stringify(result.result.value, null, 2));
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
