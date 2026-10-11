import fs from 'node:fs/promises';
import path from 'node:path';

// File-backed KV emulation for running the Cloudflare Worker on Node/Render.
// Same API surface the worker uses: get/put/delete/list + expirationTtl.
export class FileKV {
  constructor(file) {
    this.file = file;
    this.map = new Map();
    this.timer = null;
  }

  async load() {
    try {
      const raw = await fs.readFile(this.file, 'utf8');
      const obj = JSON.parse(raw);
      const now = Date.now();
      for (const [k, v] of Object.entries(obj)) {
        if (v && typeof v.val !== 'undefined' && (!v.exp || v.exp > now)) this.map.set(k, v);
      }
      console.log(`kv loaded: ${this.map.size} keys`);
    } catch {
      console.log('kv: fresh start (no data file yet)');
    }
  }

  scheduleSave() {
    if (this.timer) return;
    this.timer = setTimeout(() => {
      this.timer = null;
      this.save().catch((e) => console.error('kv save failed', e));
    }, 5000);
  }

  async save() {
    try {
      await fs.mkdir(path.dirname(this.file), { recursive: true });
      await fs.writeFile(this.file, JSON.stringify(Object.fromEntries(this.map)));
    } catch (e) {
      console.error('kv save failed', e);
    }
  }

  async get(k) {
    const v = this.map.get(k);
    if (!v) return null;
    if (v.exp && v.exp <= Date.now()) {
      this.map.delete(k);
      this.scheduleSave();
      return null;
    }
    return v.val;
  }

  async put(k, val, opts = {}) {
    let exp = 0;
    if (opts.expirationTtl) exp = Date.now() + opts.expirationTtl * 1000;
    else if (opts.expiration) exp = opts.expiration * 1000;
    this.map.set(k, { val: String(val), exp });
    this.scheduleSave();
  }

  async delete(k) {
    this.map.delete(k);
    this.scheduleSave();
  }

  async list({ prefix = '', cursor } = {}) {
    const now = Date.now();
    const keys = [];
    for (const [k, v] of this.map) {
      if (v.exp && v.exp <= now) continue;
      if (k.startsWith(prefix)) keys.push({ name: k });
    }
    return { keys, list_complete: true, cursor: undefined };
  }
}
