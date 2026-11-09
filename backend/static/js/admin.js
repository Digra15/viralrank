// Admin console — users, API config (FastMoss / TikTok Shop / AI gateway), audit, snapshots.
(() => {
const page = $('#page');
const titles = {overview: 'Overview', users: 'Pengguna', apisettings: 'Konfigurasi API', audit: 'Audit log', snapshots: 'Snapshot'};

$$('.nav-item[data-meta]').forEach((el) => {
  el.addEventListener('click', () => {
    $$('.nav-item').forEach((n) => n.classList.toggle('active', n === el));
    $('#pageTitle').textContent = titles[el.dataset.meta];
    $('#side').classList.remove('open');
    render(el.dataset.meta);
  });
});
$('#navOut').addEventListener('click', async () => {
  try { await api('/api/auth/logout', {method: 'POST'}); } catch {}
  store.clear(); location.href = '/';
});
$('#navApp').addEventListener('click', () => (location.href = '/app'));

function table(rows, cols) {
  return `<div class="table-wrap"><table><thead><tr>${cols.map((c) => `<th>${c[0]}</th>`).join('')}</tr></thead>
  <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td class="${c[2] || ''}">${c[1](r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}
function emptyBox(msg, hint) {
  return `<div class="card center" style="padding:44px 20px"><h3>${esc(msg)}</h3><p class="small muted" style="margin-top:6px">${esc(hint || '')}</p></div>`;
}
function fmtDate(ts) { return ts ? new Date(ts * 1000).toLocaleString('id-ID', {dateStyle: 'short', timeStyle: 'short'}) : '—'; }

// ---------------------------------------------------------------- overview
async function overview() {
  page.innerHTML = '<div class="grid g4">' + '<div class="skeleton"></div>'.repeat(4) + '</div>';
  const d = await api('/api/admin/stats');
  const s = d.latest_snapshot || {};
  page.innerHTML = `
  <div class="grid g4">
    <div class="card"><div class="kpi"><span class="label">Pengguna</span><span class="value">${d.users}</span></div></div>
    <div class="card"><div class="kpi"><span class="label">Sesi aktif (record)</span><span class="value">${d.sessions}</span></div></div>
    <div class="card"><div class="kpi"><span class="label">API keys</span><span class="value">${d.api_keys}</span></div></div>
    <div class="card"><div class="kpi"><span class="label">Snapshot iklan</span><span class="value">${d.ads_fetched}</span></div></div>
  </div>
  <div class="card">
    <h3 style="margin-bottom:10px">Snapshot terakhir</h3>
    ${s.created_at ? `<div class="row"><span class="pill ok">live</span>
      <span class="small">${fmtDate(s.created_at)} · ${s.total_ads} iklan · CTR avg ${(s.avg_ctr * 100).toFixed(2)}%</span></div>`
      : '<p class="small dim">Belum ada snapshot.</p>'}
  </div>`;
}

// ---------------------------------------------------------------- users
async function users() {
  page.innerHTML = `
  <div class="card">
    <h3 style="margin-bottom:10px">Tambah pengguna</h3>
    <div class="row">
      <label class="field" style="width:180px">Username<input id="uName"></label>
      <label class="field" style="width:180px">Password<input id="uPass" type="password"></label>
      <label class="field" style="width:130px">Role
        <select id="uRole"><option value="user">user</option><option value="admin">admin</option></select>
      </label>
      <button class="primary" id="uAdd">Buat</button>
    </div>
  </div>
  <div class="skeleton" style="height:200px"></div>`;
  $('#uAdd').addEventListener('click', async () => {
    try {
      const r = await api('/api/admin/users', {method: 'POST', body: JSON.stringify({
        username: $('#uName').value.trim(), password: $('#uPass').value, role: $('#uRole').value,
      })});
      toast(r.code === 0 ? 'User dibuat' : r.message, r.code === 0 ? 'ok' : 'err');
      users();
    } catch (e) { toast(e.message, 'err'); }
  });
  const d = await api('/api/admin/users');
  const box = document.createElement('div');
  box.innerHTML = table(d.users || [], [
    ['ID', (r) => `<span class="mono dim">${r.id}</span>`],
    ['Username', (r) => `<b>${esc(r.username)}</b>`],
    ['Role', (r) => r.role === 'admin' ? '<span class="pill acc">admin</span>' : '<span class="pill">user</span>'],
    ['Dibuat', (r) => `<span class="small dim">${fmtDate(r.created_at)}</span>`],
    ['Login terakhir', (r) => `<span class="small dim">${fmtDate(r.last_login)}</span>`],
    ['', (r) => `<div class="row tight">
      <button class="sm" data-role="${r.id}" data-now="${r.role}">Ganti role</button>
      <button class="sm danger" data-del="${r.id}">Hapus</button></div>`],
  ]);
  page.querySelectorAll('.skeleton').forEach((s) => s.replaceWith(box));
  $$('[data-del]', page).forEach((b) => b.addEventListener('click', async () => {
    if (!confirm('Hapus user #' + b.dataset.del + '?')) return;
    const r = await api('/api/admin/users/' + b.dataset.del, {method: 'DELETE'});
    toast(r.code === 0 ? 'Dihapus' : r.message, r.code === 0 ? 'ok' : 'err'); users();
  }));
  $$('[data-role]', page).forEach((b) => b.addEventListener('click', async () => {
    const next = b.dataset.now === 'admin' ? 'user' : 'admin';
    if (!confirm(`Jadikan user #${b.dataset.role} sebagai ${next}?`)) return;
    const r = await api(`/api/admin/users/${b.dataset.role}/role`, {method: 'PATCH', body: JSON.stringify({role: next})});
    toast(r.code === 0 ? 'Role diubah' : r.message, r.code === 0 ? 'ok' : 'err'); users();
  }));
}

// ---------------------------------------------------------------- API settings
const FIELDS = [
  ['fm_api_key', 'FastMoss API key', 'secret', 'Dari https://developers.fastmoss.com. Kosong = modul FastMoss off.'],
  ['fm_base_url', 'FastMoss base URL', 'text', 'Default https://openapi.fastmoss.com'],
  ['tts_app_key', 'TikTok Shop app key', 'secret', 'Partner Center app key. Kosong = modul Shop off.'],
  ['tts_app_secret', 'TikTok Shop app secret', 'secret', 'Partner Center app secret.'],
  ['tts_shop_cipher', 'TikTok Shop cipher', 'text', 'Shop cipher opsional (multi-shop).'],
  ['ai_gateway_url', 'AI gateway base URL', 'text', 'OpenAI-compatible, mis. http://localhost:20128/v1'],
  ['ai_gateway_key', 'AI gateway key', 'secret', 'Bearer key gateway.'],
  ['ai_model_chain', 'Model chain', 'text', 'Dipisah koma, urutan fallback. Contoh: ag/claude-sonnet-4-6,ag/gemini-3.8-flash'],
  ['cache_ttl', 'Cache TTL (detik)', 'text', 'Default 900.'],
];

async function apisettings() {
  const d = await api('/api/admin/settings');
  const s = d.settings || {};
  page.innerHTML = `
  <div class="card pad-lg">
    <h3 style="margin-bottom:4px">Konfigurasi API &amp; integrasi</h3>
    <p class="small muted">Nilai disimpan di database aplikasi (tabel settings). Secret ditampilkan tersamar; isi ulang untuk mengganti. Kosongkan untuk menghapus.</p>
    <div class="grid g2" style="margin-top:16px">
      ${FIELDS.map(([k, label, type, hint]) => `
        <label class="field">
          <span>${esc(label)}</span>
          <input id="set_${k}" value="${esc(s[k] || '')}" ${type === 'secret' ? 'type="password" autocomplete="off"' : ''} placeholder="${type === 'secret' ? '•••• (tersamar)' : ''}">
          <span class="tiny dim">${esc(hint)}</span>
        </label>`).join('')}
    </div>
    <div class="row" style="margin-top:16px">
      <button class="primary" id="saveSettings">Simpan semua</button>
      <button id="testFM">Tes FastMoss</button>
      <button id="testAI">Tes AI gateway</button>
      <span class="small" id="testOut"></span>
    </div>
  </div>`;
  $('#saveSettings').addEventListener('click', async () => {
    const btn = $('#saveSettings');
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> menyimpan…';
    try {
      for (const [k] of FIELDS) {
        const el = $('#set_' + k);
        if (!el) continue;
        const val = el.value.trim();
        const isSecret = el.type === 'password';
        if (!val || (isSecret && val.includes('*'))) continue; // skip empty / masked
        await api('/api/admin/settings/put', {method: 'POST', body: JSON.stringify({key: k, value: val})});
      }
      toast('Tersimpan. Restart service bila perlu.', 'ok');
    } catch (e) { toast(e.message, 'err'); }
    finally { btn.disabled = false; btn.textContent = 'Simpan semua'; }
  });
  $('#testAI').addEventListener('click', async () => {
    $('#testOut').textContent = 'menguji…';
    try {
      const r = await api('/api/admin/settings/test-connection', {method: 'POST', body: JSON.stringify({
        provider: 'ai',
        base_url: ($('#set_ai_gateway_url').value || 'http://localhost:20128/v1').trim(),
        api_key: $('#set_ai_gateway_key').value,
        test_url: '/models',
      })});
      $('#testOut').innerHTML = `<span class="pill ${r.code === 0 && r.status === 200 ? 'ok' : 'err'}">HTTP ${r.status}</span> <span class="tiny dim mono">${esc((r.body || r.message || '').slice(0, 120))}</span>`;
    } catch (e) { $('#testOut').innerHTML = `<span class="pill err">${esc(e.message)}</span>`; }
  });
  $('#testFM').addEventListener('click', async () => {
    $('#testOut').textContent = 'menguji…';
    try {
      const r = await api('/api/admin/settings/test-connection', {method: 'POST', body: JSON.stringify({
        provider: 'fastmoss',
        base_url: ($('#set_fm_base_url').value || 'https://openapi.fastmoss.com').trim(),
        api_key: $('#set_fm_api_key').value,
        test_url: '/',
      })});
      $('#testOut').innerHTML = `<span class="pill ${r.code === 0 ? 'ok' : 'err'}">HTTP ${r.status}</span> <span class="tiny dim mono">${esc((r.body || r.message || '').slice(0, 160))}</span>`;
    } catch (e) { $('#testOut').innerHTML = `<span class="pill err">${esc(e.message)}</span>`; }
  });
}

// ---------------------------------------------------------------- audit
async function audit() {
  page.innerHTML = '<div class="skeleton" style="height:300px"></div>';
  const d = await api('/api/admin/audit?limit=200');
  const box = document.createElement('div');
  box.innerHTML = (d.items || []).length ? table(d.items, [
    ['Waktu', (r) => `<span class="small dim">${fmtDate(r.created_at)}</span>`],
    ['User', (r) => esc(r.username || ('#' + (r.user_id ?? 'anon')))],
    ['Aksi', (r) => `<span class="pill">${esc(r.action)}</span>`],
    ['Detail', (r) => `<span class="tiny mono">${esc(r.detail || '')}</span>`],
    ['IP', (r) => `<span class="tiny mono dim">${esc(r.ip || '')}</span>`],
  ]) : emptyBox('Audit kosong');
  page.querySelectorAll('.skeleton').forEach((s) => s.replaceWith(box));
}

// ---------------------------------------------------------------- snapshots
async function snapshots() {
  page.innerHTML = '<div class="skeleton" style="height:300px"></div>';
  const d = await api('/api/admin/snapshots?limit=100');
  const box = document.createElement('div');
  box.innerHTML = (d.items || []).length ? table(d.items, [
    ['ID', (r) => `<span class="mono dim">${r.id}</span>`],
    ['Waktu', (r) => fmtDate(r.created_at)],
    ['Region', (r) => esc(r.region || '—')],
    ['Periode', (r) => esc(r.period || '—')],
    ['Iklan', (r) => `<span class="num">${r.total_ads}</span>`],
    ['CTR avg', (r) => `<span class="num">${(r.avg_ctr * 100).toFixed(2)}%</span>`],
  ]) : emptyBox('Belum ada snapshot', 'Snapshot tersimpan tiap kali /api/ads memuat data baru.');
  page.querySelectorAll('.skeleton').forEach((s) => s.replaceWith(box));
}

// ---------------------------------------------------------------- boot
async function boot() {
  if (!store.token) { location.href = '/'; return; }
  try {
    const me = await api('/api/auth/me');
    if (me.user.role !== 'admin') { location.href = '/app'; return; }
    $('#adminPill').textContent = me.user.username + ' · admin';
  } catch { return; }
  $$('.nav-item[data-meta]')[0]?.classList.add('active');
  render('overview');
}

async function render(which) {
  const v = {overview, users, apisettings, audit, snapshots}[which];
  if (!v) return;
  try { await v(); } catch (e) {
    page.innerHTML = emptyBox('Gagal memuat', e.message);
  }
}

boot();
})();
