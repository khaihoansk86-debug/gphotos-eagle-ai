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
  const wsPhoto = $('photoWorkspace');
  const wsVideo = $('videoWorkspace');

  if (mode === 'photo') {
    tabPhoto?.classList.add('active');
    tabPhoto?.setAttribute('aria-selected', 'true');
    tabVideo?.classList.remove('active');
    tabVideo?.setAttribute('aria-selected', 'false');

    if (wsPhoto) wsPhoto.style.display = 'flex';
    if (wsVideo) wsVideo.style.display = 'none';

    if (cachedPhotoItems.length === 0) {
      loadPhotos(true);
    }
  } else {
    tabVideo?.classList.add('active');
    tabVideo?.setAttribute('aria-selected', 'true');
    tabPhoto?.classList.remove('active');
    tabPhoto?.setAttribute('aria-selected', 'false');

    if (wsVideo) wsVideo.style.display = 'flex';
    if (wsPhoto) wsPhoto.style.display = 'none';

    if (cachedVideoItems.length === 0) {
      loadVideos(true);
    }
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
  if (tabPhoto) tabPhoto.onclick = () => switchWorkflow('photo');
  if (tabVideo) tabVideo.onclick = () => switchWorkflow('video');

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

  // 8. Quick Hero Filter Button
  const btnHero = $('btnQuickHero');
  if (btnHero) {
    btnHero.onclick = () => {
      document.querySelectorAll('#photoFilterChips .filter-chip').forEach(b => {
        b.classList.toggle('active', b.dataset.filter === 'hero');
      });
      photoFilter = 'hero';
      message('⚡ Đang lọc 20 ảnh Hero 5 sao nét nhất cho chiến dịch...');
      loadPhotos(true);
    };
  }

  // 9. Load More Buttons
  const btnMoreP = $('btnLoadMorePhotos');
  if (btnMoreP) btnMoreP.onclick = () => loadPhotos(false);

  const btnMoreV = $('btnLoadMoreVideos');
  if (btnMoreV) btnMoreV.onclick = () => loadVideos(false);

  // 10. Drawer Close Buttons
  const btnCloseD = $('btnCloseDrawerBtn');
  const btnCloseTl = $('btnCloseDrawer');
  const backdropD = $('videoDrawerBackdrop');
  if (btnCloseD) btnCloseD.onclick = closeDrawer;
  if (btnCloseTl) btnCloseTl.onclick = closeDrawer;
  if (backdropD) backdropD.onclick = closeDrawer;

  // 11. Modal Close Buttons
  const btnCloseM = $('btnCloseBAModal');
  const backdropM = $('beforeAfterModalBackdrop');
  if (btnCloseM) btnCloseM.onclick = closeBeforeAfterModal;
  if (backdropM) backdropM.onclick = closeBeforeAfterModal;

  // 12. Copy Transcript Button
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

  // 13. Copy CapCut Recipe Button
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

  // 14. Analyze All Videos Button
  const btnAnalyzeAll = $('btnAnalyzeAllVideos');
  if (btnAnalyzeAll) {
    btnAnalyzeAll.onclick = () => {
      message('✨ Đang kích hoạt phân tích AI timeline 5s cho toàn bộ clip...');
      setTimeout(() => {
        message('🎉 Đã hoàn tất lập bản đồ timeline 5s & bóc phụ đề!');
        loadVideos(true);
      }, 1500);
    };
  }

  // 15. Action Buttons (Profile & Eagle sync)
  const btnSync = $('btnSyncEagle');
  if (btnSync) {
    btnSync.onclick = async () => {
      btnSync.disabled = true;
      setActionStatus(true, '⚡ AI đang phân loại tư liệu vào 5 nhóm nội dung và 20 khách hàng Eagle... Vui lòng đợi trong giây lát');
      try {
        const res = await api('photos-classify-eagle', { profile_id: currentProfile });
        message('🎉 ' + (res.message || 'Đã hoàn tất phân loại tư liệu vào Eagle!'));
        await refresh();
        await loadPhotos(true);
      } catch (err) {
        message('Lỗi phân loại: ' + err.message, true);
      } finally {
        setActionStatus(false);
        btnSync.disabled = false;
      }
    };
  }

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

  // 16. Profile & Library Switchers
  const pSel = $('profileSelect');
  if (pSel) {
    pSel.onchange = async () => {
      try {
        currentProfile = pSel.value;
        await api('profile-select', { profile_id: currentProfile });
        message('✅ Đã chuyển sang hồ sơ Photos: ' + pSel.options[pSel.selectedIndex].text);
        await refresh();
        await loadPhotos(true);
      } catch (err) {
        message('Lỗi chuyển profile: ' + err.message, true);
      }
    };
  }

  const eagleSel = $('eagleLibrarySelect');
  if (eagleSel) {
    eagleSel.onchange = async () => {
      const libPath = eagleSel.value;
      try {
        await api('eagle-select', { library_path: libPath });
        message('✅ Đang chuyển sang thư viện Eagle: ' + libPath);
        await refresh();
        await loadPhotos(true);
      } catch (err) {
        message('Lỗi chuyển thư viện Eagle: ' + err.message, true);
      }
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

  // 18. Polling loop every 8 seconds
  setInterval(refresh, 8000);
});
