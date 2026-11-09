// ViralRank SPA — views: dashboard, ads, radar, brands, trends, favorites, alerts, ai, export, settings, keys.
(() => {
const view = $('#view');
const titles = {
  dashboard: 'Dashboard', ads: 'Top Ads', radar: 'Product Radar', brands: 'Brand Lab',
  trends: 'Trend Radar', favorites: 'Favorit', alerts: 'Alert', ai: 'AI Studio',
  export: 'Export', settings: 'Pengaturan', keys: 'API Key',
};

// ---------------------------------------------------------------- router
$$('.nav-item[data-view]').forEach((el) => {
  el.addEventListener('click', () => {
    state.view = el.dataset.view;
    $$('.nav-item').forEach((n) => n.classList.toggle('active', n === el));
    $('#side').classList.remove('open');
    $('#viewTitle').textContent = titles[state.view] || state.view;
    render();
  });
});
$('#navOut').addEventListener('click', async () => {
  try { await api('/api/auth/logout', {method: 'POST'}); } catch {}
  store.clear();
  location.href = '/';
});
$('#navAdmin').addEventListener('click', () => (location.href = '/admin'));

// ---------------------------------------------------------------- shared filter bar
function filterBar(viewsWithPs = true) {
  const f = state.filters;
  return `
  <div class="card row">
    <label class="field" style="width:120px">Periode
      <select id="fPeriod">
        ${[1, 7, 14, 30, 60, 120, 180].map((d) => `<option value="${d}" ${d == f.period ? 'selected' : ''}>${d} hari</option>`).join('')}
      </select>
    </label>
    <label class="field" style="width:120px">Wilayah
      <select id="fRegion">
        ${['ID', 'GB', 'US', 'SA', 'TH', 'VN', 'MY', 'PH', 'SG'].map((r) => `<option ${r === f.region ? 'selected' : ''}>${r}</option>`).join('')}
      </select>
    </label>
    <label class="field" style="width:150px">Urutkan
      <select id="fOrder">
        ${[['ctr', 'CTR tertinggi'], ['like', 'Likes terbanyak'], ['cost', 'Estimasi spend']].map(([v, l]) => `<option value="${v}" ${v === f.order ? 'selected' : ''}>${l}</option>`).join('')}
      </select>
    </label>
    <label class="field" style="flex:1;min-width:170px">Kata kunci
      <input id="fKeyword" value="${esc(f.keyword)}" placeholder="cari judul iklan…">
    </label>
    ${viewsWithPs ? `<label class="field" style="width:auto;justify-content:flex-end"><span class="small">Product sales saja</span>
      <input type="checkbox" id="fPs" ${f.onlyPs ? 'checked' : ''} style="width:16px;height:16px"></label>` : ''}
    <button class="primary" id="fGo">Terapkan</button>
  </div>`;
}

function bindFilterBar(onApply) {
  const read = () => {
    state.filters.period = Number($('#fPeriod')?.value || 7);
    state.filters.region = $('#fRegion')?.value || 'ID';
    state.filters.order = $('#fOrder')?.value || 'ctr';
    state.filters.keyword = ($('#fKeyword')?.value || '').trim();
    state.filters.onlyPs = !!$('#fPs')?.checked;
  };
  $('#fGo')?.addEventListener('click', () => { read(); onApply(); });
  $('#fKeyword')?.addEventListener('keydown', (e) => { if (e.key === 'Enter') { read(); onApply(); } });
  $('#fKeyword') && ($('#fKeyword').value = state.filters.keyword);
}

// ---------------------------------------------------------------- data fetch
async function loadAds() {
  const f = state.filters;
  const q = new URLSearchParams({period: f.period, region: f.region, order_by: f.order, limit: 30, page: 1});
  if (f.industry) q.set('industry_id', f.industry);
  if (f.keyword) q.set('keyword', f.keyword);
  const d = await api('/api/ads?' + q);
  let items = d.items || [];
  if (f.onlyPs) items = items.filter((i) => i.product_sales);
  if (f.keyword) items = items.filter((i) => (i.title || '').toLowerCase().includes(f.keyword.toLowerCase()));
  state.ads = items;
  return items;
}

async function loadInsights() {
  const f = state.filters;
  const q = new URLSearchParams({period: f.period, region: f.region, pages: 2, order_by: f.order});
  const d = await api('/api/insights?' + q);
  state.insights = d;
  return d;
}

async function loadFavs() {
  try {
    const d = await api('/api/auth/favorites');
    state.favs = d.items || [];
    $('#badgeFav').textContent = state.favs.length;
  } catch { /* silent */ }
}

// ---------------------------------------------------------------- ad card
function adCard(ad, i) {
  const s = scoreOf(ad);
  return `
  <div class="ad">
    <div class="thumb">
      ${ad.cover ? `<img loading="lazy" src="${esc(ad.cover)}" alt="">` : ''}
      <span class="rank">#${i + 1}</span>
      <span class="ctr">${fmtPct(ad.ctr)}</span>
    </div>
    <div class="meta">
      <div class="t">${esc(ad.title || '(tanpa judul)')}</div>
      <div class="s"><span class="mono">♥ ${fmtNum(ad.likes)}</span><span>·</span><span>${esc(ad.brand_name || 'non-brand')}</span></div>
      <div class="s tiny">skor <b class="num">${s}</b> · ${esc(ad.objective || '-')} · ${(ad.duration || 0).toFixed(0)}s</div>
      <div class="row tight">
        <button class="sm" data-fav="${esc(ad.id)}" data-kind="ad" data-title="${esc((ad.title || '').slice(0, 60))}">★ Simpan</button>
        <a class="btn sm" href="${esc(ad.video_url)}" target="_blank" rel="noopener">▶ Video</a>
      </div>
    </div>
  </div>`;
}

function bindFavButtons() {
  $$('[data-fav]', view).forEach((b) => b.addEventListener('click', async () => {
    try {
      const d = await api('/api/auth/favorites', {method: 'POST', body: JSON.stringify({
        kind: b.dataset.kind, ref_id: b.dataset.fav, payload: {title: b.dataset.title},
      })});
      toast(d.code === 0 ? 'Disimpan ke favorit' : d.message || 'Sudah ada', d.code === 0 ? 'ok' : '');
      loadFavs();
    } catch (e) { toast(e.message, 'err'); }
  }));
}

function table(rows, cols) {
  return `<div class="table-wrap"><table><thead><tr>${cols.map((c) => `<th>${c[0]}</th>`).join('')}</tr></thead>
  <tbody>${rows.map((r) => `<tr>${cols.map((c) => `<td class="${c[2] || ''}">${c[1](r)}</td>`).join('')}</tr>`).join('')}</tbody></table></div>`;
}

function emptyBox(msg, hint) {
  return `<div class="card center" style="padding:44px 20px"><h3>${esc(msg)}</h3><p class="small muted" style="margin-top:6px">${esc(hint || '')}</p></div>`;
}

// ---------------------------------------------------------------- views
const views = {};

views.dashboard = async () => {
  view.innerHTML = '<div class="grid g4">' + '<div class="skeleton"></div>'.repeat(4) + '</div><div class="skeleton" style="height:260px"></div>';
  const [ads, ins] = await Promise.all([loadAds(), loadInsights().catch(() => null)]);
  const topBrand = ins?.brands?.[0];
  const topTag = ins?.hashtags?.[0];
  view.innerHTML = `
  <div class="grid g4">
    <div class="card"><div class="kpi"><span class="label">Iklan aktif (sample)</span><span class="value">${fmtNum(ads.length)}</span><span class="delta small muted">${fmtPct(ads.reduce((a, i) => a + (i.ctr || 0), 0) / Math.max(ads.length, 1))} CTR rata-rata</span></div></div>
    <div class="card"><div class="kpi"><span class="label">Brand unik</span><span class="value">${fmtNum(ins?.brands?.length || 0)}</span><span class="delta small muted">${esc(topBrand ? `top: ${topBrand.name}` : '—')}</span></div></div>
    <div class="card"><div class="kpi"><span class="label">Hashtag teratas</span><span class="value" style="font-size:19px">${esc(topTag ? topTag.name : '—')}</span><span class="delta small muted">${topTag ? `muncul ${topTag.ads}×` : ''}</span></div></div>
    <div class="card"><div class="kpi"><span class="label">Kandidat product-sales</span><span class="value">${fmtNum(ads.filter((a) => a.product_sales).length)}</span><span class="delta small muted">dari ${ads.length} iklan</span></div></div>
  </div>

  <div class="card">
    <div class="row spread"><h3>Top 5 momentum hari ini</h3><button class="sm" onclick="location.hash='#ads';go('ads')">Lihat semua</button></div>
    ${table(ads.slice().sort((a, b) => scoreOf(b) - scoreOf(a)).slice(0, 5), [
      ['#', (r, i) => `<span class="dim mono">${i + 1}</span>`],
      ['Judul', (r) => `<div class="ellipsis" style="max-width:420px">${esc(r.title || '(tanpa judul)')}</div>`],
      ['Brand', (r) => esc(r.brand_name || '—')],
      ['CTR', (r) => `<span class="num">${fmtPct(r.ctr)}</span>`],
      ['Likes', (r) => `<span class="num">${fmtNum(r.likes)}</span>`],
      ['Skor', (r) => `<span class="pill ${scoreCls(scoreOf(r))} num">${scoreOf(r)}</span>`],
    ])}
  </div>

  <div class="grid g2">
    <div class="card"><h3 style="margin-bottom:10px">Brand paling agresif</h3>
      ${(ins?.brands || []).slice(0, 6).map((b) => `
        <div class="row spread" style="padding:7px 0;border-bottom:1px solid var(--line)">
          <span class="ellipsis" style="max-width:180px">${esc(b.name)}</span>
          <span class="small dim num">${b.ads} iklan · CTR ${fmtPct(b.avg_ctr)}</span>
          <div class="bar" style="width:90px"><i style="width:${Math.min(100, b.momentum * 2)}%"></i></div>
        </div>`).join('') || '<p class="small dim">Tidak ada data.</p>'}
    </div>
    <div class="card"><h3 style="margin-bottom:10px">Hashtag naik</h3>
      <div class="row tight" style="gap:8px">
        ${(ins?.hashtags || []).slice(0, 14).map((h) => `<span class="pill">${esc(h.name)} <b class="num">${h.ads}</b></span>`).join('') || '<p class="small dim">Tidak ada data.</p>'}
      </div>
    </div>
  </div>`;
};

views.ads = async () => {
  view.innerHTML = filterBar() + '<div class="skeleton" style="height:300px"></div>';
  bindFilterBar(views.ads);
  const ads = await loadAds();
  if (!ads.length) { view.innerHTML = filterBar() + emptyBox('Tidak ada iklan', 'Coba longgarkan filter atau kata kunci.'); bindFilterBar(views.ads); return; }
  view.innerHTML = filterBar() + `
    <div class="row spread"><span class="small muted">${ads.length} iklan · sumber Creative Center</span>
    <button class="sm" id="expQuick">⤓ CSV</button></div>
    <div class="adgrid">${ads.map(adCard).join('')}</div>`;
  bindFilterBar(views.ads);
  bindFavButtons();
  $('#expQuick').onclick = () => views._download();
};

views._download = () => {
  const f = state.filters;
  const q = new URLSearchParams({period: f.period, region: f.region, pages: 2, order_by: f.order});
  location.href = '/api/export/csv?' + q;
};

views.radar = async () => {
  view.innerHTML = filterBar() + '<div class="skeleton" style="height:300px"></div>';
  bindFilterBar(views.radar);
  const ads = await loadAds();
  const cands = ads.filter((a) => a.product_sales)
    .map((a) => ({...a, score: scoreOf(a)}))
    .sort((a, b) => b.score - a.score);
  if (!cands.length) { view.innerHTML = filterBar() + emptyBox('Belum ada kandidat', 'Iklan product-sales belum muncul di filter ini.'); bindFilterBar(views.radar); return; }
  view.innerHTML = filterBar() + `
    <div class="grid g4">
      <div class="card"><div class="kpi"><span class="label">Kandidat</span><span class="value">${cands.length}</span></div></div>
      <div class="card"><div class="kpi"><span class="label">Skor median</span><span class="value">${cands[Math.floor(cands.length / 2)]?.score ?? '—'}</span></div></div>
      <div class="card"><div class="kpi"><span class="label">Skor atas</span><span class="value">${cands[0].score}</span></div></div>
      <div class="card"><div class="kpi"><span class="label">CTR atas</span><span class="value">${fmtPct(cands[0].ctr)}</span></div></div>
    </div>
    ${table(cands.slice(0, 30), [
      ['#', (r, i) => `<span class="dim mono">${i + 1}</span>`],
      ['Produk / Judul', (r) => `<div class="ellipsis" style="max-width:380px">${esc(r.title)}</div>`],
      ['Brand', (r) => esc(r.brand_name || '—')],
      ['CTR', (r) => `<span class="num">${fmtPct(r.ctr)}</span>`],
      ['Likes', (r) => `<span class="num">${fmtNum(r.likes)}</span>`],
      ['Skor', (r) => `<span class="pill ${scoreCls(r.score)} num">${r.score}</span>`],
      ['', (r) => `<div class="row tight"><button class="sm" data-fav="${esc(r.id)}" data-kind="product" data-title="${esc(r.title.slice(0, 60))}">★</button><a class="btn sm" href="${esc(r.video_url)}" target="_blank">▶</a></div>`],
    ])}`;
  bindFilterBar(views.radar);
  bindFavButtons();
};

views.brands = async () => {
  view.innerHTML = filterBar(false) + '<div class="skeleton" style="height:260px"></div>';
  bindFilterBar(views.brands);
  const ins = await loadInsights();
  view.innerHTML = filterBar(false) + `
    ${table(ins.brands || [], [
      ['Brand', (r) => `<b>${esc(r.name)}</b>`],
      ['Iklan', (r) => `<span class="num">${r.ads}</span>`],
      ['CTR rata-rata', (r) => `<span class="num">${fmtPct(r.avg_ctr)}</span>`],
      ['Total likes', (r) => `<span class="num">${fmtNum(r.likes)}</span>`],
      ['Momentum', (r) => `<div class="bar" style="width:120px"><i style="width:${Math.min(100, r.momentum * 2)}%"></i></div>`],
    ])}`;
  bindFilterBar(views.brands);
};

views.trends = async () => {
  view.innerHTML = filterBar(false) + '<div class="skeleton" style="height:260px"></div>';
  bindFilterBar(views.trends);
  const ins = await loadInsights();
  view.innerHTML = filterBar(false) + `
    <div class="grid g2">
      <div class="card"><h3 style="margin-bottom:12px">Hashtag terpanas</h3>
        ${(ins.hashtags || []).slice(0, 24).map((h) => `<div class="row spread" style="padding:6px 0;border-bottom:1px solid var(--line)">
          <span>${esc(h.name)}</span><span class="num small dim">${h.ads} iklan</span></div>`).join('') || '<p class="small dim">—</p>'}
      </div>
      <div class="card"><h3 style="margin-bottom:12px">Industri</h3>
        ${table(ins.industries || [], [
          ['Kode', (r) => `<span class="mono tiny">${esc(r.name)}</span>`],
          ['Iklan', (r) => `<span class="num">${r.ads}</span>`],
          ['CTR', (r) => `<span class="num">${fmtPct(r.avg_ctr)}</span>`],
        ])}
      </div>
    </div>`;
  bindFilterBar(views.trends);
};

views.favorites = async () => {
  view.innerHTML = '<div class="skeleton" style="height:200px"></div>';
  await loadFavs();
  const items = state.favs;
  view.innerHTML = `
    <div class="row spread"><span class="small muted">${items.length} item tersimpan</span></div>
    ${items.length ? table(items, [
      ['Jenis', (r) => `<span class="pill">${esc(r.kind)}</span>`],
      ['Ref', (r) => `<span class="mono tiny">${esc(r.ref_id)}</span>`],
      ['Judul', (r) => esc(r.payload?.title || '—')],
      ['Disimpan', (r) => `<span class="small dim">${fmtDate(r.created_at)}</span>`],
      ['', (r) => `<button class="sm danger" data-delfav="${r.id}">Hapus</button>`],
    ]) : emptyBox('Favorit kosong', 'Simpan iklan atau produk dari Top Ads / Radar.')}`;
  $$('[data-delfav]', view).forEach((b) => b.addEventListener('click', async () => {
    await api('/api/auth/favorites/' + b.dataset.delfav, {method: 'DELETE'});
    toast('Dihapus', 'ok'); views.favorites();
  }));
};

views.alerts = async () => {
  view.innerHTML = `
  <div class="card">
    <h3 style="margin-bottom:10px">Buat alert</h3>
    <div class="row">
      <label class="field" style="width:130px">Jenis
        <select id="aKind"><option value="ctr">CTR ≥</option><option value="likes">Likes ≥</option></select>
      </label>
      <label class="field" style="width:130px">Ambang<input id="aVal" type="number" value="2" step="0.1"></label>
      <label class="field" style="width:220px">Label<input id="aLabel" placeholder="mis. jam tangan murah"></label>
      <button class="primary" id="aAdd">Simpan alert</button>
    </div>
    <p class="tiny dim" style="margin-top:8px">Alert dicocokkan tiap kali dashboard / radar memuat data baru. Cek halaman ini setelah sesi riset.</p>
  </div>
  <div class="skeleton" style="height:180px"></div>`;
  $('#aAdd').addEventListener('click', async () => {
    try {
      await api('/api/auth/alerts', {method: 'POST', body: JSON.stringify({
        kind: $('#aKind').value, label: $('#aLabel').value.trim() || 'alert',
        rule: {op: '>=', value: Number($('#aVal').value)},
      })});
      toast('Alert dibuat', 'ok'); views.alerts();
    } catch (e) { toast(e.message, 'err'); }
  });
  const d = await api('/api/auth/alerts');
  const items = d.items || [];
  const box = document.createElement('div');
  box.innerHTML = items.length ? table(items, [
    ['Label', (r) => `<b>${esc(r.label)}</b>`],
    ['Aturan', (r) => `<span class="mono tiny">${esc(r.kind)} ${esc(r.rule.op || '>=')} ${esc(r.rule.value)}</span>`],
    ['Aktif', (r) => r.active ? '<span class="pill ok">aktif</span>' : '<span class="pill">off</span>'],
    ['', (r) => `<button class="sm danger" data-delalert="${r.id}">Hapus</button>`],
  ]) : emptyBox('Belum ada alert', 'Buat alert di atas.');
  view.querySelectorAll('.skeleton').forEach((s) => s.replaceWith(box));
  $$('[data-delalert]', view).forEach((b) => b.addEventListener('click', async () => {
    await api('/api/auth/alerts/' + b.dataset.delalert, {method: 'DELETE'}); toast('Hapus', 'ok'); views.alerts();
  }));
};

views.ai = async () => {
  view.innerHTML = `
  <div class="card">
    <h3 style="margin-bottom:8px">Analisis AI atas set iklan aktif</h3>
    <p class="small muted">Mengirim ${state.ads.length} iklan ke model LLM (gateway dikonfigurasi admin). Model dipilih otomatis dari chain fallback.</p>
    <div class="row" style="margin-top:12px">
      <button class="primary" id="aiGo" ${state.ads.length ? '' : 'disabled'}>Analisis sekarang</button>
      <span class="small dim" id="aiMeta"></span>
    </div>
  </div>
  <div class="card hide" id="aiOut"></div>`;
  if (!state.ads.length) view.innerHTML += emptyBox('Set iklan kosong', 'Muat Top Ads dulu, lalu kembali ke sini.');
  $('#aiGo')?.addEventListener('click', async () => {
    const btn = $('#aiGo');
    btn.disabled = true; btn.innerHTML = '<span class="spin"></span> menganalisis…';
    try {
      const d = await api('/api/ai/analyze', {method: 'POST', body: JSON.stringify({
        ads: state.ads.slice(0, 20), region: state.filters.region, period: state.filters.period,
      })});
      const out = $('#aiOut');
      out.classList.remove('hide');
      out.innerHTML = `<div class="row spread"><h3>Hasil analisis</h3><span class="pill num">${esc(d.model || 'model?')}</span></div>
        <div style="margin-top:12px;white-space:pre-wrap;font-size:13.5px;line-height:1.65">${esc(d.result || '(kosong)')}</div>`;
    } catch (e) { toast(e.message, 'err'); }
    finally { btn.disabled = false; btn.textContent = 'Analisis sekarang'; }
  });
};

views.export = () => {
  const f = state.filters;
  view.innerHTML = `
  <div class="card pad-lg">
    <h3>Export CSV</h3>
    <p class="small muted" style="margin:8px 0 14px">Data mengikuti filter aktif: ${f.period} hari · ${f.region} · urut ${f.order} · 2 halaman (≈60 iklan).</p>
    <div class="row">
      <button class="primary" onclick="location.href='/api/export/csv?period=${f.period}&region=${f.region}&order_by=${f.order}&pages=2'">⤓ Unduh CSV</button>
      <a class="btn" href="/api/snapshots" target="_blank">Lihat snapshot JSON</a>
    </div>
  </div>
  <div class="card"><h3 style="margin-bottom:10px">Kolom yang disertakan</h3>
    <div class="row tight">${['id', 'title', 'brand', 'industry', 'ctr', 'likes', 'cost', 'duration', 'objective', 'hashtags', 'video_url'].map((k) => `<span class="pill mono">${k}</span>`).join('')}</div>
  </div>`;
};

views.settings = () => {
  const u = store.user || {};
  view.innerHTML = `
  <div class="grid g2">
    <div class="card pad-lg">
      <h3>Profil</h3>
      <div class="row" style="margin-top:12px"><span class="pill acc">${esc(u.username || '—')}</span><span class="pill">${esc(u.role || 'user')}</span></div>
      <p class="small muted" style="margin-top:10px">Token sesi disimpan di localStorage dan berlaku 24 jam. Keluar untuk mengakhiri sesi.</p>
      <button class="danger sm" style="margin-top:12px" onclick="document.getElementById('navOut').click()">Keluar</button>
    </div>
    <div class="card pad-lg">
      <h3>Sumber data</h3>
      <div class="row" style="margin-top:12px;gap:8px">
        <span class="pill ok">Creative Center · live</span>
        <span class="pill warn">FastMoss · butuh kredensial admin</span>
        <span class="pill warn">TikTok Shop · butuh app approval</span>
      </div>
      <p class="small muted" style="margin-top:12px">Modul FastMoss dan TikTok Shop menyala otomatis begitu admin mengisi kredensial di Admin Panel.</p>
    </div>
  </div>`;
};

views.keys = async () => {
  view.innerHTML = `
  <div class="card">
    <h3 style="margin-bottom:10px">Buat API key</h3>
    <div class="row">
      <label class="field" style="width:200px">Nama<input id="kName" placeholder="bot / n8n / sheet"></label>
      <button class="primary" id="kGo">Generate</button>
    </div>
  </div>
  <div class="skeleton" style="height:160px"></div>`;
  $('#kGo').addEventListener('click', async () => {
    try {
      const d = await api('/api/auth/keys', {method: 'POST', body: JSON.stringify({name: $('#kName').value.trim()})});
      toast('Key dibuat: ' + d.key, 'ok'); views.keys();
    } catch (e) { toast(e.message, 'err'); }
  });
  const d = await api('/api/auth/keys');
  const box = document.createElement('div');
  box.innerHTML = (d.keys || []).length ? table(d.keys, [
    ['Nama', (r) => esc(r.name || '—')],
    ['Key', (r) => `<span class="mono tiny">${esc(r.key)}</span>`],
    ['Scope', (r) => `<span class="mono tiny">${esc(JSON.stringify(r.scopes))}</span>`],
    ['Dibuat', (r) => `<span class="small dim">${fmtDate(r.created_at)}</span>`],
  ]) : emptyBox('Belum ada key', 'Generate key untuk akses API dari script.');
  view.querySelectorAll('.skeleton').forEach((s) => s.replaceWith(box));
};

// ---------------------------------------------------------------- boot
async function boot() {
  if (!store.token) { location.href = '/'; return; }
  try {
    const me = await api('/api/auth/me');
    $('#userPill').textContent = me.user.username + ' · ' + me.user.role;
    if (me.user.role === 'admin') $('#navAdmin').style.display = '';
    $('#sideFoot').textContent = 'v2.0 · Creative Center live';
  } catch (e) { return; }
  $$('.nav-item[data-view]')[0]?.classList.add('active');
  await Promise.all([loadFavs()]);
  const hash = (location.hash || '').replace('#', '');
  if (hash && views[hash]) {
    state.view = hash;
    $$('.nav-item').forEach((n) => n.classList.toggle('active', n.dataset.view === hash));
    $('#viewTitle').textContent = titles[hash];
  }
  render();
}

async function render() {
  const v = views[state.view] || views.dashboard;
  try { await v(); } catch (e) {
    view.innerHTML = emptyBox('Gagal memuat', e.message);
  }
}

window.go = (v) => { state.view = v; $('#viewTitle').textContent = titles[v]; render(); };
boot();
})();
