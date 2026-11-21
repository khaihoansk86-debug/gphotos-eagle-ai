let token = '';
let currentProfile = '';
let cachedProfiles = [];
let cachedPhotoStatus = {};
let cachedAlbums = [];
let cachedMcpTools = [];
let currentEaglePath = '';
let localTaskRunning = false;
let progressTimer = null;
let currentPct = 0;

const $ = id => document.getElementById(id);

const AVATAR_GRADIENTS = [
  'linear-gradient(135deg, #0a84ff, #5e5ce6)',
  'linear-gradient(135deg, #30d158, #00c7be)',
  'linear-gradient(135deg, #ff9f0a, #ff375f)',
  'linear-gradient(135deg, #bf5af2, #5e5ce6)',
  'linear-gradient(135deg, #38bdf8, #0284c7)',
  'linear-gradient(135deg, #f43f5e, #ec4899)'
];

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

function escapeJs(str) {
  return String(str || '').replace(/\\/g, '\\\\').replace(/'/g, "\\'");
}

function getInitials(name) {
  const parts = String(name || 'P').trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  return String(name || 'P').slice(0, 2).toUpperCase();
}

function getGradient(seed) {
  let h = 0;
  const s = String(seed || '');
  for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
  return AVATAR_GRADIENTS[h % AVATAR_GRADIENTS.length];
}

function upgradeAvatarUrl(url) {
  if (!url) return '';
  return String(url).replace(/=s\d+-c/i, '=s96-c');
}

function renderAvatarInner(name, avatarUrl) {
  const initials = escapeHtml(getInitials(name));
  const hiRes = upgradeAvatarUrl(avatarUrl);
  if (hiRes) {
    return `<img src="${escapeHtml(hiRes)}" alt="${escapeHtml(name)}" referrerpolicy="no-referrer" onerror="this.remove();this.parentElement.innerHTML='<span class=\\'avatar-initials\\'>${initials}</span>';">`;
  }
  return `<span class="avatar-initials">${initials}</span>`;
}

function parseAccountMeta(st) {
  if (!st) return { email: '', displayName: '' };
  const email = st.account_email || st.account_key || '';
  let displayName = st.account_name || '';
  if (!displayName && st.account_label) {
    const m = String(st.account_label).match(/Google:\s*([^\n(]+)/i);
    if (m) displayName = m[1].trim();
  }
  return { email, displayName };
}

// -------------------------------------------------------------
// iOS LIVE ACTIVITY / PROGRESS BAR CONTROLLER
// -------------------------------------------------------------
function setLiveActivity(mode, text, percent = null) {
  const bar = $('liveActivityBar');
  const spinner = $('liveActivitySpinner');
  const dot = $('liveActivityDot');
  const txtEl = $('liveActivityText');
  const pctEl = $('liveActivityPercent');
  const fill = $('liveProgressFill');
  if (!bar) return;

  bar.classList.remove('is-idle', 'is-running', 'is-done', 'is-error');
  bar.classList.add(`is-${mode}`);

  if (txtEl) txtEl.textContent = text;

  if (mode === 'running') {
    if (spinner) spinner.style.display = 'inline-block';
    if (dot) dot.style.display = 'none';
    const pct = Math.max(5, Math.min(99, Math.round(percent ?? 15)));
    currentPct = pct;
    if (pctEl) pctEl.textContent = `${pct}%`;
    if (fill) fill.style.width = `${pct}%`;
  } else if (mode === 'done') {
    if (spinner) spinner.style.display = 'none';
    if (dot) dot.style.display = 'inline-block';
    if (pctEl) pctEl.textContent = '100%';
    if (fill) fill.style.width = '100%';
  } else if (mode === 'error') {
    if (spinner) spinner.style.display = 'none';
    if (dot) dot.style.display = 'inline-block';
    if (pctEl) pctEl.textContent = 'Lỗi';
    if (fill) fill.style.width = '100%';
  } else {
    if (spinner) spinner.style.display = 'none';
    if (dot) dot.style.display = 'inline-block';
    if (pctEl) pctEl.textContent = 'Sẵn sàng';
    if (fill) fill.style.width = '0%';
  }
}

function startLiveTask(text, startPct = 18, maxAutoPct = 88) {
  clearInterval(progressTimer);
  clearTimeout(window._idleResetTimer);
  localTaskRunning = true;
  setLiveActivity('running', text, startPct);
  progressTimer = setInterval(() => {
    if (!localTaskRunning) return;
    if (currentPct < maxAutoPct) {
      const step = currentPct < 50 ? 7 : (currentPct < 75 ? 4 : 1.5);
      setLiveActivity('running', text, Math.min(maxAutoPct, currentPct + step));
    }
  }, 550);
}

function finishLiveTask(text, isError = false) {
  clearInterval(progressTimer);
  localTaskRunning = false;
  setLiveActivity(isError ? 'error' : 'done', text, 100);
  clearTimeout(window._idleResetTimer);
  window._idleResetTimer = setTimeout(() => {
    if (!localTaskRunning) {
      setLiveActivity('idle', 'Sẵn sàng · Kết nối MCP Gateway (8898) hoạt động ổn định');
    }
  }, 3200);
}

function showToast(text, isError = false) {
  const el = $('toast');
  if (!el) return;
  el.textContent = text;
  el.style.display = 'block';
  el.style.borderColor = isError ? 'rgba(255,69,58,0.55)' : 'rgba(48,209,88,0.55)';
  el.style.color = isError ? '#fca5a5' : '#86efac';
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => {
    el.style.display = 'none';
  }, 4200);
}

async function api(command, data = {}) {
  if (!token) {
    const s = await (await fetch('/api/state')).json();
    token = s.token;
  }
  const resp = await fetch(`/api/${command}`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Local-Token': token
    },
    body: JSON.stringify(data)
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok || body.status === 'error') {
    throw new Error(body.error || body.message || `Lỗi thực thi (${resp.status})`);
  }
  return body;
}

// -------------------------------------------------------------
// RENDER PROFILES (COMPACT SCROLLABLE AVATAR GRID)
// -------------------------------------------------------------
function renderProfiles(query = '') {
  const listEl = $('profileListContainer');
  const profiles = cachedProfiles;
  const activeId = currentProfile;
  const photoStatus = cachedPhotoStatus;

  const activeObj = profiles.find(p => p.id === activeId) || profiles[0];
  if (activeObj) {
    const st = photoStatus?.[activeObj.id] || {};
    const { email, displayName } = parseAccountMeta(st);
    const avatarUrl = st.avatar_url || '';
    const grad = getGradient(activeObj.name);

    if ($('activeProfileTitle')) $('activeProfileTitle').textContent = activeObj.name;
    if ($('activeAccountMeta')) {
      $('activeAccountMeta').textContent = (email || displayName)
        ? `${displayName ? displayName + ' · ' : ''}${email}`
        : 'Chưa đăng nhập Chrome · Bấm "Mở Đăng Nhập" để kết nối';
    }
    if ($('activeProfileAvatarWrap')) {
      $('activeProfileAvatarWrap').style.background = grad;
      $('activeProfileAvatarWrap').innerHTML = renderAvatarInner(displayName || activeObj.name, avatarUrl);
    }
    if ($('statsProfileName')) $('statsProfileName').textContent = activeObj.name;
    if ($('statsAvatarMini')) {
      $('statsAvatarMini').style.background = grad;
      $('statsAvatarMini').innerHTML = renderAvatarInner(displayName || activeObj.name, avatarUrl);
    }
  }

  const q = (query || $('profileSearchInput')?.value || '').trim().toLowerCase();
  const filtered = q
    ? profiles.filter(p => {
        const st = photoStatus?.[p.id] || {};
        const { email, displayName } = parseAccountMeta(st);
        return `${p.name} ${email} ${displayName}`.toLowerCase().includes(q);
      })
    : profiles;

  if ($('profileCountBadge')) {
    $('profileCountBadge').textContent = `${filtered.length} profile`;
  }

  if (!listEl) return;
  if (!filtered.length) {
    listEl.innerHTML = '<div style="padding:18px;text-align:center;color:var(--text-secondary);grid-column:1/-1;font-size:13px;">Không tìm thấy profile phù hợp.</div>';
    return;
  }

  const canDelete = profiles.length > 1;
  listEl.innerHTML = filtered.map(p => {
    const isAct = p.id === activeId;
    const st = photoStatus?.[p.id] || {};
    const { email, displayName } = parseAccountMeta(st);
    const avatarUrl = st.avatar_url || '';
    const grad = getGradient(p.name);
    const subText = email || displayName || 'Chưa liên kết Gmail';

    return `
      <div class="profile-tile ${isAct ? 'active' : ''}" onclick="selectProfile('${escapeJs(p.id)}')" title="Bấm để chọn profile ${escapeHtml(p.name)}">
        <div class="profile-tile-left">
          <div class="avatar-ring avatar-md" style="background:${grad};">
            ${renderAvatarInner(displayName || p.name, avatarUrl)}
          </div>
          <div class="profile-tile-info">
            <div class="profile-tile-name">
              <span style="overflow:hidden;text-overflow:ellipsis;">${escapeHtml(p.name)}</span>
              ${isAct ? '<span class="active-check">Đang dùng</span>' : ''}
            </div>
            <div class="profile-tile-sub">${escapeHtml(subText)}</div>
          </div>
        </div>
        <div class="profile-tile-actions" onclick="event.stopPropagation();">
          <button class="ios-btn btn-glass-blue btn-icon-only" onclick="openChromeProfile('${escapeJs(p.id)}')" title="Mở Chrome đăng nhập Google Photos">🌐</button>
          <button class="ios-btn btn-danger-soft btn-icon-only" ${!canDelete ? 'disabled' : ''} onclick="deleteProfile('${escapeJs(p.id)}', '${escapeJs(p.name)}')" title="Xóa profile này">🗑️</button>
        </div>
      </div>
    `;
  }).join('');
}

// -------------------------------------------------------------
// RENDER EAGLE LIBRARY
// -------------------------------------------------------------
function renderEagle(state) {
  const badge = $('eagleConnBadge');
  const pathMeta = $('eaglePathMeta');
  const sel = $('eagleLibrarySelect');
  const info = state.eagle_info || {};
  const libs = state.eagle_libraries || [];
  const stats = state.eagle_stats || {};

  currentEaglePath = info.path || '';

  if (badge) {
    badge.className = 'ios-status-pill ' + (state.eagle_connected ? 'online' : 'offline');
    badge.textContent = state.eagle_connected ? '🟢 Online' : '🔴 Chưa bật';
  }
  if (pathMeta) {
    pathMeta.textContent = info.path ? info.path : 'Hãy mở ứng dụng Eagle để kết nối thư viện';
  }
  if ($('statsEagleName')) {
    $('statsEagleName').textContent = info.name ? `${info.name}.library` : 'Chưa kết nối';
  }

  if (sel) {
    if (libs.length > 0) {
      const sig = libs.map(l => l.path).join('|') + '::' + currentEaglePath;
      if (sel.dataset.sig !== sig) {
        sel.innerHTML = libs.map(lib => {
          const isCur = currentEaglePath && lib.path.toLowerCase() === currentEaglePath.toLowerCase();
          return `<option value="${escapeHtml(lib.path)}" ${isCur ? 'selected' : ''}>${escapeHtml(lib.name)} — ${escapeHtml(lib.path)}${isCur ? ' (Đang mở)' : ''}</option>`;
        }).join('');
        sel.dataset.sig = sig;
      }
    } else if (info.path) {
      sel.innerHTML = `<option value="${escapeHtml(info.path)}">${escapeHtml(info.name || 'Eagle')} — ${escapeHtml(info.path)}</option>`;
    } else {
      sel.innerHTML = '<option value="">Không tìm thấy thư viện Eagle (Hãy bật ứng dụng Eagle)</option>';
    }
  }

  const total = stats.total || 0;
  const photos = stats.photos || 0;
  const videos = stats.videos || 0;
  const folders = stats.folders || Object.keys(state.eagle_folders || {}).length || 0;

  if ($('statEagleTotal')) $('statEagleTotal').textContent = total.toLocaleString('vi-VN');
  if ($('statEaglePhotos')) $('statEaglePhotos').textContent = photos.toLocaleString('vi-VN');
  if ($('statEagleVideos')) $('statEagleVideos').textContent = videos.toLocaleString('vi-VN');
  if ($('statEagleFolders')) $('statEagleFolders').textContent = folders.toLocaleString('vi-VN');
}

// -------------------------------------------------------------
// RENDER GOOGLE PHOTOS STATS + SYNC BACKEND LIVE PROGRESS
// -------------------------------------------------------------
function renderPhotoStatsAndProgress(state, activeId) {
  const invObj = state.photo_inventory?.[activeId]?.inventory || {};
  const counts = invObj.counts || {};
  const photoCnt = counts.photo || 0;
  const videoCnt = counts.video || 0;
  const albumCnt = state.albums_count !== undefined ? state.albums_count : (counts.albums || 0);

  if ($('statPhotosCount')) $('statPhotosCount').textContent = photoCnt.toLocaleString('vi-VN');
  if ($('statVideosCount')) $('statVideosCount').textContent = videoCnt.toLocaleString('vi-VN');
  if ($('statAlbumsCount')) $('statAlbumsCount').textContent = albumCnt.toLocaleString('vi-VN');

  cachedAlbums = state.albums || [];
  if ($('albumsModal')?.style.display === 'flex') {
    renderAlbumsList();
  }

  // Sync live backend background task if no local foreground task is active
  if (!localTaskRunning) {
    const runningOps = (state.operations || []).filter(op => op.status === 'running');
    if (invObj.status === 'running') {
      const step = invObj.step || 0;
      const pct = Math.min(98, Math.max(8, Math.round((step / 300) * 100)));
      setLiveActivity('running', `Đang quét kho Google Photos (Bước ${step}/300 · Đã thấy ${(photoCnt + videoCnt).toLocaleString('vi-VN')} mục)...`, pct);
    } else if (runningOps.length > 0) {
      const op = runningOps[0];
      const pct = op.progress ?? 50;
      setLiveActivity('running', op.message || `Đang chạy tác vụ nền: ${op.name || 'Xử lý dữ liệu'}...`, pct);
    }
  }
}

// -------------------------------------------------------------
// REFRESH STATE
// -------------------------------------------------------------
async function refresh() {
  try {
    const resp = await fetch('/api/state', { cache: 'no-store' });
    if (!resp.ok) return;
    const state = await resp.json();
    token = state.token;

    cachedProfiles = state.profiles || [];
    cachedPhotoStatus = state.photo_status || {};

    if (state.selected_profile) {
      currentProfile = state.selected_profile;
    } else if (cachedProfiles.length) {
      currentProfile = cachedProfiles[0].id;
    }

    renderProfiles();
    renderEagle(state);
    renderPhotoStatsAndProgress(state, currentProfile);

    if (state.mcp) {
      cachedMcpTools = state.mcp.tools || [];
      if ($('mcpStatusLabel')) {
        $('mcpStatusLabel').textContent = `MCP: 8898 (${state.mcp.tools_count || cachedMcpTools.length} Tools)`;
      }
    }
  } catch (err) {
    console.warn('Refresh error:', err);
  }
}

// -------------------------------------------------------------
// PROFILE ACTIONS (GLOBAL)
// -------------------------------------------------------------
window.selectProfile = async function(pid) {
  if (pid === currentProfile) return;
  startLiveTask('Đang chuyển profile Google Photos...', 35, 85);
  try {
    await api('profile-select', { profile_id: pid });
    currentProfile = pid;
    await refresh();
    finishLiveTask('Đã chuyển profile Google Photos thành công!');
    showToast('✅ Đã chuyển profile Google Photos!');
  } catch (err) {
    finishLiveTask(`Lỗi chuyển profile: ${err.message}`, true);
    showToast(err.message, true);
  }
};

window.openChromeProfile = async function(pid) {
  startLiveTask('Đang mở trình duyệt Chrome cho profile Google Photos...', 40, 90);
  try {
    await api('open-chrome', { profile_id: pid });
    finishLiveTask('Đã mở cửa sổ Chrome đăng nhập Google Photos!');
    showToast('🌐 Đã mở Chrome đăng nhập Google Photos!');
  } catch (err) {
    finishLiveTask(`Lỗi mở trình duyệt: ${err.message}`, true);
    showToast(err.message, true);
  }
};

window.deleteProfile = async function(pid, name) {
  if (!confirm(`Bạn có chắc muốn xóa profile "${name}" không?`)) return;
  startLiveTask(`Đang xóa profile "${name}"...`, 35, 85);
  try {
    const res = await api('profile-delete', { profile_id: pid });
    if (res.selected_profile) currentProfile = res.selected_profile;
    await refresh();
    finishLiveTask(`Đã xóa profile "${name}"!`);
    showToast(`🗑️ Đã xóa profile "${name}"!`);
  } catch (err) {
    finishLiveTask(`Không thể xóa profile: ${err.message}`, true);
    showToast(err.message, true);
  }
};

// -------------------------------------------------------------
// ALBUMS MODAL
// -------------------------------------------------------------
function renderAlbumsList(query = '') {
  const container = $('albumsListContainer');
  if (!container) return;
  const q = (query || $('albumSearchInput')?.value || '').trim().toLowerCase();
  const filtered = q ? cachedAlbums.filter(a => (a.title || '').toLowerCase().includes(q)) : cachedAlbums;
  const totalItems = filtered.reduce((sum, a) => sum + (a.item_count || 0), 0);

  if ($('albumsModalSummary')) {
    $('albumsModalSummary').textContent = `${filtered.length} album · ${totalItems.toLocaleString('vi-VN')} tư liệu`;
  }

  if (!filtered.length) {
    container.innerHTML = '<div style="padding:28px;text-align:center;color:var(--text-secondary);">Không tìm thấy album nào. Bấm "Quét lại Album" để đồng bộ từ Google Photos.</div>';
    return;
  }

  container.innerHTML = filtered.map(al => `
    <div class="album-row">
      <div style="min-width:0;flex:1;">
        <div class="album-row-title">${escapeHtml(al.title || 'Album không tên')}</div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="album-row-count">${(al.item_count || 0).toLocaleString('vi-VN')} mục</span>
        ${al.album_url ? `<a href="${escapeHtml(al.album_url)}" target="_blank" class="ios-btn btn-glass btn-sm" style="text-decoration:none;">🌐 Mở</a>` : ''}
      </div>
    </div>
  `).join('');
}

function openAlbumsModal() {
  $('albumsModalBackdrop').style.display = 'block';
  $('albumsModal').style.display = 'flex';
  renderAlbumsList();
}

function closeAlbumsModal() {
  $('albumsModalBackdrop').style.display = 'none';
  $('albumsModal').style.display = 'none';
}

// -------------------------------------------------------------
// MCP HUB MODAL
// -------------------------------------------------------------
function renderMcpTools(query = '') {
  const container = $('mcpToolsList');
  if (!container) return;
  const q = (query || $('mcpToolSearchInput')?.value || '').trim().toLowerCase();
  const filtered = q
    ? cachedMcpTools.filter(t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q))
    : cachedMcpTools;

  container.innerHTML = filtered.map(t => `
    <div class="mcp-tool-row" style="flex-direction:column;align-items:flex-start;gap:3px;">
      <div class="mcp-tool-name">${escapeHtml(t.name)}</div>
      <div class="mcp-tool-desc">${escapeHtml(t.description)}</div>
    </div>
  `).join('');
}

function openMcpModal() {
  $('mcpModalBackdrop').style.display = 'block';
  $('mcpHubModal').style.display = 'flex';
  renderMcpTools();
}

function closeMcpModal() {
  $('mcpModalBackdrop').style.display = 'none';
  $('mcpHubModal').style.display = 'none';
}

// -------------------------------------------------------------
// BOOTSTRAP EVENTS
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  startLiveTask('Đang tải trạng thái Profile, Eagle & MCP Gateway...', 30, 85);
  await refresh();
  finishLiveTask('Đã đồng bộ dữ liệu sẵn sàng!');

  // Search profiles live
  $('profileSearchInput')?.addEventListener('input', e => renderProfiles(e.target.value));

  // Create new profile
  const doCreateProfile = async () => {
    const inp = $('newProfileNameInput');
    const name = (inp?.value || '').trim();
    if (!name) {
      showToast('Vui lòng nhập tên profile mới', true);
      inp?.focus();
      return;
    }
    startLiveTask(`Đang tạo profile mới "${name}"...`, 30, 85);
    try {
      const res = await api('profile-create', { name });
      if (res.profile_id) currentProfile = res.profile_id;
      inp.value = '';
      await refresh();
      finishLiveTask(`Đã tạo thành công profile "${name}"!`);
      showToast(`✅ Đã tạo profile "${name}"!`);
    } catch (err) {
      finishLiveTask(`Lỗi tạo profile: ${err.message}`, true);
      showToast(err.message, true);
    }
  };
  $('btnCreateProfile')?.addEventListener('click', doCreateProfile);
  $('newProfileNameInput')?.addEventListener('keydown', e => {
    if (e.key === 'Enter') doCreateProfile();
  });

  // Open Chrome login for active profile
  $('btnOpenPhotosChrome')?.addEventListener('click', () => {
    if (currentProfile) openChromeProfile(currentProfile);
  });

  // Scan Photos & Albums
  $('btnScanPhotosProfile')?.addEventListener('click', async () => {
    if (!currentProfile) return;
    startLiveTask('Bước 1/2: Đang đọc thông tin tài khoản & ảnh đại diện Google Photos...', 20, 50);
    try {
      await api('photos-refresh', { profile_id: currentProfile }).catch(() => {});
      setLiveActivity('running', 'Bước 2/2: Đang quét toàn bộ danh sách Album Google Photos...', 58);
      const res = await api('photos-scan-albums', { profile_id: currentProfile });
      const cnt = res?.albums?.total_albums ?? '';
      await refresh();
      finishLiveTask(`Đã cập nhật xong kho Photos${cnt !== '' ? ` (${cnt} album)` : ''}!`);
      showToast(`✅ Đã cập nhật kho Photos${cnt !== '' ? ` (${cnt} album)` : ''}!`);
    } catch (err) {
      finishLiveTask(`Lỗi quét Photos: ${err.message}`, true);
      showToast(err.message, true);
    }
  });

  // Eagle library selector
  $('eagleLibrarySelect')?.addEventListener('change', async e => {
    const libPath = e.target.value;
    if (!libPath) return;
    startLiveTask('Đang chuyển thư viện Eagle DAM...', 30, 88);
    try {
      await api('eagle-select', { library_path: libPath });
      await refresh();
      finishLiveTask('Đã chuyển thư viện Eagle thành công!');
      showToast('🦅 Đã chuyển thư viện Eagle!');
    } catch (err) {
      finishLiveTask(`Lỗi chuyển thư viện Eagle: ${err.message}`, true);
      showToast(err.message, true);
    }
  });

  // Open Eagle folder
  $('btnOpenEagleDirect')?.addEventListener('click', async () => {
    startLiveTask('Đang mở thư viện Eagle DAM...', 45, 90);
    try {
      const res = await api('open-eagle', { library_path: currentEaglePath });
      finishLiveTask(res.message || 'Đã mở thư mục Eagle DAM!');
      showToast('📂 ' + (res.message || 'Đã mở Eagle DAM!'));
    } catch (err) {
      finishLiveTask(`Lỗi mở Eagle: ${err.message}`, true);
      showToast(err.message, true);
    }
  });

  // Refresh Eagle stats
  $('btnRefreshEagle')?.addEventListener('click', async () => {
    startLiveTask('Đang đọc lại toàn bộ số liệu thư viện Eagle DAM...', 25, 88);
    try {
      await api('eagle-refresh');
      await refresh();
      finishLiveTask('Đã cập nhật số liệu Eagle DAM!');
      showToast('✅ Đã cập nhật số liệu Eagle!');
    } catch (err) {
      finishLiveTask(`Lỗi làm mới Eagle: ${err.message}`, true);
      showToast(err.message, true);
    }
  });

  // Refresh All
  $('btnRefreshAll')?.addEventListener('click', async () => {
    startLiveTask('Đang làm mới toàn bộ số liệu Photos, Eagle và MCP...', 25, 88);
    await api('eagle-refresh').catch(() => {});
    await refresh();
    finishLiveTask('Đã làm mới toàn bộ số liệu!');
    showToast('✅ Đã làm mới toàn bộ số liệu!');
  });

  // System Update Tool (git pull)
  $('btnSystemUpdate')?.addEventListener('click', async () => {
    const btn = $('btnSystemUpdate');
    if (btn) btn.disabled = true;
    startLiveTask('Đang tải bản cập nhật mới nhất từ GitHub (git pull)...', 15, 92);
    try {
      const res = await api('system-update');
      await refresh();
      finishLiveTask(`Cập nhật thành công: ${res.detail || 'Đã ở bản mới nhất'}`);
      showToast(`✅ ${res.message}`);
    } catch (err) {
      finishLiveTask(`Lỗi cập nhật Tool: ${err.message}`, true);
      showToast(err.message, true);
    } finally {
      if (btn) btn.disabled = false;
    }
  });

  // Albums modal triggers
  $('btnOpenAlbumsModal')?.addEventListener('click', openAlbumsModal);
  $('btnCloseAlbumsModal')?.addEventListener('click', closeAlbumsModal);
  $('albumsModalBackdrop')?.addEventListener('click', closeAlbumsModal);
  $('albumSearchInput')?.addEventListener('input', e => renderAlbumsList(e.target.value));
  $('btnRescanAlbums')?.addEventListener('click', async () => {
    startLiveTask('Đang quét lại toàn bộ danh sách Album từ Google Photos...', 20, 90);
    try {
      const res = await api('photos-scan-albums', { profile_id: currentProfile });
      await refresh();
      renderAlbumsList();
      finishLiveTask(`Đã quét xong ${res?.albums?.total_albums || 0} album!`);
      showToast(`✅ Đã quét xong ${res?.albums?.total_albums || 0} album!`);
    } catch (err) {
      finishLiveTask(`Lỗi quét album: ${err.message}`, true);
      showToast(err.message, true);
    }
  });

  // MCP modal triggers
  $('btnOpenMcpHub')?.addEventListener('click', openMcpModal);
  $('btnDownloadConnectOpen')?.addEventListener('click', openMcpModal);
  $('btnCloseMcpModal')?.addEventListener('click', closeMcpModal);
  $('mcpModalBackdrop')?.addEventListener('click', closeMcpModal);
  $('mcpToolSearchInput')?.addEventListener('input', e => renderMcpTools(e.target.value));
  $('btnCopyMcpConfig')?.addEventListener('click', async () => {
    const cfg = JSON.stringify({
      mcpServers: {
        'gphotos-content-vision': { url: 'http://127.0.0.1:8898/mcp' }
      }
    }, null, 2);
    try {
      await navigator.clipboard.writeText(cfg);
      showToast('📋 Đã sao chép JSON cấu hình MCP!');
    } catch {
      showToast('Endpoint MCP: http://127.0.0.1:8898/mcp');
    }
  });

  // Auto-refresh every 6 seconds to catch live background scans
  setInterval(refresh, 6000);
});
