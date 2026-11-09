// Small API + DOM helper layer, bearer-token aware.
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];

const store = {
  get token() { return localStorage.getItem('vr_token'); },
  get user() { try { return JSON.parse(localStorage.getItem('vr_user') || 'null'); } catch { return null; } },
  clear() { localStorage.removeItem('vr_token'); localStorage.removeItem('vr_user'); },
};

function toast(msg, kind) {
  const d = document.createElement('div');
  d.className = kind || '';
  d.textContent = msg;
  $('#toast').appendChild(d);
  setTimeout(() => d.remove(), 4000);
}

function esc(s) {
  return String(s ?? '').replace(/[&<>"']/g, (c) => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
}

async function api(path, opts = {}) {
  const headers = Object.assign({'Content-Type': 'application/json'}, opts.headers || {});
  if (store.token) headers.Authorization = 'Bearer ' + store.token;
  const r = await fetch(path, {...opts, headers});
  if (r.status === 401) {
    store.clear();
    location.href = '/';
    throw new Error('unauthorized');
  }
  const ct = r.headers.get('content-type') || '';
  const body = ct.includes('json') ? await r.json() : await r.text();
  if (!r.ok) {
    const msg = (body && body.detail) || (typeof body === 'string' ? body : `HTTP ${r.status}`);
    throw new Error(typeof msg === 'string' ? msg : JSON.stringify(msg));
  }
  return body;
}

const state = {
  view: 'dashboard',
  filters: {period: 7, region: 'ID', order: 'ctr', industry: '', keyword: '', onlyPs: false},
  ads: [],
  favs: [],
  insights: null,
  loading: false,
};

function fmtPct(v) { return (Number(v || 0) * 100).toFixed(2) + '%'; }
function fmtNum(v) { return new Intl.NumberFormat('id-ID').format(Number(v || 0)); }
function fmtDate(ts) { return new Date(ts * 1000).toLocaleString('id-ID', {dateStyle: 'short', timeStyle: 'short'}); }

function scoreOf(ad) {
  const ctr = Number(ad.ctr || 0) * 100;
  const likes = Math.log10(Number(ad.likes || 1));
  const ps = ad.product_sales ? 1.35 : 1;
  return Math.round((ctr * 9 + likes * 6) * ps * 10) / 10;
}

function scoreCls(s) { return s >= 60 ? 'ok' : s >= 35 ? 'warn' : ''; }
