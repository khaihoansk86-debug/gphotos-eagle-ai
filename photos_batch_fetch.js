/**
 * Fast Batch Thumbnail/HD-Preview Fetcher via Chrome DevTools Protocol.
 * Connects ONCE to the open Google Photos Chrome profile and fetches missing
 * images concurrently (concurrency=10) with real-time JSONL progress output.
 */
const fs = require('node:fs');
const path = require('node:path');

function upgradeUrl(u) {
  try {
    const parsed = new URL(u);
    if (parsed.protocol !== 'https:') return '';
    if (!(parsed.hostname === 'photos.fife.usercontent.google.com' || parsed.hostname.endsWith('.googleusercontent.com'))) {
      return '';
    }
    // Upgrade small grid thumb (=w171-h228-no) to crisp HD preview (=w1000-no)
    const upgraded = u.replace(/=w\d+-h\d+[^?&#]*/i, '=w1000-no');
    return upgraded;
  } catch {
    return '';
  }
}

async function main() {
  const profileDir = process.argv[2];
  const reqRaw = fs.readFileSync(0, 'utf8');
  const payload = JSON.parse(reqRaw);
  const items = payload.items || [];
  const concurrency = Math.max(1, Math.min(15, Number(payload.concurrency) || 10));

  const portFile = path.join(profileDir, 'DevToolsActivePort');
  if (!fs.existsSync(portFile)) {
    throw new Error('chrome_not_open: Hay bam "Mo Dang Nhap" de mo Chrome Google Photos truoc khi keo toan bo anh.');
  }
  const lines = fs.readFileSync(portFile, 'utf8').trim().split(/\r?\n/);
  if (!/^\d+$/.test(lines[0]) || !/^\/devtools\/browser\/[a-zA-Z0-9-]+$/.test(lines[1])) {
    throw new Error('bridge_required');
  }

  const ws = new WebSocket(`ws://127.0.0.1:${Number(lines[0])}${lines[1]}`);
  await new Promise((resolve, reject) => {
    ws.onopen = resolve;
    ws.onerror = () => reject(new Error('chrome_not_open: Khong ket noi duoc Chrome. Hay mo lai cua so Google Photos.'));
  });

  let seq = 0;
  const pending = new Map();
  ws.onmessage = e => {
    const m = JSON.parse(e.data);
    const p = pending.get(m.id);
    if (p) {
      pending.delete(m.id);
      clearTimeout(p.timer);
      m.error ? p.reject(new Error(m.error.message)) : p.resolve(m.result);
    }
  };

  const call = (method, params = {}, sessionId, timeoutMs = 20000) =>
    new Promise((resolve, reject) => {
      const id = ++seq;
      const timer = setTimeout(() => {
        pending.delete(id);
        reject(new Error(`timeout:${method}`));
      }, timeoutMs);
      pending.set(id, { resolve, reject, timer });
      ws.send(JSON.stringify(sessionId ? { id, method, params, sessionId } : { id, method, params }));
    });

  const { targetInfos } = await call('Target.getTargets');
  const pages = targetInfos.filter(t => t.type === 'page' && /^https:\/\/photos\.google\.com\//.test(t.url));
  if (!pages.length) {
    ws.close();
    throw new Error('no_photos_tab: Khong thay tab photos.google.com dang mo trong Chrome.');
  }

  const { sessionId } = await call('Target.attachToTarget', { targetId: pages[0].targetId, flatten: true });
  await call('Page.enable', {}, sessionId);
  const { frameTree } = await call('Page.getFrameTree', {}, sessionId);
  const frameId = frameTree.frame.id;

  async function fetchBytes(urlStr) {
    const { resource } = await call(
      'Network.loadNetworkResource',
      { frameId, url: urlStr, options: { disableCache: false, includeCredentials: true } },
      sessionId,
      20000
    );
    if (!resource || !resource.success || resource.httpStatusCode !== 200 || !resource.stream) {
      return null;
    }
    const chunks = [];
    let total = 0;
    try {
      while (true) {
        const part = await call('IO.read', { handle: resource.stream, size: 65536 }, sessionId, 15000);
        const bytes = Buffer.from(part.data, part.base64Encoded ? 'base64' : 'utf8');
        total += bytes.length;
        if (total > 12 * 1024 * 1024) return null;
        chunks.push(bytes);
        if (part.eof) break;
      }
    } finally {
      await call('IO.close', { handle: resource.stream }, sessionId).catch(() => {});
    }
    return Buffer.concat(chunks);
  }

  let done = 0;
  let ok = 0;
  let failed = 0;
  let cursor = 0;
  const total = items.length;

  async function worker() {
    while (true) {
      const idx = cursor++;
      if (idx >= total) break;
      const it = items[idx];
      try {
        const hdUrl = upgradeUrl(it.url);
        let buf = hdUrl ? await fetchBytes(hdUrl) : null;
        if (!buf && it.url && it.url !== hdUrl) {
          buf = await fetchBytes(it.url);
        }
        if (buf && buf.length > 200) {
          fs.writeFileSync(it.out_path, buf);
          ok++;
        } else {
          failed++;
        }
      } catch {
        failed++;
      }
      done++;
      if (done % 15 === 0 || done === total) {
        process.stdout.write(JSON.stringify({ event: 'progress', done, total, ok, failed }) + '\n');
      }
    }
  }

  const workers = [];
  for (let i = 0; i < Math.min(concurrency, total || 1); i++) {
    workers.push(worker());
  }
  await Promise.all(workers);

  ws.close();
  process.stdout.write(JSON.stringify({ event: 'complete', done, total, ok, failed }) + '\n');
}

main().catch(err => {
  process.stderr.write(String(err.message || err) + '\n');
  process.exit(1);
});
