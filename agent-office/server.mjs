// agent-office：接收 Claude Code hook 事件 → 存 JSONL → SSE 推給瀏覽器
// 只用 Node 內建模組，不需要 npm install。  node server.mjs  → http://localhost:5180
import http from 'node:http';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const DIR = path.dirname(fileURLToPath(import.meta.url));
const EV_DIR = path.join(DIR, 'events');
const PUB = path.join(DIR, 'public');
const PORT = Number(process.env.PORT) || 5180;
fs.mkdirSync(EV_DIR, { recursive: true });

const clients = new Set();
const safe = (s) => String(s || 'unknown').replace(/[^\w-]/g, '_').slice(0, 80);
const MIME = { '.html': 'text/html; charset=utf-8', '.js': 'text/javascript', '.css': 'text/css', '.png': 'image/png' };

function readLog(session) {
  const f = path.join(EV_DIR, safe(session) + '.jsonl');
  if (!fs.existsSync(f)) return [];
  return fs.readFileSync(f, 'utf8').split('\n').filter(Boolean).flatMap((l) => {
    try { return [JSON.parse(l)]; } catch { return []; }
  });
}

function listSessions() {
  return fs.readdirSync(EV_DIR).filter((f) => f.endsWith('.jsonl')).map((f) => {
    const id = f.slice(0, -6);
    const evs = readLog(id);
    const start = evs.find((e) => e.event === 'UserPromptSubmit' && /equity-research-tw/.test(e.prompt || ''));
    return {
      id,
      count: evs.length,
      first: evs[0]?.ts ?? 0,
      last: evs.at(-1)?.ts ?? 0,
      prompt: (start?.prompt || evs.find((e) => e.prompt)?.prompt || '').slice(0, 80),
    };
  }).sort((a, b) => b.last - a.last);
}

function json(res, data) {
  res.writeHead(200, { 'content-type': 'application/json; charset=utf-8' }).end(JSON.stringify(data));
}

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, 'http://localhost');

  if (req.method === 'POST' && url.pathname === '/event') {
    let body = '';
    for await (const chunk of req) {
      body += chunk;
      if (body.length > 64 * 1024) break;
    }
    try {
      const e = JSON.parse(body);
      e.ts ||= Date.now();
      e.session = safe(e.session);
      fs.appendFileSync(path.join(EV_DIR, e.session + '.jsonl'), JSON.stringify(e) + '\n');
      const line = `data: ${JSON.stringify(e)}\n\n`;
      for (const c of clients) c.write(line);
    } catch { /* 壞掉的事件直接丟掉 */ }
    res.writeHead(204).end();
    return;
  }

  if (url.pathname === '/stream') {
    res.writeHead(200, { 'content-type': 'text/event-stream', 'cache-control': 'no-cache', connection: 'keep-alive' });
    res.write(': connected\n\n');
    clients.add(res);
    req.on('close', () => clients.delete(res));
    return;
  }

  if (url.pathname === '/api/sessions') return json(res, listSessions());
  if (url.pathname === '/api/log') return json(res, readLog(url.searchParams.get('session')));

  const rel = url.pathname === '/' ? 'index.html' : url.pathname.slice(1);
  const file = path.join(PUB, path.normalize(rel));
  if (!file.startsWith(PUB) || !fs.existsSync(file) || fs.statSync(file).isDirectory()) {
    res.writeHead(404).end('not found');
    return;
  }
  res.writeHead(200, { 'content-type': MIME[path.extname(file)] || 'application/octet-stream' });
  fs.createReadStream(file).pipe(res);
});

setInterval(() => { for (const c of clients) c.write(': ping\n\n'); }, 25_000);
server.listen(PORT, '127.0.0.1', () => console.log(`agent-office → http://localhost:${PORT}`));
