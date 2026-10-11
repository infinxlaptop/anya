import http from 'node:http';
import worker from './worker.js';
import { FileKV } from './kvstore.js';

// Runs the Cloudflare Worker (worker.js) on Node/Render with zero changes:
// - env.ANYA_KV  -> file-backed store (./data/kv.json)
// - ctx.waitUntil -> background promise guard
// - scheduled()  -> tiny cron ticker below

const kv = new FileKV(new URL('./data/kv.json', import.meta.url));
await kv.load();

const env = {
  BOT_TOKEN: process.env.BOT_TOKEN || '',
  GEMINI_API_KEY: process.env.GEMINI_API_KEY || '',
  MEMBER_API_URL: process.env.MEMBER_API_URL || '',
  MEMBER_API_KEY: process.env.MEMBER_API_KEY || '',
  UPDATES_CHANNEL_ID: process.env.UPDATES_CHANNEL_ID || '',
  ANYA_KV: kv,
};

if (!env.BOT_TOKEN) console.error('FATAL: BOT_TOKEN env missing hai!');
if (!env.GEMINI_API_KEY) console.error('WARN: GEMINI_API_KEY env missing hai (AI reply nahi hoga)');

const ctxStub = () => ({
  waitUntil(p) {
    Promise.resolve(p).catch((e) => console.error('bg task failed:', e));
  },
});

const server = http.createServer(async (req, res) => {
  if (req.url === '/' && req.method === 'GET') {
    res.writeHead(200, { 'content-type': 'text/plain' });
    res.end('anya alive');
    return;
  }
  try {
    const chunks = [];
    for await (const c of req) chunks.push(c);
    const body = Buffer.concat(chunks);
    const url = `http://${req.headers.host || 'localhost'}${req.url}`;
    const wreq = new Request(url, {
      method: req.method,
      headers: req.headers,
      body: req.method === 'GET' || req.method === 'HEAD' ? undefined : body,
      duplex: 'half',
    });
    const wres = await worker.fetch(wreq, env, ctxStub());
    const headers = {};
    for (const [k, v] of wres.headers.entries()) headers[k] = v;
    res.writeHead(wres.status, headers);
    res.end(Buffer.from(await wres.arrayBuffer()));
  } catch (e) {
    console.error('webhook failed:', e);
    res.writeHead(500);
    res.end('err');
  }
});

const PORT = Number(process.env.PORT || 10000);
server.listen(PORT, '0.0.0.0', () => console.log(`anya listening on ${PORT}`));

// ----- Cron ticker (wrangler.toml wale schedules) -----
const CRONS = ['* * * * *', '*/5 * * * *', '30 1 * * *', '30 8 * * *', '30 13 * * *'];
let lastTick = '';
setInterval(async () => {
  try {
    const d = new Date();
    const key = d.toISOString().slice(0, 16);
    if (key === lastTick) return;
    lastTick = key;
    const m = d.getUTCMinutes();
    const h = d.getUTCHours();
    for (const cron of CRONS) {
      let due = false;
      if (cron === '* * * * *') due = true;
      else if (cron === '*/5 * * * *') due = m % 5 === 0;
      else {
        const parts = cron.split(' ');
        due = m === Number(parts[0]) && h === Number(parts[1]);
      }
      if (!due) continue;
      try {
        await worker.scheduled({ cron }, env, ctxStub());
      } catch (e) {
        console.error('cron failed:', cron, e);
      }
    }
  } catch (e) {
    console.error('ticker failed:', e);
  }
}, 20000);

async function shutdown() {
  console.log('saving kv...');
  await kv.save();
  process.exit(0);
}
process.on('SIGTERM', shutdown);
process.on('SIGINT', shutdown);
