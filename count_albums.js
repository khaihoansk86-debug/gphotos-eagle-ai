const fs = require('node:fs');
const path = require('node:path');

const pause = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const profileDir = process.argv[2];
  const portFile = path.join(profileDir, 'DevToolsActivePort');
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
    const target = await call('Target.createTarget', {
      url: 'https://photos.google.com/albums',
      background: true
    });
    targetId = target.targetId;
    const { sessionId } = await call('Target.attachToTarget', {
      targetId,
      flatten: true
    });

    await pause(3000);

    // Scroll several times to load all albums
    for (let i = 0; i < 8; i++) {
      await call(
        'Runtime.evaluate',
        {
          expression: `window.scrollBy(0, 3000)`
        },
        sessionId
      );
      await pause(1000);
    }

    const result = await call(
      'Runtime.evaluate',
      {
        expression: `
        (function() {
          const albums = [];
          document.querySelectorAll('a[href*="/album/"]').forEach(a => {
            const text = (a.innerText || '').trim();
            const title = a.getAttribute('aria-label') || text.split('\\n')[0];
            albums.push({ title: title.trim(), href: a.href, text });
          });
          const seen = new Set();
          const unique = [];
          for (const item of albums) {
            if (!seen.has(item.href)) {
              seen.add(item.href);
              unique.push(item);
            }
          }
          return {
            total_albums: unique.length,
            sample: unique.slice(0, 15).map(x => x.title)
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
  console.error(err);
  process.exit(1);
});
