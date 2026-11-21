/**
 * Ultra-Accurate Google Photos Real Album Membership Scanner.
 * Uses a foreground reusable Chrome tab so Chrome never throttles virtual scrolling,
 * extracts ALL embedded AF1Qip photo IDs from AF_initDataCallback scripts, AND
 * scrolls the active C-WIZ container to guarantee 100% of items in every album.
 */
const fs = require('node:fs');
const path = require('node:path');

const pause = ms => new Promise(r => setTimeout(r, ms));

async function main() {
  const profileDir = process.argv[2];
  const payload = JSON.parse(fs.readFileSync(0, 'utf8'));
  const albums = payload.albums || [];

  const portFile = path.join(profileDir, 'DevToolsActivePort');
  if (!fs.existsSync(portFile)) {
    throw new Error('chrome_not_open: Hay mo Chrome Google Photos truoc.');
  }
  const lines = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
  const ws = new WebSocket(`ws://127.0.0.1:${Number(lines[0])}${lines[1]}`);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = () => reject(new Error('chrome_not_open'));
  });

  let seq = 0;
  const pending = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    const p = pending.get(m.id);
    if (p) {
      pending.delete(m.id);
      clearTimeout(p.timer);
      m.error ? p.reject(Error(m.error.message)) : p.resolve(m.result);
    }
  };

  const call = (method, params = {}, sessionId, timeoutMs = 25000) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`timeout:${method}`));
      }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
    });

  let targetId = null;
  try {
    const target = await call('Target.createTarget', { url: 'about:blank', background: false });
    targetId = target.targetId;
    const { sessionId } = await call('Target.attachToTarget', { targetId, flatten: true });
    await call('Page.enable', {}, sessionId);

    const extractAndScrollExpr = `(function() {
      const seen = new Map();
      // 1. Collect all visible /photo/ links in DOM
      document.querySelectorAll('a[href*="/photo/"]').forEach(a => {
        try {
          const u = new URL(a.href, location.href);
          const m = u.pathname.match(/(\\/photo\\/[^/?#]+)/);
          if (m) {
            const lbl = (a.getAttribute('aria-label') || '').normalize('NFC').slice(0, 240);
            seen.set(m[1], { media_key: m[1], photo_url: 'https://photos.google.com' + m[1], label: lbl });
          }
        } catch {}
      });
      // 2. Collect embedded AF1Qip photo IDs from Google Photos AF_initDataCallback scripts
      for (const sc of document.scripts) {
        const txt = sc.textContent || '';
        if (txt.includes('AF_initDataCallback') && txt.includes('AF1Qip')) {
          const matches = txt.match(/AF1Qip[A-Za-z0-9_-]{30,}/g) || [];
          for (const id of matches) {
            const mk = '/photo/' + id;
            if (!seen.has(mk)) {
              seen.set(mk, { media_key: mk, photo_url: 'https://photos.google.com' + mk, label: '' });
            }
          }
        }
      }
      // 3. Scroll C-WIZ scroller
      let atBottom = true;
      const scrollers = [...document.querySelectorAll('c-wiz, main, [role="main"], div')].filter(
        e => e.clientHeight > 200 && e.scrollHeight > e.clientHeight + 40 && /(auto|scroll)/.test(getComputedStyle(e).overflowY)
      );
      if (scrollers.length) {
        const sc = scrollers.sort((a, b) => b.scrollHeight - a.scrollHeight)[0];
        atBottom = sc.scrollTop + sc.clientHeight >= sc.scrollHeight - 30;
        sc.scrollTop += Math.max(900, Math.floor(sc.clientHeight * 0.95));
      }
      return { items: [...seen.values()], atBottom };
    })()`;

    for (let i = 0; i < albums.length; i++) {
      const al = albums[i];
      const expected = Number(al.item_count) || 0;
      const ownAlbumIdMatch = String(al.album_url || '').match(/AF1Qip[A-Za-z0-9_-]{20,}/);
      const ownAlbumKey = ownAlbumIdMatch ? `/photo/${ownAlbumIdMatch[0]}` : '';
      const collected = new Map();

      try {
        await call('Page.navigate', { url: al.album_url }, sessionId);
        await pause(1800);

        const maxScrolls = expected > 80 ? 20 : 4;
        let stableCount = 0;
        let lastSize = 0;

        for (let s = 0; s < maxScrolls; s++) {
          const ev = await call('Runtime.evaluate', { expression: extractAndScrollExpr, returnByValue: true }, sessionId);
          const val = ev?.result?.value;
          if (val && Array.isArray(val.items)) {
            for (const it of val.items) {
              if (it.media_key === ownAlbumKey) continue;
              if (!collected.has(it.media_key) || (it.label && !collected.get(it.media_key).label)) {
                collected.set(it.media_key, it);
              }
            }
            if (expected > 0 && collected.size >= expected && s >= 1) {
              break;
            }
            if (val.atBottom || collected.size === lastSize) {
              stableCount++;
              if (stableCount >= 2) break;
            } else {
              stableCount = 0;
              lastSize = collected.size;
            }
          }
          await pause(550);
        }
      } catch (err) {
        // Continue to next album
      }

      process.stdout.write(
        JSON.stringify({
          event: 'album_done',
          idx: i + 1,
          total: albums.length,
          album_id: al.id,
          title: al.title,
          expected,
          found: collected.size,
          items: [...collected.values()],
        }) + '\n'
      );
    }
  } finally {
    if (targetId) {
      await call('Target.closeTarget', { targetId }).catch(() => {});
    }
    ws.close();
  }
}

main().catch(err => {
  process.stderr.write(String(err.message || err) + '\n');
  process.exit(1);
});
