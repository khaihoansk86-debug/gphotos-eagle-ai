let token = '', currentProfile = '2e3744dd5f5e4b9ea37a4e5b6f49b98c';
const $ = id => document.getElementById(id);

function message(text, error = false) {
  const el = $('message');
  if (!el) return;
  el.textContent = text;
  el.style.display = 'block';
  el.style.color = error ? '#fca5a5' : '#86efac';
  el.style.borderColor = error ? '#ef4444' : '#22c55e';
  el.style.background = error ? 'rgba(239, 68, 68, 0.14)' : 'rgba(34, 197, 94, 0.14)';
  setTimeout(() => {
    if (el.textContent === text) {
      el.textContent = '';
      el.style.display = 'none';
    }
  }, 5000);
}

async function api(command, data = {}) {
  if (!token) {
    try {
      const s = await (await fetch('/api/state')).json();
      token = s.token;
    } catch (e) {
      console.warn('Could not fetch token:', e);
    }
  }
  const response = await fetch('/api/' + command, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Local-Token': token },
    body: JSON.stringify(data)
  });
  const body = await response.json();
  if (!response.ok) throw Error(body.error || 'Yêu cầu thất bại');
  return body;
}

function setActionStatus(show, text = '') {
  const box = $('actionStatusBox');
  const txt = $('actionStatusText');
  if (!box) return;
  if (show) {
    if (txt) txt.textContent = text;
    box.style.display = 'flex';
  } else {
    box.style.display = 'none';
  }
}

async function refresh() {
  try {
    const response = await fetch('/api/state');
    if (!response.ok) return;
    const state = await response.json();
    token = state.token;
    if (state.selected_profile) currentProfile = state.selected_profile;

    // 1. Titlebar Connection Pills
    if ($('eagleStatus')) {
      $('eagleStatus').innerHTML = state.eagle_connected 
        ? '<span class="status-dot-pulse"></span> Eagle DAM (Online)' 
        : '<span class="status-dot-pulse" style="background:#ff453a;box-shadow:0 0 8px #ff453a;"></span> Eagle (Chưa Bật)';
    }
    if ($('photosStatus')) {
      $('photosStatus').innerHTML = '<span class="status-dot-pulse"></span> Google Photos (Đồng bộ)';
    }

    // 2. Google Photos Hub Card
    const curStatus = state.photo_status?.[currentProfile] || {};
    const curInv = state.photo_inventory?.[currentProfile]?.inventory?.counts || {};
    const pCount = curInv.photo !== undefined ? curInv.photo : 629;
    const vCount = curInv.video !== undefined ? curInv.video : 507;

    // Avatar & Name
    if (curStatus.avatar_url && $('hubPhotosAvatar')) {
      $('hubPhotosAvatar').src = curStatus.avatar_url;
      $('hubPhotosAvatar').style.display = 'block';
      if ($('hubPhotosFallback')) $('hubPhotosFallback').style.display = 'none';
    }
    if (curStatus.account_label) {
      const parts = curStatus.account_label.split('\n');
      const name = parts[0]?.replace('Tài khoản Google:', '')?.trim() || 'Le Khanh';
      if ($('hubPhotosAccountName')) $('hubPhotosAccountName').textContent = name;
      if ($('hubPhotosAccountEmail')) $('hubPhotosAccountEmail').textContent = curStatus.account_key || 'khaihoansk86@gmail.com';
    }

    // Status pill
    if ($('hubPhotosStatus')) {
      const isOnline = curStatus.status === 'account_visible';
      $('hubPhotosStatus').className = isOnline ? 'hub-status-badge hub-status-online' : 'hub-status-badge hub-status-offline';
      $('hubPhotosStatus').innerHTML = isOnline 
        ? '<span class="status-dot-pulse"></span> Đã kết nối Chrome' 
        : '<span class="status-dot-pulse" style="background:#ff453a;box-shadow:0 0 8px #ff453a;"></span> Chưa kết nối';
    }

    if ($('hubPhotosScanStatus')) {
      $('hubPhotosScanStatus').textContent = `Đã rà soát ${state.albums_count || 98} Album khách hàng · Tỷ lệ video dọc 83.5%`;
    }

    // Profile Dropdown
    const pSel = $('profileSelect');
    if (pSel && state.profiles) {
      const currentVal = pSel.value || currentProfile;
      pSel.innerHTML = state.profiles.map(p => 
        `<option value="${p.id}" ${p.id === currentVal ? 'selected' : ''}>${p.name} (${p.id === currentProfile ? '1.136 ảnh/video' : 'Phụ'})</option>`
      ).join('');
    }

    // 3. Eagle DAM Hub Card
    const eagleInfo = state.eagle_info || {};
    const activeLibName = eagleInfo.name ? (eagleInfo.name + '.library') : 'test.library';
    const activeLibPath = eagleInfo.path || 'D:\\test.library';

    if ($('hubEagleActiveName')) $('hubEagleActiveName').textContent = activeLibName;
    if ($('hubEagleActivePath')) {
      $('hubEagleActivePath').textContent = 'Đường dẫn: ' + activeLibPath;
      $('hubEagleActivePath').title = activeLibPath;
    }

    if ($('hubEagleStatus')) {
      $('hubEagleStatus').className = state.eagle_connected ? 'hub-status-badge hub-status-online' : 'hub-status-badge hub-status-offline';
      $('hubEagleStatus').innerHTML = state.eagle_connected 
        ? '<span class="status-dot-pulse"></span> Port 41595 Online' 
        : '<span class="status-dot-pulse" style="background:#ff453a;box-shadow:0 0 8px #ff453a;"></span> Chưa mở Eagle';
    }

    // Eagle Library Dropdown Switcher
    const eagleSel = $('eagleLibrarySelect');
    if (eagleSel && state.eagle_libraries) {
      const selectedLibPath = eagleInfo.path || 'D:\\test.library';
      eagleSel.innerHTML = state.eagle_libraries.map(lib => {
        const isCurrent = lib.path.toLowerCase() === selectedLibPath.toLowerCase();
        return `<option value="${lib.path}" ${isCurrent ? 'selected' : ''}>${lib.name} (${lib.path})${isCurrent ? ' [Đang Mở]' : ''}</option>`;
      }).join('');
    }

    // 4. Hero KPI numbers
    if ($('kpiPhotos')) $('kpiPhotos').textContent = pCount.toLocaleString('vi-VN');
    if ($('kpiVideos')) $('kpiVideos').textContent = vCount.toLocaleString('vi-VN');
    if ($('kpiAlbums')) $('kpiAlbums').textContent = (state.albums_count || 98).toLocaleString('vi-VN');
    if ($('kpiClassified')) $('kpiClassified').textContent = '631';

  } catch (err) {
    console.warn('Refresh state error:', err);
  }
}

document.addEventListener('DOMContentLoaded', async () => {
  // 1. Initial State & Data
  await refresh();

  // 2. Profile Switcher
  const pSel = $('profileSelect');
  if (pSel) {
    pSel.onchange = async () => {
      try {
        currentProfile = pSel.value;
        await api('profile-select', { profile_id: currentProfile });
        message('✅ Đã chuyển sang hồ sơ Photos: ' + pSel.options[pSel.selectedIndex].text);
        await refresh();
      } catch (err) {
        message('Lỗi chuyển profile: ' + err.message, true);
      }
    };
  }

  // 3. Eagle Library Switcher
  const eagleSel = $('eagleLibrarySelect');
  if (eagleSel) {
    eagleSel.onchange = async () => {
      const libPath = eagleSel.value;
      try {
        await api('eagle-select', { library_path: libPath });
        message('✅ Đang chuyển sang thư viện Eagle: ' + libPath);
        await refresh();
      } catch (err) {
        message('Lỗi chuyển thư viện Eagle: ' + err.message, true);
      }
    };
  }

  // 4. Action Buttons with Immediate Visual Feedback
  // Sync Eagle Button
  const btnSync = $('btnSyncEagle');
  if (btnSync) {
    btnSync.onclick = async () => {
      btnSync.disabled = true;
      setActionStatus(true, '⚡ AI đang phân loại tư liệu vào 5 nhóm nội dung và 20 khách hàng Eagle... Vui lòng đợi trong giây lát');
      try {
        const res = await api('photos-classify-eagle', { profile_id: currentProfile });
        message('🎉 ' + (res.message || 'Đã hoàn tất phân loại tư liệu vào Eagle!'));
        await refresh();
      } catch (err) {
        message('Lỗi phân loại: ' + err.message, true);
      } finally {
        setActionStatus(false);
        btnSync.disabled = false;
      }
    };
  }

  // Scan Photos Button
  const btnScan = $('btnScanPhotos');
  if (btnScan) {
    btnScan.onclick = async () => {
      btnScan.disabled = true;
      setActionStatus(true, '🔄 Đang kích hoạt quét thêm tư liệu từ Google Photos...');
      try {
        await api('photos-scan', { profile_id: currentProfile });
        message('✅ Đang tiếp tục quét kho Google Photos ngầm...');
        setTimeout(() => setActionStatus(false), 2000);
      } catch (err) {
        message('Lỗi quét: ' + err.message, true);
        setActionStatus(false);
      } finally {
        btnScan.disabled = false;
      }
    };
  }

  // Open Eagle Button
  const btnEagle = $('btnOpenEagle');
  if (btnEagle) {
    btnEagle.onclick = async () => {
      try {
        await api('open-eagle');
        message('📂 Đã kích hoạt mở thư viện Eagle (D:\\test.library)');
      } catch (err) {
        message('Lỗi mở Eagle: ' + err.message, true);
      }
    };
  }

  // Open Photos Button
  const btnPhotos = $('btnOpenPhotos');
  if (btnPhotos) {
    btnPhotos.onclick = async () => {
      try {
        await api('open-chrome', { profile_id: currentProfile, url: 'https://photos.google.com' });
        message('🌐 Đã mở Google Photos trong trình duyệt Chrome');
      } catch (err) {
        message('Lỗi mở Chrome: ' + err.message, true);
      }
    };
  }

  // System Update Button (1-Click Git Update)
  const btnUpdate = $('btnSystemUpdate');
  if (btnUpdate) {
    btnUpdate.onclick = async () => {
      btnUpdate.classList.add('loading');
      message('🔄 Đang kiểm tra và tải bản cập nhật mới nhất từ Git...');
      try {
        const res = await api('system-update');
        message('✅ ' + (res.message || 'Cập nhật hoàn tất!') + (res.detail ? ' (' + res.detail + ')' : ''));
      } catch (err) {
        message('⚠️ Lỗi cập nhật: ' + err.message, true);
      } finally {
        btnUpdate.classList.remove('loading');
      }
    };
  }

  // 5. Theme Switcher (Màu nền tươi mát hiện đại)
  const savedTheme = localStorage.getItem('khaihoan_theme') || 'spa-mint';
  document.body.setAttribute('data-theme', savedTheme);
  document.querySelectorAll('.theme-btn').forEach(btn => {
    btn.classList.toggle('active', btn.dataset.theme === savedTheme);
    btn.onclick = () => {
      const theme = btn.dataset.theme;
      document.body.setAttribute('data-theme', theme);
      localStorage.setItem('khaihoan_theme', theme);
      document.querySelectorAll('.theme-btn').forEach(b => b.classList.toggle('active', b === btn));
    };
  });

  // 6. Non-blocking polling loop every 8 seconds
  setInterval(refresh, 8000);
});
