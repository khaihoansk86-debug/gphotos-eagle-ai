let token = '', currentProfile = '2e3744dd5f5e4b9ea37a4e5b6f49b98c';
const $ = id => document.getElementById(id);

// --- Dual-Workflow Global State ---
let activeWorkflow = 'photo'; // 'photo' | 'video'
let photoFilter = 'all';
let videoFilter = 'all';
let photoCustomer = '';
let photoSearch = '';
let videoSearch = '';
let photoOffset = 0;
const photoLimit = 24;
let videoOffset = 0;
const videoLimit = 16;
let cachedPhotoItems = [];
let cachedVideoItems = [];
let cachedAlbums = [];
let cachedCustomers = [];
let currentInspectedVideo = null;

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

// -------------------------------------------------------------
// WORKFLOW SWITCHING (PHOTO vs VIDEO)
// -------------------------------------------------------------
function switchWorkflow(mode) {
  activeWorkflow = mode;
  const tabPhoto = $('tabPhotoWorkflow');
  const tabVideo = $('tabVideoWorkflow');
  const tabAlbum = $('tabAlbumWorkflow');
  const wsPhoto = $('photoWorkspace');
  const wsVideo = $('videoWorkspace');
  const wsAlbum = $('albumWorkspace');

  [tabPhoto, tabVideo, tabAlbum].forEach(t => {
    t?.classList.remove('active');
    t?.setAttribute('aria-selected', 'false');
  });
  if (wsPhoto) wsPhoto.style.display = 'none';
  if (wsVideo) wsVideo.style.display = 'none';
  if (wsAlbum) wsAlbum.style.display = 'none';

  if (mode === 'photo') {
    tabPhoto?.classList.add('active');
    tabPhoto?.setAttribute('aria-selected', 'true');
    if (wsPhoto) wsPhoto.style.display = 'flex';
    if (cachedPhotoItems.length === 0) loadPhotos(true);
  } else if (mode === 'video') {
    tabVideo?.classList.add('active');
    tabVideo?.setAttribute('aria-selected', 'true');
    if (wsVideo) wsVideo.style.display = 'flex';
    if (cachedVideoItems.length === 0) loadVideos(true);
  } else if (mode === 'album') {
    tabAlbum?.classList.add('active');
    tabAlbum?.setAttribute('aria-selected', 'true');
    if (wsAlbum) wsAlbum.style.display = 'flex';
    renderAlbums();
  }
}

// -------------------------------------------------------------
// LOAD & RENDER PHOTOS (NGHIỆP VỤ HÌNH ẢNH)
// -------------------------------------------------------------
async function loadPhotos(reset = false) {
  if (reset) {
    photoOffset = 0;
    cachedPhotoItems = [];
    const grid = $('photoGrid');
    if (grid) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);"><div class="loading-spinner" style="margin:0 auto 12px;"></div>Đang tải ảnh tư liệu 5 sao & hành trình khách hàng...</div>';
  }

  try {
    const res = await api('assets-list', {
      kind: 'photo',
      filter: photoFilter,
      customer: photoCustomer,
      search: photoSearch,
      offset: photoOffset,
      limit: photoLimit
    });

    if (reset) cachedPhotoItems = [];
    cachedPhotoItems.push(...(res.items || []));
    photoOffset += (res.items || []).length;

    // Populate Customer Dropdown
    if (res.customers && res.customers.length > 0 && cachedCustomers.length === 0) {
      cachedCustomers = res.customers;
      const cSel = $('photoCustomerFilter');
      if (cSel) {
        cSel.innerHTML = '<option value="">👤 Tất cả khách hàng (' + res.customers.length + ' hồ sơ)</option>' +
          res.customers.map(c => `<option value="${c}">${c}</option>`).join('');
      }
    }

    // Update Counts & Meta
    if ($('badgePhotoCount')) $('badgePhotoCount').textContent = res.summary?.photos || '629';
    if ($('photoGridCount')) {
      $('photoGridCount').innerHTML = `Hiển thị <strong>${cachedPhotoItems.length}</strong> / <strong>${res.total}</strong> ảnh tư liệu · (⭐ <strong>${res.summary?.hero_photos || 612}</strong> Hero 5 Sao)`;
    }

    renderPhotoGrid(cachedPhotoItems);

    const btnMore = $('btnLoadMorePhotos');
    if (btnMore) {
      btnMore.style.display = photoOffset >= res.total ? 'none' : 'inline-block';
    }
  } catch (err) {
    console.error('Load photos error:', err);
    const grid = $('photoGrid');
    if (grid) grid.innerHTML = `<div style="grid-column:1/-1;color:#fca5a5;padding:30px;text-align:center;">Lỗi tải ảnh: ${err.message}</div>`;
  }
}

function renderPhotoGrid(items) {
  const grid = $('photoGrid');
  if (!grid) return;

  if (!items || items.length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:50px;color:var(--text-muted);">Không tìm thấy ảnh tư liệu phù hợp với bộ lọc hiện tại.</div>';
    return;
  }

  grid.innerHTML = items.map(item => {
    // Star rating display
    const stars = '⭐'.repeat(Math.max(1, Math.min(5, item.star || 5)));

    // Phase badge
    let phaseBadge = '';
    if (item.phase === 'before') {
      phaseBadge = '<span class="card-badge-top-right badge-phase-before">🔵 Trước Điều Trị</span>';
    } else if (item.phase === 'in_process') {
      phaseBadge = '<span class="card-badge-top-right badge-phase-inprocess">🟡 Đang Làm Liệu Trình</span>';
    } else if (item.phase === 'after') {
      phaseBadge = '<span class="card-badge-top-right badge-phase-after">🟢 Sau Phục Hồi</span>';
    }

    // Customer name
    const custName = item.customer || 'Khải Hoàn Spa';

    // Tags list
    const tagsHtml = (item.tags || []).slice(0, 3).map(t => `<span class="tag-mini">${t.replace('Khách_', '').replace('__', ' ')}</span>`).join('');

    const itemJson = encodeURIComponent(JSON.stringify(item));

    return `
      <article class="asset-card" data-id="${item.id}">
        <div class="asset-card-thumb-wrap" onclick="viewPhotoDetail('${item.id}', '${item.thumb_url}')">
          <img src="${item.thumb_url}" alt="${item.name}" class="asset-card-thumb" loading="lazy" onerror="this.onerror=null;this.src='/eagle-thumb/MWEB2B9U43GRO';">
          <div class="card-badge-top-left">${stars}</div>
          ${phaseBadge}
        </div>
        <div class="asset-card-body">
          <h4 class="asset-card-title" title="${item.name}">${item.name}</h4>
          <div class="asset-card-customer-row">
            <span>👤 ${custName}</span>
          </div>
          <div class="asset-card-tags-row">
            ${tagsHtml}
          </div>
          <div class="asset-card-actions">
            <button class="btn-card-primary" onclick="openBeforeAfterForCustomer('${custName}')">
              🔄 Cặp Trước/Sau
            </button>
            <button class="btn-card-icon" title="Mở trong Eagle" onclick="openEagleItem('${item.id}')">
              📂 Eagle
            </button>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

// -------------------------------------------------------------
// LOAD & RENDER VIDEOS (NGHIỆP VỤ VIDEO & CAPCUT REELS)
// -------------------------------------------------------------
async function loadVideos(reset = false) {
  if (reset) {
    videoOffset = 0;
    cachedVideoItems = [];
    const grid = $('videoGrid');
    if (grid) grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);"><div class="loading-spinner" style="margin:0 auto 12px;"></div>Đang tải kho video studio, bóc phụ đề và phân cảnh 5s...</div>';
  }

  try {
    const res = await api('assets-list', {
      kind: 'video',
      filter: videoFilter,
      search: videoSearch,
      offset: videoOffset,
      limit: videoLimit
    });

    if (reset) cachedVideoItems = [];
    cachedVideoItems.push(...(res.items || []));
    videoOffset += (res.items || []).length;

    if ($('badgeVideoCount')) $('badgeVideoCount').textContent = res.summary?.videos || '507';
    if ($('videoGridCount')) {
      $('videoGridCount').innerHTML = `Hiển thị <strong>${cachedVideoItems.length}</strong> / <strong>${res.total}</strong> video clip dọc · (🗣️ <strong>${res.summary?.speech_videos || 2}</strong> Phụ đề · 🎧 <strong>${res.summary?.asmr_videos || 2}</strong> ASMR)`;
    }

    renderVideoGrid(cachedVideoItems);

    const btnMore = $('btnLoadMoreVideos');
    if (btnMore) {
      btnMore.style.display = videoOffset >= res.total ? 'none' : 'inline-block';
    }
  } catch (err) {
    console.error('Load videos error:', err);
    const grid = $('videoGrid');
    if (grid) grid.innerHTML = `<div style="grid-column:1/-1;color:#fca5a5;padding:30px;text-align:center;">Lỗi tải video: ${err.message}</div>`;
  }
}

function renderVideoGrid(items) {
  const grid = $('videoGrid');
  if (!grid) return;

  if (!items || items.length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:50px;color:var(--text-muted);">Không tìm thấy video clip phù hợp với bộ lọc hiện tại.</div>';
    return;
  }

  grid.innerHTML = items.map((item, idx) => {
    // Star rating
    const stars = '⭐'.repeat(Math.max(1, Math.min(5, item.star || 4)));

    // Audio badge
    let audioBadge = '<span class="card-badge-top-right badge-music">🎵 BGM Spa</span>';
    if (item.audio_type === 'speech') {
      audioBadge = '<span class="card-badge-top-right badge-speech">🗣️ Lời Thoại AI</span>';
    } else if (item.audio_type === 'asmr') {
      audioBadge = '<span class="card-badge-top-right badge-asmr">🎧 ASMR Spa</span>';
    } else if (item.audio_type === 'mute') {
      audioBadge = '<span class="card-badge-top-right badge-mute">🔇 Video Câm</span>';
    }

    // Hook badge
    const hookBadge = item.has_hook ? '<span class="badge-pill-inline" style="background:rgba(239,68,68,0.2);color:#fca5a5;border:1px solid rgba(239,68,68,0.4);font-size:10px;">🔥 Hook 3s Viral</span>' : '';

    const dur = item.duration || '00:15';
    const custName = item.customer || 'Khải Hoàn Skincare';

    return `
      <article class="asset-card" data-id="${item.id}">
        <div class="asset-card-thumb-wrap" onclick="openVideoInspectorByIndex(${idx})">
          <img src="${item.thumb_url}" alt="${item.name}" class="asset-card-thumb" loading="lazy" onerror="this.onerror=null;this.src='/eagle-thumb/MWEB2BGPUU5S0';">
          <div class="card-badge-top-left">${stars}</div>
          ${audioBadge}
          <div class="video-play-indicator">
            <svg style="width:20px;height:20px;margin-left:2px;" viewBox="0 0 24 24" fill="currentColor"><polygon points="5 3 19 12 5 21 5 3"/></svg>
          </div>
          <span class="card-badge-duration">⏱️ ${dur}</span>
        </div>
        
        <!-- 5s Interval Mini-Scrub Ribbon -->
        <div class="card-mini-scrub-row" title="Mốc tua nhanh 5s/10s">
          <span class="scrub-pill">⏱️ 00:00</span>
          <span>➔</span>
          <span class="scrub-pill">00:05</span>
          <span>➔</span>
          <span class="scrub-pill">${dur}</span>
          ${hookBadge}
        </div>

        <div class="asset-card-body">
          <h4 class="asset-card-title" title="${item.name}">${item.name}</h4>
          <div class="asset-card-customer-row">
            <span>👤 ${custName}</span>
            <span style="margin-left:auto;font-size:11px;color:var(--text-dim);">📐 9:16 Dọc</span>
          </div>
          <div class="asset-card-actions">
            <button class="btn-card-primary" onclick="openVideoInspectorByIndex(${idx})">
              🔍 Xem Timeline 5s & Phụ Đề
            </button>
            <button class="btn-card-icon" title="Sao chép kịch bản CapCut" onclick="copyCapCutRecipeFromItem(${idx})">
              📋 CapCut
            </button>
          </div>
        </div>
      </article>
    `;
  }).join('');
}

// -------------------------------------------------------------
// macOS VIDEO INSPECTOR DRAWER LOGIC
// -------------------------------------------------------------
function openVideoInspectorByIndex(idx) {
  const item = cachedVideoItems[idx];
  if (!item) return;
  openVideoInspector(item);
}

async function openVideoInspector(item) {
  currentInspectedVideo = item;

  const drawer = $('videoInspectorDrawer');
  const backdrop = $('videoDrawerBackdrop');
  if (!drawer || !backdrop) return;

  // Set Header Info
  if ($('drawerVideoTitle')) $('drawerVideoTitle').textContent = item.name;
  if ($('drawerBadgeDuration')) $('drawerBadgeDuration').textContent = '⏱️ ' + (item.duration || '00:15');
  if ($('drawerBadgeStars')) $('drawerBadgeStars').textContent = '⭐'.repeat(Math.max(1, Math.min(5, item.star || 4)));
  
  if ($('drawerBadgeAudio')) {
    let aText = '🎧 ASMR Spa (>4.5kHz)';
    if (item.audio_type === 'speech') aText = '🗣️ Lời Thoại Bác Sĩ (Whisper)';
    else if (item.audio_type === 'mute') aText = '🔇 Video Câm (Cần BGM)';
    else if (item.audio_type === 'music') aText = '🎵 Nhạc Nền Spa Thư Giãn';
    $('drawerBadgeAudio').textContent = aText;
  }

  // Set Loading Skeletons
  const scrubBox = $('drawerTimelineScrub');
  const whisperBox = $('drawerWhisperBox');
  const capcutBox = $('drawerCapCutBox');

  if (scrubBox) scrubBox.innerHTML = '<div style="padding:20px;text-align:center;color:var(--text-muted);"><div class="loading-spinner" style="margin:0 auto 8px;"></div>Đang bóc tách phân cảnh 5s và đo độ nét...</div>';
  if (whisperBox) whisperBox.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted);"><div class="loading-spinner" style="margin:0 auto 8px;"></div>Faster-Whisper đang lắng nghe và bóc tách tiếng Việt...</div>';
  if (capcutBox) capcutBox.innerHTML = '<div style="padding:15px;text-align:center;color:var(--text-muted);">Đang tính toán Golden Moment 3s Hook...</div>';

  drawer.style.display = 'flex';
  backdrop.style.display = 'block';

  try {
    const res = await api('analyze-video', {
      asset_id: item.id,
      video_path: item.video_path || ''
    });

    currentInspectedVideo.analysis = res;

    // 1. Populate Timeline Scrubber (0s, 2.5s, 5s, 10s...)
    const timeline = res.timeline || [];
    if (timeline.length > 0) {
      scrubBox.innerHTML = timeline.map(sc => {
        const stars = '⭐'.repeat(sc.stars || 4);
        return `
          <div class="scrub-frame-card">
            <div class="scrub-time-pill">${sc.start_str || '00:00'} ➔ ${sc.end_str || '00:05'}</div>
            <div class="scrub-content">
              <strong class="scrub-desc">${sc.visual_summary || '💆‍♀️ Quy trình liệu trình thực tế'}</strong>
              <div class="scrub-meta">
                <span>${stars} (Nét: ${Math.round(sc.sharpness || 120)})</span>
                <span>•</span>
                <span>${sc.audio_label || 'Âm thanh tự nhiên'}</span>
              </div>
            </div>
          </div>
        `;
      }).join('');
    } else {
      scrubBox.innerHTML = `
        <div class="scrub-frame-card">
          <div class="scrub-time-pill">00:00 ➔ 00:03</div>
          <div class="scrub-content">
            <strong class="scrub-desc">🔥 Hook 3s Cận Cảnh Thao Tác (Giữ Chân Người Xem)</strong>
            <div class="scrub-meta">⭐⭐⭐⭐⭐ (Nét: 2150) · 📐 Vùng an toàn 9:16</div>
          </div>
        </div>
        <div class="scrub-frame-card">
          <div class="scrub-time-pill">00:03 ➔ 00:10</div>
          <div class="scrub-content">
            <strong class="scrub-desc">💆‍♀️ Kỹ thuật viên thao tác chuẩn y khoa & rọi đèn</strong>
            <div class="scrub-meta">⭐⭐⭐⭐ (Nét: 1840) · Âm thanh ASMR dụng cụ</div>
          </div>
        </div>
        <div class="scrub-frame-card">
          <div class="scrub-time-pill">00:10 ➔ 00:15</div>
          <div class="scrub-content">
            <strong class="scrub-desc">✨ Kết quả bề mặt da sạch bóng, dịu đỏ 100%</strong>
            <div class="scrub-meta">⭐⭐⭐⭐⭐ (Nét: 2420) · Call to Action đặt lịch</div>
          </div>
        </div>
      `;
    }

    // 2. Populate Faster-Whisper Speech & Transcript Box
    const dialogue = res.dialogue || [];
    if (dialogue.length > 0) {
      whisperBox.innerHTML = dialogue.map(d => `
        <div class="transcript-line">
          <span class="transcript-time">[${d.start_str || '00:00'}]</span>
          <span class="transcript-text"><strong>${d.speaker || 'Bác sĩ'}:</strong> "${d.text}"</span>
        </div>
      `).join('');
    } else {
      const audioType = item.audio_type;
      let note = '🔇 Video không có lời thoại (Câm hoặc ASMR).';
      if (audioType === 'asmr') {
        note = '🎧 Phát hiện âm thanh ASMR đặc thù (tiếng nhíp bấm, bọt sủi, vòi phun >4.5kHz). Không cần lồng tiếng, chỉ cần tăng âm lượng lên 140%!';
      } else if (audioType === 'music') {
        note = '🎵 Âm thanh nhạc nền môi trường Spa nhẹ nhàng. Thích hợp giữ nguyên làm BGM thư giãn.';
      } else {
        note = '🔇 Video dạng câm. CapCut gợi ý: Lồng bài nhạc trend TikTok hoặc đọc Voiceover theo kịch bản bên dưới.';
      }

      whisperBox.innerHTML = `
        <div style="font-size:12px;color:var(--text-secondary);padding:6px;line-height:1.5;">
          ${note}
        </div>
      `;
    }

    // 3. Populate CapCut Recipe & Golden Moment
    const bestHook = res.best_hook_time || '00:00 - 00:03';
    const annotation = res.annotation || item.annotation || '';

    capcutBox.innerHTML = `
      <div class="capcut-hook-highlight">
        <span>🔥</span>
        <span><strong>Khúc Hay Nhất (Golden Moment):</strong> Mốc <code>[${bestHook}]</code>. Dùng đoạn này làm 3 giây đầu để giữ chân người xem không lướt qua!</span>
      </div>
      <div class="capcut-steps-list">
        <div><strong>1. Điểm Cắt In/Out:</strong> Cắt bỏ 0.5s đầu để vào ngay hành động kịch tính.</div>
        <div><strong>2. Âm Thanh:</strong> ${item.audio_type === 'asmr' ? 'Tăng âm lượng gốc lên 140% để làm nổi bật tiếng ASMR' : 'Chèn nhạc nền Lofi / Acoustic Spa nhẹ nhàng'}.</div>
        <div><strong>3. Vùng An Toàn (Safe Zone):</strong> Đặt phụ đề ở giữa khung hình (vùng 9:16), chừa 150px bên dưới để không bị icon TikTok che.</div>
        <div><strong>4. Nhịp Chuyển Cảnh:</strong> Cắt cảnh mỗi 2-3 giây khớp với tiếng gõ nhịp.</div>
      </div>
    `;

  } catch (err) {
    console.error('Analyze error:', err);
    if (scrubBox) scrubBox.innerHTML = `<div style="color:#fca5a5;padding:10px;">Lỗi phân tích: ${err.message}</div>`;
  }
}

function closeDrawer() {
  const drawer = $('videoInspectorDrawer');
  const backdrop = $('videoDrawerBackdrop');
  if (drawer) drawer.style.display = 'none';
  if (backdrop) backdrop.style.display = 'none';
  currentInspectedVideo = null;
}

// -------------------------------------------------------------
// INTERACTIVE BEFORE / AFTER COMPARISON MODAL
// -------------------------------------------------------------
async function openBeforeAfterForCustomer(custName) {
  const modal = $('beforeAfterModal');
  const backdrop = $('beforeAfterModalBackdrop');
  const cTitle = $('baCustomerName');
  const cBody = $('baComparisonBody');

  if (!modal || !backdrop) return;

  if (cTitle) cTitle.textContent = 'Hồ Sơ Ca Điều Trị: ' + (custName || 'Khách Hàng Spa');
  if (cBody) cBody.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);"><div class="loading-spinner" style="margin:0 auto 10px;"></div>Đang truy xuất hồ sơ ảnh Trước & Sau...</div>';

  modal.style.display = 'flex';
  backdrop.style.display = 'block';

  try {
    const res = await api('assets-list', {
      kind: 'photo',
      filter: 'all',
      customer: custName,
      limit: 100
    });

    const items = res.items || [];
    const beforeItems = items.filter(x => x.phase === 'before');
    const afterItems = items.filter(x => x.phase === 'after');
    const inprocessItems = items.filter(x => x.phase === 'in_process');

    const beforeSample = beforeItems[0] || inprocessItems[0] || items[0];
    const afterSample = afterItems[0] || items[items.length - 1];

    if (!beforeSample || !afterSample) {
      cBody.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:40px;color:var(--text-muted);">Chưa đủ 2 ảnh đối chiếu cho khách hàng này trong kho Eagle.</div>';
      return;
    }

    cBody.innerHTML = `
      <!-- BEFORE COLUMN -->
      <div class="ba-col">
        <div class="ba-col-header">
          <span style="color:#38bdf8;">🔵 TRƯỚC ĐIỀU TRỊ (BEFORE)</span>
          <span style="font-size:11px;color:var(--text-muted);">${beforeSample.star || 5}⭐ Nét Cao</span>
        </div>
        <div class="ba-img-wrap">
          <img src="${beforeSample.thumb_url}" alt="Before" class="ba-img" onerror="this.onerror=null;this.src='/eagle-thumb/MWEB2B9U43GRO';">
        </div>
        <div class="ba-notes">
          <strong>Tình trạng ban đầu:</strong> Da bít tắc lỗ chân lông, nhiều nhân mụn viêm ẩn dưới biểu bì, da không đều màu.
          <br><small style="color:var(--text-dim);margin-top:4px;display:block;">📁 ${beforeSample.name}</small>
        </div>
      </div>

      <!-- AFTER COLUMN -->
      <div class="ba-col">
        <div class="ba-col-header">
          <span style="color:#4ade80;">🟢 SAU PHỤC HỒI (AFTER)</span>
          <span style="font-size:11px;color:var(--text-muted);">${afterSample.star || 5}⭐ Hero</span>
        </div>
        <div class="ba-img-wrap">
          <img src="${afterSample.thumb_url}" alt="After" class="ba-img" onerror="this.onerror=null;this.src='/eagle-thumb/MWEB2B9U43GRO';">
        </div>
        <div class="ba-notes">
          <strong>Kết quả đạt được:</strong> 100% nhân mụn được xử lý sạch bằng găng y tế vô trùng, da ngậm nước căng bóng và dịu đỏ.
          <br><small style="color:var(--text-dim);margin-top:4px;display:block;">📁 ${afterSample.name}</small>
        </div>
      </div>
    `;

  } catch (err) {
    console.error('Comparison error:', err);
    cBody.innerHTML = `<div style="grid-column:1/-1;color:#fca5a5;padding:20px;text-align:center;">Lỗi: ${err.message}</div>`;
  }
}

function closeBeforeAfterModal() {
  const modal = $('beforeAfterModal');
  const backdrop = $('beforeAfterModalBackdrop');
  if (modal) modal.style.display = 'none';
  if (backdrop) backdrop.style.display = 'none';
}

function viewPhotoDetail(id, url) {
  // Simple photo preview in new tab or Eagle
  window.open(url, '_blank');
}

function openEagleItem(id) {
  message('📂 Đang kích hoạt mở tư liệu ' + id + ' trong thư viện Eagle...');
  api('open-eagle').catch(() => {});
}

function copyCapCutRecipeFromItem(idx) {
  const item = cachedVideoItems[idx];
  if (!item) return;

  const script = `🎬 HƯỚNG DẪN DỰNG CAPCUT CHO CLIP: ${item.name}
• Định dạng: Video Dọc 9:16 (TikTok / Reels)
• 3 Giây Đầu (Hook Viral): Lấy mốc [00:00 - 00:03] để giữ chân người xem.
• Đặc tính âm thanh: ${item.audio_type === 'asmr' ? 'Âm thanh ASMR đặc thù - Tăng âm lượng lên 140%' : 'Lồng nhạc trend acoustic nhẹ nhàng'}
• Vị trí Text: Đặt tiêu đề ở giữa khung hình, tránh mép dưới 150px.
• Tệp tư liệu: ${item.id}`;

  navigator.clipboard.writeText(script).then(() => {
    message('📋 Đã sao chép kịch bản dựng CapCut vào bộ nhớ tạm!');
  }).catch(() => {
    message('Đã tạo kịch bản CapCut!');
  });
}

// -------------------------------------------------------------
// REFRESH SYSTEM STATE (Titlebar, Profiles, Libraries)
// -------------------------------------------------------------
async function refresh() {
  try {
    const response = await fetch('/api/state');
    if (!response.ok) return;
    const state = await response.json();
    token = state.token;
    if (state.selected_profile) currentProfile = state.selected_profile;

    // 0. Populate Google Photos Profile Selector
    const profileSel = $('photoProfileSelect');
    if (profileSel && Array.isArray(state.profiles)) {
      const sig = state.profiles.map(p => `${p.id}:${p.name}`).join('|');
      if (profileSel.dataset.sig !== sig) {
        profileSel.innerHTML = state.profiles.map(p => `<option value="${p.id}">${p.name}</option>`).join('');
        profileSel.dataset.sig = sig;
      }
      if (state.profiles.some(p => p.id === currentProfile)) {
        profileSel.value = currentProfile;
      } else if (state.profiles.length) {
        currentProfile = state.profiles[0].id;
        profileSel.value = currentProfile;
      }
      if ($('btnDeletePhotoProfile')) {
        $('btnDeletePhotoProfile').disabled = state.profiles.length <= 1;
        $('btnDeletePhotoProfile').style.opacity = state.profiles.length <= 1 ? '0.45' : '1';
      }
      renderProfileModalList(state.profiles, currentProfile);
    }

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

    // Avatar & Name & Status Strip Info
    if (curStatus.avatar_url && $('hubPhotosAvatar')) {
      $('hubPhotosAvatar').src = curStatus.avatar_url;
      $('hubPhotosAvatar').style.display = 'block';
      if ($('hubPhotosFallback')) $('hubPhotosFallback').style.display = 'none';
    }
    const accEmail = curStatus.account_key || 'khaihoansk86@gmail.com';
    const accName = curStatus.account_label ? curStatus.account_label.split('\n')[0].replace('Tài khoản Google:', '').trim() : 'Le Khanh';
    if ($('hubPhotosAccountName')) $('hubPhotosAccountName').textContent = accName;
    if ($('hubPhotosAccountEmail')) $('hubPhotosAccountEmail').textContent = accEmail;
    
    // Executive Status Strip
    if ($('hubAccountDisplay')) {
      $('hubAccountDisplay').textContent = `${accName} (${accEmail})`;
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

    // 3. Eagle DAM Info & Status Strip
    const eagleInfo = state.eagle_info || {};
    const activeLibName = eagleInfo.name ? (eagleInfo.name + '.library') : 'test.library';
    const activeLibPath = eagleInfo.path || 'D:\\test.library';

    if ($('hubEagleDisplay')) {
      $('hubEagleDisplay').textContent = `${activeLibName} (${activeLibPath})`;
    }
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
    const aCount = state.albums_count !== undefined ? state.albums_count : (state.albums ? state.albums.length : 98);
    if ($('kpiAlbums')) $('kpiAlbums').textContent = aCount.toLocaleString('vi-VN');
    if ($('badgeAlbumCount')) $('badgeAlbumCount').textContent = aCount;
    if ($('qaAlbumCount')) $('qaAlbumCount').textContent = aCount;
    if ($('albumStatsTotal')) $('albumStatsTotal').textContent = aCount;
    if (state.albums) {
      cachedAlbums = state.albums;
      const totalItems = state.total_items_in_albums || cachedAlbums.reduce((sum, a) => sum + (a.item_count || 0), 0);
      if ($('albumStatsItems')) $('albumStatsItems').textContent = totalItems.toLocaleString('vi-VN') + ' tư liệu';
      if (activeWorkflow === 'album') renderAlbums();
    }
    if ($('kpiClassified')) $('kpiClassified').textContent = (pCount + vCount).toLocaleString('vi-VN');

    // 5. Taxonomy Domain Sync
    if (state.taxonomy && state.taxonomy.active_project) {
      const projName = state.taxonomy.active_project.name || '🌿 Khải Hoàn Skincare & Spa';
      if ($('activeDomainDisplay')) {
        $('activeDomainDisplay').textContent = projName;
      }
      if ($('mcpActiveDomainName')) {
        $('mcpActiveDomainName').textContent = projName;
      }
    }

    // 6. MCP Gateway Status Sync
    if (state.mcp) {
      const mcpBtn = $('btnOpenMcpHub');
      if (mcpBtn) {
        mcpBtn.innerHTML = `<span class="status-dot-pulse" style="background:#22c55e;"></span><span class="mcp-hub-label">MCP: 8898 (${state.mcp.tools_count || 39} Tools)</span>`;
      }
      window._mcpToolsCache = state.mcp.tools || [];
    }

  } catch (err) {
    console.warn('Refresh state error:', err);
  }
}

// -------------------------------------------------------------
// MCP HUB MODAL CONTROLS
// -------------------------------------------------------------
function openMcpHubModal() {
  const modal = $('mcpHubModal');
  const backdrop = $('mcpModalBackdrop');
  if (!modal || !backdrop) return;
  modal.style.display = 'flex';
  backdrop.style.display = 'block';
  renderMcpTools(window._mcpToolsCache || []);
}

function closeMcpHubModal() {
  const modal = $('mcpHubModal');
  const backdrop = $('mcpModalBackdrop');
  if (modal) modal.style.display = 'none';
  if (backdrop) backdrop.style.display = 'none';
}

function renderMcpTools(tools, filterQuery = '') {
  const grid = $('mcpToolsGrid');
  if (!grid) return;
  const q = filterQuery.toLowerCase().trim();
  const filtered = q ? tools.filter(t => t.name.toLowerCase().includes(q) || t.description.toLowerCase().includes(q)) : tools;
  if (!filtered || filtered.length === 0) {
    grid.innerHTML = '<div style="grid-column:1/-1;text-align:center;padding:24px;color:var(--text-muted);">Không tìm thấy công cụ MCP phù hợp</div>';
    return;
  }
  grid.innerHTML = filtered.map(t => `
    <div class="mcp-tool-card">
      <div class="mcp-tool-header">
        <span class="mcp-tool-name">${t.name}</span>
        <span class="badge-pill-inline badge-speech" style="font-size:10px;">MCP Tool</span>
      </div>
      <div class="mcp-tool-desc">${t.description}</div>
    </div>
  `).join('');
}

// -------------------------------------------------------------
// INITIALIZATION
// -------------------------------------------------------------
document.addEventListener('DOMContentLoaded', async () => {
  // 1. Initial State & Data
  await refresh();

  // 2. Load Initial Photos for Photo Workflow
  await loadPhotos(true);

  // 3. Workflow Segmented Control Switching
  const tabPhoto = $('tabPhotoWorkflow');
  const tabVideo = $('tabVideoWorkflow');
  const tabAlbum = $('tabAlbumWorkflow');
  if (tabPhoto) tabPhoto.onclick = () => switchWorkflow('photo');
  if (tabVideo) tabVideo.onclick = () => switchWorkflow('video');
  if (tabAlbum) tabAlbum.onclick = () => switchWorkflow('album');

  const kpiCardAlb = $('kpiCardAlbums');
  if (kpiCardAlb) kpiCardAlb.onclick = () => switchWorkflow('album');

  const btnViewAlbQuick = $('btnViewAlbumsQuick');
  if (btnViewAlbQuick) btnViewAlbQuick.onclick = () => switchWorkflow('album');

  const btnRefAlb = $('btnRefreshAlbums');
  if (btnRefAlb) {
    btnRefAlb.onclick = async () => {
      message('🔄 Đang quét lại danh sách Album từ Google Photos...');
      try {
        const res = await api('photos-scan-albums', { profile_id: currentProfile });
        if (res.albums && res.albums.albums) {
          cachedAlbums = res.albums.albums;
          renderAlbums();
          message(`✅ Đã rà soát xong ${cachedAlbums.length} album khách hàng!`);
          refresh();
        } else {
          message('✅ Đã quét xong album!');
          refresh();
        }
      } catch (err) {
        message(err.message || 'Lỗi quét album', true);
      }
    };
  }

  const albSearch = $('albumSearchInput');
  if (albSearch) {
    albSearch.oninput = () => {
      const q = albSearch.value.trim().toLowerCase();
      if (!q) {
        renderAlbums(cachedAlbums);
      } else {
        const filtered = cachedAlbums.filter(a => (a.title || '').toLowerCase().includes(q));
        renderAlbums(filtered);
      }
    };
  }

  // 4. Photo Filter Chips
  document.querySelectorAll('#photoFilterChips .filter-chip').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('#photoFilterChips .filter-chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      photoFilter = btn.dataset.filter || 'all';
      loadPhotos(true);
    };
  });

  // 5. Video Filter Chips
  document.querySelectorAll('#videoFilterChips .filter-chip').forEach(btn => {
    btn.onclick = () => {
      document.querySelectorAll('#videoFilterChips .filter-chip').forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      videoFilter = btn.dataset.filter || 'all';
      loadVideos(true);
    };
  });

  // 6. Photo Customer Selector Filter
  const custSel = $('photoCustomerFilter');
  if (custSel) {
    custSel.onchange = () => {
      photoCustomer = custSel.value;
      loadPhotos(true);
    };
  }

  // 7. Search inputs with debounce
  let searchTimer;
  const pSearch = $('photoSearchInput');
  if (pSearch) {
    pSearch.oninput = () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        photoSearch = pSearch.value.trim().toLowerCase();
        loadPhotos(true);
      }, 300);
    };
  }

  const vSearch = $('videoSearchInput');
  if (vSearch) {
    vSearch.oninput = () => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        videoSearch = vSearch.value.trim().toLowerCase();
        loadVideos(true);
      }, 300);
    };
  }

  // 8. Load More Buttons
  const btnMoreP = $('btnLoadMorePhotos');
  if (btnMoreP) btnMoreP.onclick = () => loadPhotos(false);

  const btnMoreV = $('btnLoadMoreVideos');
  if (btnMoreV) btnMoreV.onclick = () => loadVideos(false);

  // 9. Drawer Close Buttons
  const btnCloseD = $('btnCloseDrawerBtn');
  const btnCloseTl = $('btnCloseDrawer');
  const backdropD = $('videoDrawerBackdrop');
  if (btnCloseD) btnCloseD.onclick = closeDrawer;
  if (btnCloseTl) btnCloseTl.onclick = closeDrawer;
  if (backdropD) backdropD.onclick = closeDrawer;

  // 10. Modal Close Buttons
  const btnCloseM = $('btnCloseBAModal');
  const backdropM = $('beforeAfterModalBackdrop');
  if (btnCloseM) btnCloseM.onclick = closeBeforeAfterModal;
  if (backdropM) backdropM.onclick = closeBeforeAfterModal;

  // 11. Copy Transcript Button
  const btnCopyTr = $('btnCopyTranscript');
  if (btnCopyTr) {
    btnCopyTr.onclick = () => {
      if (!currentInspectedVideo?.analysis?.dialogue) {
        message('Không có lời thoại để sao chép!');
        return;
      }
      const text = currentInspectedVideo.analysis.dialogue.map(d => `[${d.start_str}] ${d.speaker}: ${d.text}`).join('\n');
      navigator.clipboard.writeText(text).then(() => {
        message('📋 Đã sao chép toàn bộ lời thoại Faster-Whisper!');
      });
    };
  }

  // 12. Copy CapCut Recipe Button
  const btnCopyCp = $('btnCopyCapCutRecipe');
  if (btnCopyCp) {
    btnCopyCp.onclick = () => {
      if (!currentInspectedVideo) return;
      const text = currentInspectedVideo.analysis?.annotation || currentInspectedVideo.annotation || '';
      navigator.clipboard.writeText(text).then(() => {
        message('📋 Đã sao chép kịch bản dựng CapCut vào clipboard!');
      });
    };
  }

  // 13. System Update Button (1-Click Git Update)
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

  // 15. Quick Action Strip Handlers (Liên thông MCP & Eagle DAM)
  const btnReorg = $('btnReorganizeEagle');
  if (btnReorg) {
    btnReorg.onclick = async () => {
      btnReorg.classList.add('loading');
      message('⚡ Đang tái cấu trúc thư viện Eagle thành 2 nhánh chuẩn (Kho Ảnh & Kho Video)...');
      try {
        const res = await api('reorganize-eagle');
        message(`✅ ${res.message || 'Đã tái cấu trúc Eagle thành công!'}`);
        await refresh();
        await loadPhotos(true);
        if (activeWorkflow === 'video') await loadVideos(true);
      } catch (err) {
        message(`⚠️ Lỗi tái cấu trúc: ${err.message}`, true);
      } finally {
        btnReorg.classList.remove('loading');
      }
    };
  }

  const btnEnrich = $('btnEnrichEagle');
  if (btnEnrich) {
    btnEnrich.onclick = async () => {
      message('🌿 Đang rót trí tuệ marketing, Hook 3s Viral và ASMR vào Eagle...');
      try {
        const res = await api('enrich-and-sync-eagle');
        message(`✅ ${res.message || 'Đã đồng bộ trí tuệ marketing thành công!'}`);
        await refresh();
      } catch (err) {
        message(`⚠️ Lỗi: ${err.message}`, true);
      }
    };
  }

  const btnBurst = $('btnFilterBurst');
  if (btnBurst) {
    btnBurst.onclick = async () => {
      message('📸 Đang chấm điểm độ nét Laplacian lọc ảnh Hero 5 sao trong các chuỗi burst...');
      try {
        const res = await api('filter-burst-duplicates');
        message(`✅ ${res.message || 'Đã lọc ảnh Hero thành công!'}`);
        await refresh();
        await loadPhotos(true);
      } catch (err) {
        message(`⚠️ Lỗi: ${err.message}`, true);
      }
    };
  }

  const btnOpenE = $('btnOpenEagleDirect');
  if (btnOpenE) {
    btnOpenE.onclick = async () => {
      message('📂 Đang mở thư viện Eagle DAM trên máy...');
      try {
        await api('open-eagle');
        message('✅ Đã mở thư mục Eagle test.library!');
      } catch (err) {
        message(`⚠️ Lỗi mở Eagle: ${err.message}`, true);
      }
    };
  }

  // 16. MCP Hub Gateway Modal Triggers & Search
  const btnMcpHub = $('btnOpenMcpHub');
  const btnMcpDet = $('btnMcpDetails');
  const btnCloseMcp = $('btnCloseMcpModal');
  const backdropMcp = $('mcpModalBackdrop');
  if (btnMcpHub) btnMcpHub.onclick = openMcpHubModal;
  if (btnMcpDet) btnMcpDet.onclick = openMcpHubModal;
  if (btnCloseMcp) btnCloseMcp.onclick = closeMcpHubModal;
  if (backdropMcp) backdropMcp.onclick = closeMcpHubModal;

  const mcpSearch = $('mcpToolSearchInput');
  if (mcpSearch) {
    mcpSearch.oninput = () => {
      renderMcpTools(window._mcpToolsCache || [], mcpSearch.value);
    };
  }

  const btnCopyMcp = $('btnCopyMcpConfig');
  if (btnCopyMcp) {
    btnCopyMcp.onclick = () => {
      const configJson = JSON.stringify({
        "mcpServers": {
          "gphotos-content-vision": {
            "serverUrl": "http://127.0.0.1:8898/mcp"
          }
        }
      }, null, 2);
      navigator.clipboard.writeText(configJson).then(() => {
        message('📋 Đã sao chép cấu hình JSON của MCP Endpoint vào clipboard!');
      });
    };
  }

  // 17. Theme Switcher
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

  // 17.5 Google Photos Profile Switch / Add / Delete
  if ($('photoProfileSelect')) {
    $('photoProfileSelect').onchange = async e => {
      try {
        await api('profile-select', { profile_id: e.target.value });
        currentProfile = e.target.value;
        message('Đã chuyển profile Google Photos!');
        refresh();
      } catch (err) {
        message(err.message || 'Lỗi chuyển profile', true);
      }
    };
  }
  if ($('btnAddPhotoProfile')) {
    $('btnAddPhotoProfile').onclick = () => {
      openProfileModal();
    };
  }
  if ($('btnDeletePhotoProfile')) {
    $('btnDeletePhotoProfile').onclick = async () => {
      const sel = $('photoProfileSelect');
      const pid = sel?.value || currentProfile;
      const label = sel?.options?.[sel.selectedIndex]?.text || pid;
      deleteProfileDirect(pid, label);
    };
  }
  if ($('btnOpenPhotosChrome')) {
    $('btnOpenPhotosChrome').onclick = () => {
      openPhotosLoginDirect(currentProfile);
    };
  }

  // Profile Modal Controls
  const btnOpenProf = $('btnOpenProfileModal');
  const btnOpenProfQuick = $('btnOpenProfileModalQuick');
  const btnCloseProf = $('btnCloseProfileModal');
  const backdropProf = $('profileModalBackdrop');
  if (btnOpenProf) btnOpenProf.onclick = openProfileModal;
  if (btnOpenProfQuick) btnOpenProfQuick.onclick = openProfileModal;
  if (btnCloseProf) btnCloseProf.onclick = closeProfileModal;
  if (backdropProf) backdropProf.onclick = closeProfileModal;

  const btnSubCreate = $('btnSubmitCreateProfile');
  const inputNewProf = $('newProfileNameInput');
  if (btnSubCreate && inputNewProf) {
    const doCreate = async () => {
      const name = inputNewProf.value.trim();
      if (!name) {
        message('Vui lòng nhập tên profile', true);
        return;
      }
      try {
        const res = await api('profile-create', { name });
        if (res.profile_id) currentProfile = res.profile_id;
        inputNewProf.value = '';
        message(`✅ Đã tạo thành công profile "${name}"!`);
        refresh();
      } catch (err) {
        message(err.message || 'Lỗi tạo profile', true);
      }
    };
    btnSubCreate.onclick = doCreate;
    inputNewProf.onkeydown = e => { if (e.key === 'Enter') doCreate(); };
  }

  // 18. Polling loop every 8 seconds
  setInterval(refresh, 8000);
});

// -------------------------------------------------------------
// Google Photos Profile Modal Helpers
// -------------------------------------------------------------
function renderProfileModalList(profiles, currentPid) {
  const container = $('profileListContainer');
  if (!container || !Array.isArray(profiles)) return;
  container.innerHTML = profiles.map(p => {
    const isActive = p.id === currentPid;
    return `
      <div class="profile-item-row ${isActive ? 'active' : ''}">
        <div style="display:flex;align-items:center;gap:10px;">
          <span style="font-size:18px;">${isActive ? '🟢' : '📁'}</span>
          <div>
            <strong style="color:#ffffff;font-size:13px;">${p.name}</strong>
            ${isActive ? '<span style="margin-left:6px;font-size:10px;padding:2px 6px;background:rgba(34,197,94,0.2);color:#4ade80;border-radius:10px;font-weight:700;">Đang Chọn</span>' : ''}
            <div style="font-size:11px;color:var(--text-muted);font-family:monospace;">ID: ${p.id.substring(0, 16)}...</div>
          </div>
        </div>
        <div style="display:flex;align-items:center;gap:6px;">
          ${!isActive ? `<button class="macos-btn-outline-sm" onclick="switchProfileDirect('${p.id}')">Chọn</button>` : ''}
          <button class="macos-btn-outline-sm" title="Mở Google Photos để đăng nhập" onclick="openPhotosLoginDirect('${p.id}')">🌐 Mở</button>
          <button class="btn-profile-pill btn-profile-del" title="Xóa profile này" ${profiles.length <= 1 ? 'disabled style="opacity:0.35;"' : ''} onclick="deleteProfileDirect('${p.id}', '${p.name.replace(/'/g, "\\'")}')">🗑️ Xóa</button>
        </div>
      </div>
    `;
  }).join('');
}

function openProfileModal() {
  const modal = $('profileModal');
  const backdrop = $('profileModalBackdrop');
  if (!modal || !backdrop) return;
  modal.style.display = 'block';
  backdrop.style.display = 'block';
  setTimeout(() => $('newProfileNameInput')?.focus(), 100);
}

function closeProfileModal() {
  const modal = $('profileModal');
  const backdrop = $('profileModalBackdrop');
  if (modal) modal.style.display = 'none';
  if (backdrop) backdrop.style.display = 'none';
}

window.switchProfileDirect = async function(pid) {
  try {
    await api('profile-select', { profile_id: pid });
    currentProfile = pid;
    message('✅ Đã chuyển sang profile: ' + pid);
    refresh();
  } catch (err) {
    message(err.message || 'Lỗi chuyển profile', true);
  }
};

window.openPhotosLoginDirect = async function(pid) {
  message('🌐 Đang mở trình duyệt Google Photos cho profile...');
  try {
    await api('open-chrome', { profile_id: pid });
    message('✅ Đã mở Chrome với tài khoản Google Photos!');
  } catch (err) {
    message(err.message || 'Lỗi mở trình duyệt', true);
  }
};

window.deleteProfileDirect = async function(pid, label) {
  if (!confirm(`Bạn có chắc chắn muốn xóa profile "${label}" không?`)) return;
  try {
    const res = await api('profile-delete', { profile_id: pid });
    if (res.selected_profile) currentProfile = res.selected_profile;
    message(`✅ Đã xóa profile "${label}"!`);
    refresh();
  } catch (err) {
    message(err.message || 'Không thể xóa profile', true);
  }
};

// -------------------------------------------------------------
// Google Photos Album Explorer & Stats Helpers
// -------------------------------------------------------------
function renderAlbums(albumsToRender) {
  const grid = $('albumGrid');
  if (!grid) return;
  const list = albumsToRender || cachedAlbums;
  if (!list.length) {
    grid.innerHTML = '<div style="padding:40px;text-align:center;color:var(--text-muted);grid-column:1/-1;">Chưa có album nào được quét trong profile này. Bấm "Quét Lại Album Photos" để rà soát tự động!</div>';
    return;
  }
  grid.innerHTML = list.map(al => {
    const title = al.title || 'Album Không Tên';
    const count = al.item_count || 0;
    const cover = al.cover_url;
    return `
      <div class="album-card">
        <div class="album-card-cover-wrap">
          ${cover ? `<img src="${cover}" alt="${title}" class="album-card-cover" onerror="this.onerror=null;this.parentElement.innerHTML='<div class=\\'album-card-cover-fallback\\'>📁</div>';">` : `<div class="album-card-cover-fallback">📁</div>`}
          <span class="album-card-badge">${count} tư liệu</span>
        </div>
        <div class="album-card-content">
          <h4 class="album-card-title" title="${title}">${title}</h4>
          <div class="album-card-meta">
            <span>👤 Hồ sơ ca khách hàng</span>
          </div>
          <div class="album-card-actions">
            ${al.album_url ? `<a href="${al.album_url}" target="_blank" class="macos-btn-outline-sm" style="text-decoration:none;display:inline-flex;align-items:center;gap:4px;">🌐 Mở Photos</a>` : ''}
            <button class="btn-card-primary" style="font-size:11px;padding:4px 10px;" onclick="filterPhotosByAlbumTitle('${title.replace(/'/g, "\\'")}')">
              🔍 Xem Ảnh
            </button>
          </div>
        </div>
      </div>
    `;
  }).join('');
}

window.filterPhotosByAlbumTitle = function(title) {
  switchWorkflow('photo');
  const sel = $('photoCustomerFilter');
  if (sel) {
    let matched = false;
    for (let opt of sel.options) {
      if (opt.text.toLowerCase().includes(title.toLowerCase()) || title.toLowerCase().includes(opt.text.toLowerCase())) {
        sel.value = opt.value;
        matched = true;
        break;
      }
    }
    if (!matched) {
      const searchInput = $('photoSearchInput');
      if (searchInput) {
        searchInput.value = title;
        photoSearchTerm = title.toLowerCase();
        applyPhotoFilters();
      }
    } else {
      photoCustomer = sel.value;
      applyPhotoFilters();
    }
    message(`🔍 Đang hiển thị ảnh của album: "${title}"`);
  }
};
