let token = '';
let currentProfile = '';
let cachedAlbums = [];
let cachedMcpTools = [];
let currentEaglePath = '';

const $ = id => document.getElementById(id);

function showToast(text, isError = false) {
  const el = $('toast');
  if (!el) return;
  el.textContent = text;
  el.style.display = 'block';
  el.style.borderColor = isError ? 'rgba(239,68,68,0.6)' : 'rgba(34,197,94,0.6)';
  el.style.color = isError ? '#fca5a5' : '#86efac';
  clearTimeout(window._toastTimer);
  window._toastTimer = setTimeout(() => {
    el.style.display = 'none';
  }, 4500);
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

// -------------------------------------------------------------
// RENDER PROFILES
// -------------------------------------------------------------
function renderProfiles(profiles, activeId, photoStatus) {
  const sel = $('photoProfileSelect');
  const listEl = $('profileListContainer');
  if (!Array.isArray(profiles)) return;

  if (sel) {
    const sig = profiles.map(p => `${p.id}:${p.name}`).join('|');
    if (sel.dataset.sig !== sig) {
      sel.innerHTML = profiles.map(p => `<option value="${escapeHtml(p.id)}">${escapeHtml(p.name)}</option>`).join('');
      sel.dataset.sig = sig;
    }
    if (profiles.some(p => p.id === activeId)) {
      sel.value = activeId;
    }
  }

  const activeObj = profiles.find(p => p.id === activeId) || profiles[0];
  const st = photoStatus?.[activeId] || {};
  const accEmail = st.account_email || st.account_key || '';
  const accName = st.account_name || '';
  if ($('activeAccountMeta')) {
    if (accEmail || accName) {
      $('activeAccountMeta').textContent = `Tài khoản: ${accName ? accName + ' · ' : ''}${accEmail}`;
    } else if (activeObj) {
      $('activeAccountMeta').textContent = `Đang chọn: ${activeObj.name}`;
    }
  }
  if ($('statsProfileName') && activeObj) {
    $('statsProfileName').textContent = activeObj.name;
  }

  if (listEl) {
    const canDelete = profiles.length > 1;
    listEl.innerHTML = profiles.map(p => {
      const isAct = p.id === activeId;
      const pSt = photoStatus?.[p.id] || {};
      const subEmail = pSt.account_email || pSt.account_key || '';
      return `
        <div class="profile-row ${isAct ? 'active' : ''}">
          <div class="profile-row-info">
            <span>${isAct ? '🟢' : '📁'}</span>
            <div>
              <div style="display:flex;align-items:center;gap:8px;">
                <span class="profile-name">${escapeHtml(p.name)}</span>
                ${isAct ? '<span class="profile-badge-active">Đang dùng</span>' : ''}
              </div>
              <div class="profile-id-sub">${subEmail ? escapeHtml(subEmail) + ' · ' : ''}ID: ${escapeHtml(p.id.slice(0, 14))}</div>
            </div>
          </div>
          <div class="profile-row-actions">
            ${!isAct ? `<button class="btn btn-secondary btn-sm" onclick="selectProfile('${escapeJs(p.id)}')">Chọn</button>` : ''}
            <button class="btn btn-info btn-sm" onclick="openChromeProfile('${escapeJs(p.id)}')" title="Mở trình duyệt đăng nhập Google Photos">🌐 Mở</button>
            <button class="btn btn-danger btn-sm" ${!canDelete ? 'disabled' : ''} onclick="deleteProfile('${escapeJs(p.id)}', '${escapeJs(p.name)}')" title="Xóa profile này">🗑️ Xóa</button>
          </div>
        </div>
      `;
    }).join('');
  }
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
    badge.className = 'status-badge ' + (state.eagle_connected ? 'online' : 'offline');
    badge.textContent = state.eagle_connected ? '🟢 Đã kết nối Eagle' : '🔴 Chưa bật Eagle';
  }
  if (pathMeta) {
    pathMeta.textContent = info.path ? `Đường dẫn: ${info.path}` : 'Hãy mở ứng dụng Eagle để đồng bộ thư viện';
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
      sel.innerHTML = '<option value="">Không tìm thấy thư viện Eagle (Hãy bật Eagle)</option>';
    }
  }

  // Eagle Stats
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
// RENDER GOOGLE PHOTOS STATS
// -------------------------------------------------------------
function renderPhotoStats(state, activeId) {
  const inv = state.photo_inventory?.[activeId]?.inventory?.counts || {};
  const photoCnt = inv.photo || 0;
  const videoCnt = inv.video || 0;
  const albumCnt = state.albums_count !== undefined ? state.albums_count : (inv.albums || 0);

  if ($('statPhotosCount')) $('statPhotosCount').textContent = photoCnt.toLocaleString('vi-VN');
  if ($('statVideosCount')) $('statVideosCount').textContent = videoCnt.toLocaleString('vi-VN');
  if ($('statAlbumsCount')) $('statAlbumsCount').textContent = albumCnt.toLocaleString('vi-VN');

  cachedAlbums = state.albums || [];
  if ($('albumsModal')?.style.display === 'flex') {
    renderAlbumsList();
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

    if (state.selected_profile) {
      currentProfile = state.selected_profile;
    } else if (state.profiles?.length) {
      currentProfile = state.profiles[0].id;
    }

    renderProfiles(state.profiles || [], currentProfile, state.photo_status || {});
    renderEagle(state);
    renderPhotoStats(state, currentProfile);

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
// PROFILE ACTIONS (GLOBAL FOR INLINE HANDLERS)
// -------------------------------------------------------------
window.selectProfile = async function(pid) {
  try {
    await api('profile-select', { profile_id: pid });
    currentProfile = pid;
    showToast('✅ Đã chuyển profile Google Photos!');
    await refresh();
  } catch (err) {
    showToast(err.message, true);
  }
};

window.openChromeProfile = async function(pid) {
  showToast('🌐 Đang mở Chrome cho profile Google Photos...');
  try {
    await api('open-chrome', { profile_id: pid });
    showToast('✅ Đã mở cửa sổ Google Photos để đăng nhập!');
  } catch (err) {
    showToast(err.message, true);
  }
};

window.deleteProfile = async function(pid, name) {
  if (!confirm(`Bạn có chắc muốn xóa profile "${name}" không?`)) return;
  try {
    const res = await api('profile-delete', { profile_id: pid });
    if (res.selected_profile) currentProfile = res.selected_profile;
    showToast(`✅ Đã xóa profile "${name}"!`);
    await refresh();
  } catch (err) {
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
    container.innerHTML = '<div style="padding:28px;text-align:center;color:var(--text-muted);">Không tìm thấy album nào. Bấm "Quét lại Album" để đồng bộ từ Google Photos.</div>';
    return;
  }

  container.innerHTML = filtered.map(al => `
    <div class="album-row">
      <div style="min-width:0;flex:1;">
        <div class="album-row-title">${escapeHtml(al.title || 'Album không tên')}</div>
      </div>
      <div style="display:flex;align-items:center;gap:10px;">
        <span class="album-row-count">${(al.item_count || 0).toLocaleString('vi-VN')} mục</span>
        ${al.album_url ? `<a href="${escapeHtml(al.album_url)}" target="_blank" class="btn btn-secondary btn-sm" style="text-decoration:none;">🌐 Mở</a>` : ''}
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
  await refresh();

  // Profile selector dropdown
  $('photoProfileSelect')?.addEventListener('change', e => {
    selectProfile(e.target.value);
  });

  // Create new profile
  const doCreateProfile = async () => {
    const inp = $('newProfileNameInput');
    const name = (inp?.value || '').trim();
    if (!name) {
      showToast('Vui lòng nhập tên profile mới', true);
      inp?.focus();
      return;
    }
    try {
      const res = await api('profile-create', { name });
      if (res.profile_id) currentProfile = res.profile_id;
      inp.value = '';
      showToast(`✅ Đã tạo profile "${name}"!`);
      await refresh();
    } catch (err) {
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

  // Scan Photos & Albums for active profile
  $('btnScanPhotosProfile')?.addEventListener('click', async () => {
    if (!currentProfile) return;
    showToast('🔄 Đang quét thông tin tài khoản và danh sách Album...');
    try {
      await api('photos-refresh', { profile_id: currentProfile }).catch(() => {});
      const res = await api('photos-scan-albums', { profile_id: currentProfile });
      const cnt = res?.albums?.total_albums ?? '';
      showToast(`✅ Đã cập nhật xong kho Photos${cnt !== '' ? ` (${cnt} album)` : ''}!`);
      await refresh();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // Eagle library selector
  $('eagleLibrarySelect')?.addEventListener('change', async e => {
    const libPath = e.target.value;
    if (!libPath) return;
    showToast('🦅 Đang chuyển thư viện Eagle...');
    try {
      await api('eagle-select', { library_path: libPath });
      showToast('✅ Đã chuyển thư viện Eagle thành công!');
      await refresh();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // Open Eagle folder
  $('btnOpenEagleDirect')?.addEventListener('click', async () => {
    try {
      const res = await api('open-eagle', { library_path: currentEaglePath });
      showToast('✅ ' + (res.message || 'Đã mở Eagle DAM!'));
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // Refresh Eagle stats
  $('btnRefreshEagle')?.addEventListener('click', async () => {
    showToast('🔄 Đang làm mới số liệu Eagle...');
    try {
      await api('eagle-refresh');
      await refresh();
      showToast('✅ Đã cập nhật số liệu Eagle DAM!');
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // Refresh All
  $('btnRefreshAll')?.addEventListener('click', async () => {
    showToast('↻ Đang làm mới toàn bộ số liệu...');
    await api('eagle-refresh').catch(() => {});
    await refresh();
    showToast('✅ Đã làm mới toàn bộ số liệu!');
  });

  // System Update Tool (git pull)
  $('btnSystemUpdate')?.addEventListener('click', async () => {
    const btn = $('btnSystemUpdate');
    if (btn) btn.disabled = true;
    showToast('🔄 Đang tải phiên bản mới nhất từ GitHub (git pull)...');
    try {
      const res = await api('system-update');
      showToast(`✅ ${res.message} (${res.detail || 'Up to date'})`);
      await refresh();
    } catch (err) {
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
    showToast('🔄 Đang quét lại toàn bộ Album từ Google Photos...');
    try {
      const res = await api('photos-scan-albums', { profile_id: currentProfile });
      showToast(`✅ Đã quét xong ${res?.albums?.total_albums || 0} album!`);
      await refresh();
      renderAlbumsList();
    } catch (err) {
      showToast(err.message, true);
    }
  });

  // MCP modal triggers
  $('btnOpenMcpHub')?.addEventListener('click', openMcpModal);
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

  // Auto-refresh every 10 seconds
  setInterval(refresh, 10000);
});
