// ============================================================
// SWITCHBOARD — app.js  (complete rewrite / consolidated)
// ============================================================

const state = {
  videoPath: null,
  videoFilename: null,
  videoSizeMb: null,
  thumbnails: { youtube: null, facebook: null, instagram: null },
  settings: {},
  templates: { titles: [], hashtags: [], descriptions: [] },
  connectionStatus: { youtube: false, facebook: false, instagram: false }
};

const $ = id => document.getElementById(id);

// ============================================================
// Toast notifications
// ============================================================
function toast(message, type = 'info', duration = 3500) {
  const container = $('toastContainer');
  const el = document.createElement('div');
  el.className = `toast toast--${type}`;
  el.textContent = message;
  container.appendChild(el);
  requestAnimationFrame(() => el.classList.add('toast--visible'));
  setTimeout(() => {
    el.classList.remove('toast--visible');
    setTimeout(() => el.remove(), 350);
  }, duration);
}

// ============================================================
// View navigation
// ============================================================
let currentView = 'upload';

function switchView(viewName) {
  currentView = viewName;
  document.querySelectorAll('.view').forEach(v => {
    v.hidden = v.dataset.view !== viewName;
  });
  document.querySelectorAll('.bottom-nav__item, .topnav__tab').forEach(b => {
    b.classList.toggle('is-active', b.dataset.view === viewName);
  });
  // Transmit bar only on upload
  $('transmitBar').hidden = viewName !== 'upload';

  if (viewName === 'schedule') loadSchedules();
  if (viewName === 'history') loadHistory();
}

document.querySelectorAll('.bottom-nav__item').forEach(btn =>
  btn.addEventListener('click', () => switchView(btn.dataset.view))
);
document.querySelectorAll('.topnav__tab').forEach(btn =>
  btn.addEventListener('click', () => switchView(btn.dataset.view))
);

// ============================================================
// Video upload — with drag-and-drop
// ============================================================
const sourceCard  = $('sourceCard');
const videoInput  = $('videoInput');
const sourceEmpty = $('sourceEmpty');
const sourcePreview = $('sourcePreview');
const previewVideo  = $('previewVideo');

// Click to browse
sourceEmpty.addEventListener('click', () => videoInput.click());

// Drag-and-drop
sourceCard.addEventListener('dragover', e => {
  e.preventDefault();
  sourceCard.classList.add('drag-over');
});
sourceCard.addEventListener('dragleave', e => {
  if (!sourceCard.contains(e.relatedTarget)) sourceCard.classList.remove('drag-over');
});
sourceCard.addEventListener('drop', e => {
  e.preventDefault();
  sourceCard.classList.remove('drag-over');
  const file = e.dataTransfer.files[0];
  if (file && file.type.startsWith('video/')) {
    uploadVideo(file);
  } else {
    toast('Please drop a video file (MP4, MOV, WEBM)', 'error');
  }
});

videoInput.addEventListener('change', e => {
  const file = e.target.files[0];
  if (file) uploadVideo(file);
});

async function uploadVideo(file) {
  const MAX_MB = 500;
  if (file.size > MAX_MB * 1024 * 1024) {
    toast(`Video exceeds ${MAX_MB} MB limit`, 'error');
    return;
  }

  sourceEmpty.hidden = true;
  sourcePreview.hidden = false;
  previewVideo.src = URL.createObjectURL(file);
  $('sourceFilename').textContent = file.name;
  $('sourceSize').textContent = `${(file.size / 1024 / 1024).toFixed(1)} MB`;

  const progressEl = $('uploadProgress');
  const fillEl     = $('uploadProgressFill');
  const labelEl    = $('uploadProgressLabel');
  progressEl.hidden = false;
  fillEl.style.width = '0%';
  labelEl.textContent = 'Uploading…';

  const formData = new FormData();
  formData.append('file', file);

  try {
    const result = await xhrUpload('/api/upload/video', formData, pct => {
      fillEl.style.width = pct + '%';
      labelEl.textContent = pct < 100 ? `Uploading… ${pct}%` : 'Processing…';
    });

    state.videoPath     = result.path;
    state.videoFilename = result.filename;
    state.videoSizeMb   = result.size_mb;

    fillEl.style.width = '100%';
    labelEl.textContent = '✓ Ready';
    setTimeout(() => { progressEl.hidden = true; }, 1400);

    $('aiCard').hidden       = false;
    $('channels').hidden     = false;
    $('templatesCard').hidden = false;

    // Auto-fill Instagram public URL
    $('ig-video-url').value = window.location.origin + result.path;

    renderTemplates();
    updateTransmitButton();
    toast('Video uploaded and ready', 'success');
  } catch (err) {
    labelEl.textContent = 'Upload failed: ' + err.message;
    fillEl.style.width = '0%';
    toast('Upload failed: ' + err.message, 'error');
  }
}

function xhrUpload(url, formData, onProgress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open('POST', url);
    xhr.upload.onprogress = e => {
      if (e.lengthComputable) onProgress(Math.round((e.loaded / e.total) * 100));
    };
    xhr.onload = () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(JSON.parse(xhr.responseText));
      } else {
        let errorMsg = 'Upload failed';
        try {
          const errData = JSON.parse(xhr.responseText);
          errorMsg = errData.detail || errorMsg;
        } catch (e) { /* fallback to default message */ }
        reject(new Error(errorMsg));
      }
    };
    xhr.onerror = () => reject(new Error('Network error'));
    xhr.send(formData);
  });
}

$('removeVideo').addEventListener('click', () => {
  state.videoPath = state.videoFilename = state.videoSizeMb = null;
  state.thumbnails = { youtube: null, facebook: null, instagram: null };
  sourceEmpty.hidden = false;
  sourcePreview.hidden = true;
  $('channels').hidden = $('aiCard').hidden = $('templatesCard').hidden = true;
  previewVideo.src = '';
  videoInput.value = '';
  ['yt-thumb-preview','fb-thumb-preview','ig-thumb-preview'].forEach(id => {
    $(id).innerHTML = thumbPlaceholderSvg();
  });
  updateTransmitButton();
});

function thumbPlaceholderSvg() {
  return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8.5" cy="8.5" r="1.5"/><path d="M21 15l-5-5L5 21"/></svg>`;
}

// ============================================================
// Thumbnail uploads
// ============================================================
function setupThumbnailUpload(platform, uploadBtnId, inputId, previewId) {
  $(uploadBtnId).addEventListener('click', () => $(inputId).click());
  $(inputId).addEventListener('change', async e => {
    const file = e.target.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('file', file);
    try {
      const resp = await fetch('/api/upload/thumbnail', { method: 'POST', body: formData });
      const result = await resp.json();
      if (!resp.ok) throw new Error(result.detail || 'Upload failed');
      state.thumbnails[platform] = result.path;
      $(previewId).innerHTML = `<img src="${result.path}" alt="Thumbnail">`;
      toast(`${platform.charAt(0).toUpperCase()+platform.slice(1)} thumbnail set`, 'success', 2000);
    } catch (err) {
      toast('Thumbnail upload failed: ' + err.message, 'error');
    }
  });
}

setupThumbnailUpload('youtube',   'yt-thumb-upload-btn', 'yt-thumb-input',  'yt-thumb-preview');
setupThumbnailUpload('facebook',  'fb-thumb-upload-btn', 'fb-thumb-input',  'fb-thumb-preview');
setupThumbnailUpload('instagram', 'ig-thumb-upload-btn', 'ig-thumb-input',  'ig-thumb-preview');

// ============================================================
// YouTube frame picker
// ============================================================
const framePickerModal = $('framePickerModal');
const framePickerVideo = $('framePickerVideo');
const frameScrubber    = $('frameScrubber');

$('yt-thumb-frame-btn').addEventListener('click', () => {
  if (!state.videoPath) { toast('Upload a video first', 'error'); return; }
  framePickerVideo.src = state.videoPath;
  framePickerModal.hidden = false;
  framePickerVideo.addEventListener('loadedmetadata', () => {
    frameScrubber.max   = framePickerVideo.duration;
    frameScrubber.value = 0;
    updateFrameTime(0);
  }, { once: true });
});

$('closeFramePicker').addEventListener('click', () => { framePickerModal.hidden = true; });
framePickerModal.querySelector('.modal__backdrop').addEventListener('click', () => { framePickerModal.hidden = true; });

frameScrubber.addEventListener('input', () => {
  const t = parseFloat(frameScrubber.value);
  framePickerVideo.currentTime = t;
  updateFrameTime(t);
});

function updateFrameTime(seconds) {
  const m = Math.floor(seconds / 60);
  const s = Math.floor(seconds % 60);
  $('frameTime').textContent = `${m}:${s.toString().padStart(2,'0')}`;
}

$('confirmFrameBtn').addEventListener('click', async () => {
  const timestamp = parseFloat(frameScrubber.value);
  $('confirmFrameBtn').textContent = 'Extracting…';
  $('confirmFrameBtn').disabled = true;
  try {
    const resp = await fetch('/api/upload/extract-frame', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ video_path: state.videoPath, timestamp })
    });
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.detail || 'Extraction failed');
    state.thumbnails.youtube = result.path;
    $('yt-thumb-preview').innerHTML = `<img src="${result.path}" alt="Frame thumbnail">`;
    framePickerModal.hidden = true;
    toast('Frame saved as YouTube thumbnail', 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    $('confirmFrameBtn').textContent = 'Use this frame';
    $('confirmFrameBtn').disabled = false;
  }
});

// ============================================================
// Facebook → Instagram sync
// ============================================================
const fbTitle    = $('fb-title');
const fbHashtags = $('fb-hashtags');

function getMaxIgHashtags() {
  return parseInt(state.settings?.instagram?.max_hashtags ?? 5, 10);
}

function syncInstagramFromFacebook() {
  const title = fbTitle.value;
  const igTitleDisplay = $('ig-title-display');
  igTitleDisplay.textContent = title || '—';
  igTitleDisplay.classList.toggle('synced-title--empty', !title);

  const tags = fbHashtags.value.split(',').map(t => t.trim()).filter(Boolean);
  const max  = getMaxIgHashtags();
  $('ig-hashtag-limit').textContent = `first ${max} used`;

  const chips = $('ig-hashtag-chips');
  chips.innerHTML = '';
  if (!tags.length) {
    chips.innerHTML = '<span class="hashtag-chip">No hashtags yet</span>';
    return;
  }
  tags.forEach((tag, i) => {
    const chip = document.createElement('span');
    chip.className = 'hashtag-chip ' + (i < max ? 'hashtag-chip--active' : 'hashtag-chip--cut');
    chip.textContent = '#' + tag.replace(/^#/, '');
    chips.appendChild(chip);
  });
}

fbTitle.addEventListener('input', syncInstagramFromFacebook);
fbHashtags.addEventListener('input', syncInstagramFromFacebook);

// ============================================================
// Volume sliders
// ============================================================
['yt-volume','fb-volume','ig-volume'].forEach(id => {
  $(id).addEventListener('input', () => { $(id + '-val').textContent = $(id).value + '%'; });
});

// ============================================================
// YouTube Audio Library
// ============================================================
$('yt-audio-refresh').addEventListener('click', async () => {
  const select = $('yt-audio-select');
  select.innerHTML = '<option value="">Loading…</option>';
  try {
    const resp   = await fetch('/api/youtube/audio-library');
    const result = await resp.json();
    select.innerHTML = '<option value="">No music</option>';
    (result.tracks || []).forEach(t => {
      const opt = document.createElement('option');
      opt.value = t.id;
      opt.textContent = `${t.title} — ${t.channel}`;
      select.appendChild(opt);
    });
    if (result.note) select.innerHTML = `<option value="">${result.note}</option>`;
    if (!result.tracks?.length && !result.note) {
      toast('No tracks found — connect YouTube first', 'error');
    }
  } catch {
    select.innerHTML = '<option value="">Could not load library</option>';
    toast('Could not load Audio Library', 'error');
  }
});

$('yt-audio-select').addEventListener('change', () => {
  $('yt-volume-row').hidden = !$('yt-audio-select').value;
});

// ============================================================
// AI generation
// ============================================================
$('aiGenerateBtn').addEventListener('click', async () => {
  const context = $('aiContext').value.trim();
  if (!context) { toast('Describe your video first', 'error'); return; }

  const btn = $('aiGenerateBtn');
  btn.innerHTML = '<span class="spinner"></span> Generating…';
  btn.disabled = true;

  try {
    const resp   = await fetch('/api/ai/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ context })
    });
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.detail || 'Generation failed');

    $('yt-title').value       = result.title || '';
    $('yt-description').value = result.description || '';
    $('yt-tags').value        = (result.youtube_tags || []).join(', ');
    $('fb-title').value       = result.title || '';
    $('fb-hashtags').value    = (result.hashtags || []).join(', ');
    syncInstagramFromFacebook();
    toast('AI content generated!', 'success');
  } catch (err) {
    toast(err.message, 'error');
  } finally {
    btn.innerHTML = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v3m0 12v3M5.6 5.6l2.1 2.1m8.6 8.6 2.1 2.1M3 12h3m12 0h3M5.6 18.4l2.1-2.1m8.6-8.6 2.1-2.1"/></svg> Generate';
    btn.disabled = false;
  }
});

// ============================================================
// Saved templates
// ============================================================
async function loadTemplates() {
  try {
    const resp = await fetch('/api/settings/templates');
    state.templates = await resp.json();
    renderTemplates();
  } catch (err) { console.error('Templates load failed', err); }
}

function renderTemplates() {
  const titlesEl   = $('savedTitles');
  const hashtagsEl = $('savedHashtags');
  titlesEl.innerHTML = hashtagsEl.innerHTML = '';

  const mkChip = (text, onClick) => {
    const c = document.createElement('span');
    c.className = 'chip';
    c.textContent = text;
    c.addEventListener('click', onClick);
    return c;
  };

  (state.templates.titles || []).forEach(title => {
    titlesEl.appendChild(mkChip(title, () => {
      $('fb-title').value = $('yt-title').value = title;
      syncInstagramFromFacebook();
      toast('Title applied', 'info', 1500);
    }));
  });

  (state.templates.hashtags || []).forEach(tagSet => {
    hashtagsEl.appendChild(mkChip(tagSet, () => {
      $('fb-hashtags').value = tagSet;
      syncInstagramFromFacebook();
      toast('Hashtags applied', 'info', 1500);
    }));
  });

  // Show "no templates" state
  if (!state.templates.titles?.length) {
    titlesEl.innerHTML = '<span style="color:var(--text-faint);font-size:.82rem">No saved titles yet</span>';
  }
  if (!state.templates.hashtags?.length) {
    hashtagsEl.innerHTML = '<span style="color:var(--text-faint);font-size:.82rem">No saved hashtags yet — they\'re auto-saved after publishing</span>';
  }
}

async function saveCurrentAsTemplate() {
  const title    = $('fb-title').value.trim();
  const hashtags = $('fb-hashtags').value.trim();
  const calls = [];
  if (title)    calls.push(fetch('/api/settings/templates/add', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({category:'titles',   value: title}) }));
  if (hashtags) calls.push(fetch('/api/settings/templates/add', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({category:'hashtags', value: hashtags}) }));
  if (calls.length) { await Promise.all(calls); await loadTemplates(); }
}

// ============================================================
// Channel toggles
// ============================================================
document.querySelectorAll('.channel-toggle').forEach(t =>
  t.addEventListener('change', updateTransmitButton)
);

function getActiveChannels() {
  return [...document.querySelectorAll('.channel-toggle')]
    .filter(t => t.checked)
    .map(t => t.dataset.channel);
}

function updateTransmitButton() {
  const btn    = $('publishBtn');
  const label  = btn.querySelector('.transmit-btn__label');
  const active = getActiveChannels();

  document.querySelectorAll('.transmit-target').forEach(t => {
    t.classList.toggle('is-active', active.includes(t.dataset.channel));
    t.classList.remove('is-success','is-error','is-pulsing');
  });

  if (!state.videoPath) {
    btn.disabled = true;
    label.textContent = 'Select a video to begin';
  } else if (!active.length) {
    btn.disabled = true;
    label.textContent = 'Select at least one platform';
  } else {
    btn.disabled = false;
    label.textContent = `Publish to ${active.map(c => c.charAt(0).toUpperCase()+c.slice(1)).join(' + ')}`;
  }
}

// ============================================================
// Connection status
// ============================================================
async function checkConnections() {
  const [yt, fb, ig] = await Promise.all([
    fetch('/api/youtube/auth/status').then(r=>r.json()).catch(()=>({connected:false})),
    fetch('/api/facebook/auth/status').then(r=>r.json()).catch(()=>({connected:false})),
    fetch('/api/instagram/auth/status').then(r=>r.json()).catch(()=>({connected:false}))
  ]);

  setConnPill('yt-status', yt.connected);
  setConnPill('fb-status', fb.connected, fb.name);
  setConnPill('ig-status', ig.connected, ig.username ? '@'+ig.username : '');

  state.connectionStatus = { youtube: yt.connected, facebook: fb.connected, instagram: ig.connected };

  // On-air dot
  const anyOn = yt.connected || fb.connected || ig.connected;
  $('onAirDot').classList.toggle('is-live', anyOn);

  // Update channel header badge styles
  updateChannelConnectBadge('youtube',   yt.connected);
  updateChannelConnectBadge('facebook',  fb.connected);
  updateChannelConnectBadge('instagram', ig.connected);
  updateAuthButtons();
}

function setConnPill(id, connected, label) {
  const el = $(id);
  el.classList.toggle('status-pill--on',  connected);
  el.classList.toggle('status-pill--off', !connected);
  el.textContent = connected ? (label || 'Connected') : 'Not connected';
}

function updateChannelConnectBadge(platform, connected) {
  const map = { youtube:'yt', facebook:'fb', instagram:'ig' };
  const pfx = map[platform];
  const connectRow = $(`${pfx}-connect`);
  if (!connectRow) return;
  connectRow.classList.toggle('channel__connect--ok', connected);
}

// Auth flows
$('yt-auth-btn').addEventListener('click', async () => {
  if (state.connectionStatus.youtube) {
    if (!confirm('Disconnect YouTube?')) return;
    await fetch('/api/youtube/revoke', {method:'POST'});
    await checkConnections();
    toast('YouTube disconnected', 'info');
    return;
  }
  try {
    const resp = await fetch('/api/youtube/auth/start');
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.detail);
    window.location.href = result.auth_url;
  } catch (err) {
    toast(err.message + ' — configure YouTube in Settings first', 'error', 5000);
  }
});

$('fb-settings-link').addEventListener('click', openSettings);
$('ig-settings-link').addEventListener('click', openSettings);

// Dynamically update Connect button text
function updateAuthButtons() {
  const ytBtn = $('yt-auth-btn');
  if (ytBtn) ytBtn.textContent = state.connectionStatus.youtube ? 'Disconnect' : 'Connect';
}

// ============================================================
// Settings modal
// ============================================================
const settingsModal = $('settingsModal');

function openSettings() {
  loadSettingsIntoModal();
  settingsModal.hidden = false;
}

$('openSettings').addEventListener('click', openSettings);
$('closeSettings').addEventListener('click', () => { settingsModal.hidden = true; });
settingsModal.querySelector('.modal__backdrop').addEventListener('click', () => { settingsModal.hidden = true; });

async function loadSettingsIntoModal() {
  try {
    const s = await fetch('/api/settings/raw').then(r=>r.json());
    state.settings = s;
    $('set-anthropic-key').value    = s.general?.anthropic_api_key || '';
    $('set-yt-client-id').value     = s.youtube?.client_id || '';
    $('set-yt-client-secret').value = s.youtube?.client_secret || '';
    $('set-yt-redirect').value      = s.youtube?.redirect_uri || `${window.location.origin}/auth/youtube/callback`;
    $('set-fb-token').value         = s.facebook?.access_token || '';
    $('set-fb-page-id').value       = s.facebook?.page_id || '';
    $('set-ig-account-id').value    = s.instagram?.account_id || '';
    $('set-ig-max-hashtags').value  = s.instagram?.max_hashtags || 5;
  } catch (err) { console.error('Settings load failed', err); }
}

$('saveSettingsBtn').addEventListener('click', async () => {
  const btn = $('saveSettingsBtn');
  btn.textContent = 'Saving…';
  btn.disabled = true;

  const payload = {
    general:   { anthropic_api_key: $('set-anthropic-key').value },
    youtube:   { client_id: $('set-yt-client-id').value, client_secret: $('set-yt-client-secret').value, redirect_uri: $('set-yt-redirect').value },
    facebook:  { access_token: $('set-fb-token').value, page_id: $('set-fb-page-id').value },
    instagram: { account_id: $('set-ig-account-id').value, max_hashtags: parseInt($('set-ig-max-hashtags').value,10)||5 }
  };

  try {
    const resp = await fetch('/api/settings', { method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(payload) });
    if (!resp.ok) throw new Error('Save failed');
    const data = await resp.json();
    state.settings = data.settings;
    toast('Settings saved', 'success');
    syncInstagramFromFacebook();
    await checkConnections();
  } catch (err) {
    toast('Save failed: ' + err.message, 'error');
  } finally {
    btn.textContent = 'Save settings';
    btn.disabled = false;
  }
});

// ============================================================
// Helpers to get publish payload
// ============================================================
function buildPublishPayload(platforms) {
  const max = getMaxIgHashtags();
  const payload = { platforms };

  if (platforms.includes('youtube')) {
    payload.youtube_data = {
      video_path:      state.videoPath,
      title:           $('yt-title').value       || 'Untitled Short',
      description:     $('yt-description').value || '',
      tags:            $('yt-tags').value.split(',').map(t=>t.trim()).filter(Boolean),
      thumbnail_path:  state.thumbnails.youtube  || '',
      privacy:         $('yt-privacy').value
    };
  }
  if (platforms.includes('facebook')) {
    payload.facebook_data = {
      video_path:     state.videoPath,
      title:          $('fb-title').value    || 'Untitled Reel',
      hashtags:       $('fb-hashtags').value.split(',').map(t=>t.trim()).filter(Boolean),
      thumbnail_path: state.thumbnails.facebook || ''
    };
  }
  if (platforms.includes('instagram')) {
    payload.instagram_data = {
      video_path:     state.videoPath,
      video_url:      $('ig-video-url').value,
      title:          $('fb-title').value    || 'Untitled Reel',
      hashtags:       $('fb-hashtags').value.split(',').map(t=>t.trim()).filter(Boolean).slice(0, max),
      thumbnail_path: state.thumbnails.instagram || ''
    };
  }
  return payload;
}

// ============================================================
// Publish (Transmit)
// ============================================================
$('publishBtn').addEventListener('click', publishAll);

async function publishAll() {
  const active = getActiveChannels();
  if (!state.videoPath || !active.length) return;

  const btn   = $('publishBtn');
  const label = btn.querySelector('.transmit-btn__label');
  btn.disabled = true;
  btn.classList.add('is-sending');
  label.textContent = 'Transmitting…';

  // Pulse the target dots
  document.querySelectorAll('.transmit-target').forEach(t => {
    t.classList.remove('is-success','is-error');
    if (active.includes(t.dataset.channel)) {
      t.classList.add('is-pulsing');
      setTimeout(() => t.classList.remove('is-pulsing'), 1000);
    }
  });

  // Clear per-channel status lines
  [['yt','youtube'],['fb','facebook'],['ig','instagram']].forEach(([pfx]) => {
    const el = $(`${pfx}-result-status`);
    if (el) { el.textContent = ''; el.className = 'channel__status'; }
  });

  const payload = buildPublishPayload(active);

  try {
    const resp   = await fetch('/api/history/publish-all', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const result = await resp.json();
    if (!resp.ok) {
      throw new Error(result.detail || 'Transmission failed');
    }

    renderResults(result.results || {});
    await saveCurrentAsTemplate();
  } catch (err) {
    toast('Publish failed: ' + err.message, 'error');
  } finally {
    btn.classList.remove('is-sending');
    updateTransmitButton();
  }
}

function renderResults(results) {
  const platformMeta = {
    youtube:   { name: 'YouTube Shorts',   iconClass: 'channel__icon--youtube',   statusId: 'yt-result-status' },
    facebook:  { name: 'Facebook Reels',   iconClass: 'channel__icon--facebook',  statusId: 'fb-result-status' },
    instagram: { name: 'Instagram Reels',  iconClass: 'channel__icon--instagram', statusId: 'ig-result-status' }
  };

  const body = $('resultsBody');
  body.innerHTML = '';
  let anyFail = false;

  Object.entries(results).forEach(([platform, result]) => {
    const meta   = platformMeta[platform];
    const target = document.querySelector(`.transmit-target[data-channel="${platform}"]`);
    const statusEl = $(meta.statusId);

    if (result.success) {
      target?.classList.add('is-success');
      if (statusEl) { statusEl.textContent = '✓ Published'; statusEl.classList.add('channel__status--success'); }
    } else {
      anyFail = true;
      target?.classList.add('is-error');
      if (statusEl) { statusEl.textContent = '✕ ' + (result.error || 'Failed').slice(0, 80); statusEl.classList.add('channel__status--error'); }
    }

    const item = document.createElement('div');
    item.className = 'result-item';
    item.innerHTML = `
      <div class="result-item__icon ${meta.iconClass}">${platformIconSvg(platform)}</div>
      <div class="result-item__body">
        <div class="result-item__platform">${meta.name}</div>
        <div class="result-item__detail">
          ${result.success
            ? `Published!${result.url ? ` <a href="${result.url}" target="_blank" rel="noopener">View →</a>` : ''}`
            : `Failed: ${escapeHtml((result.error || 'Unknown error').slice(0, 200))}`}
        </div>
      </div>
    `;
    body.appendChild(item);
  });

  $('resultsModal').hidden = false;
  if (!anyFail) toast('All transmissions succeeded!', 'success', 4000);
}

function platformIconSvg(platform) {
  const icons = {
    youtube:   `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M23.5 6.2a3 3 0 0 0-2.1-2.1C19.5 3.5 12 3.5 12 3.5s-7.5 0-9.4.6A3 3 0 0 0 .5 6.2 31.3 31.3 0 0 0 0 12a31.3 31.3 0 0 0 .5 5.8 3 3 0 0 0 2.1 2.1c1.9.6 9.4.6 9.4.6s7.5 0 9.4-.6a3 3 0 0 0 2.1-2.1A31.3 31.3 0 0 0 24 12a31.3 31.3 0 0 0-.5-5.8ZM9.6 15.5v-7l6.3 3.5-6.3 3.5Z"/></svg>`,
    facebook:  `<svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor"><path d="M24 12.07C24 5.4 18.63 0 12 0S0 5.4 0 12.07C0 18.1 4.39 23.1 10.13 24v-8.44H7.08v-3.49h3.04V9.41c0-3 1.79-4.66 4.53-4.66 1.31 0 2.68.23 2.68.23v2.96H15.83c-1.49 0-1.96.92-1.96 1.87v2.26h3.32l-.53 3.49h-2.8V24C19.62 23.1 24 18.1 24 12.07Z"/></svg>`,
    instagram: `<svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8"><rect x="2" y="2" width="20" height="20" rx="5"/><circle cx="12" cy="12" r="4"/><circle cx="17.5" cy="6.5" r="1" fill="currentColor" stroke="none"/></svg>`
  };
  return icons[platform] || '';
}

function escapeHtml(str) {
  const d = document.createElement('div');
  d.textContent = str;
  return d.innerHTML;
}

$('closeResults').addEventListener('click', () => { $('resultsModal').hidden = true; });
$('resultsModal').querySelector('.modal__backdrop').addEventListener('click', () => { $('resultsModal').hidden = true; });

// ============================================================
// Scheduling
// ============================================================
$('createScheduleBtn').addEventListener('click', async () => {
  if (!state.videoPath) {
    toast('Upload a video on the Upload tab first', 'error');
    switchView('upload');
    return;
  }
  const dt = $('scheduleDateTime').value;
  if (!dt) { toast('Pick a date and time', 'error'); return; }

  const active = getActiveChannels();
  if (!active.length) { toast('Select at least one platform on the Upload tab', 'error'); return; }

  const payload = {
    ...buildPublishPayload(active),
    scheduled_time: dt,
    title: $('scheduleLabel').value || $('fb-title').value || 'Scheduled Upload'
  };

  try {
    const resp = await fetch('/api/schedule/create', {
      method: 'POST', headers: {'Content-Type':'application/json'}, body: JSON.stringify(payload)
    });
    const result = await resp.json();
    if (!resp.ok) throw new Error(result.detail || 'Scheduling failed');
    $('scheduleDateTime').value = $('scheduleLabel').value = '';
    await loadSchedules();
    toast('Scheduled successfully', 'success');
  } catch (err) {
    toast(err.message, 'error');
  }
});

async function loadSchedules() {
  const listEl = $('scheduleList');
  try {
    const schedules = await fetch('/api/schedule/list').then(r=>r.json());
    if (!schedules.length) {
      listEl.innerHTML = '<p class="empty-state">No schedules yet.</p>';
      return;
    }
    listEl.innerHTML = '';
    [...schedules]
      .sort((a,b) => new Date(b.scheduled_time) - new Date(a.scheduled_time))
      .forEach(s => {
        const dt = new Date(s.scheduled_time);
        const badgeMap = { pending:'pending', running:'running', completed:'success', partial_failure:'error', missed:'error' };
        const badgeClass = 'list-item__badge--' + (badgeMap[s.status] || 'pending');
        const item = document.createElement('div');
        item.className = 'list-item';
        item.innerHTML = `
          <div class="list-item__main">
            <div class="list-item__title">${escapeHtml(s.title)}</div>
            <div class="list-item__meta">${dt.toLocaleString()}</div>
          </div>
          <div class="list-item__platforms">
            ${s.platforms.map(p=>`<span class="platform-dot platform-dot--${p}" title="${p}"></span>`).join('')}
          </div>
          <span class="list-item__badge ${badgeClass}">${s.status}</span>
          ${s.status==='pending' ? `<button class="btn-text btn-text--danger" data-cancel="${s.id}">Cancel</button>` : ''}
        `;
        listEl.appendChild(item);
      });

    listEl.querySelectorAll('[data-cancel]').forEach(btn => {
      btn.addEventListener('click', async () => {
        await fetch(`/api/schedule/${btn.dataset.cancel}`, { method:'DELETE' });
        await loadSchedules();
        toast('Schedule cancelled', 'info');
      });
    });
  } catch {
    listEl.innerHTML = `<p class="empty-state">Could not load schedules.</p>`;
  }
}

// ============================================================
// History
// ============================================================
async function loadHistory() {
  const listEl = $('historyList');
  try {
    const history = await fetch('/api/history/list').then(r=>r.json());
    if (!history.length) {
      listEl.innerHTML = '<p class="empty-state">No uploads yet. Your transmissions will appear here.</p>';
      return;
    }
    listEl.innerHTML = '';
    history.forEach(h => {
      const dt = new Date(h.timestamp);
      const item = document.createElement('div');
      item.className = 'list-item';
      item.innerHTML = `
        <div class="list-item__main">
          <div class="list-item__title">${escapeHtml(h.title)}</div>
          <div class="list-item__meta">${h.platform} · ${dt.toLocaleString()}${h.error ? ' · <span style="color:var(--danger)">'+escapeHtml(h.error.slice(0,60))+'</span>' : ''}</div>
        </div>
        <span class="list-item__badge ${h.status==='success'?'list-item__badge--success':'list-item__badge--error'}">${h.status}</span>
      `;
      listEl.appendChild(item);
    });
  } catch {
    listEl.innerHTML = '<p class="empty-state">Could not load history.</p>';
  }
}

$('clearHistoryBtn').addEventListener('click', async () => {
  if (!confirm('Clear all upload history?')) return;
  await fetch('/api/history/clear', { method:'DELETE' });
  await loadHistory();
  toast('History cleared', 'info');
});

// ============================================================
// Init
// ============================================================
async function init() {
  // Set default redirect URI placeholder
  if ($('set-yt-redirect')) {
    $('set-yt-redirect').placeholder = `${window.location.origin}/auth/youtube/callback`;
  }

  try {
    state.settings = await fetch('/api/settings/raw').then(r=>r.json());
  } catch {}

  syncInstagramFromFacebook();
  await checkConnections();
  updateAuthButtons();
  await loadTemplates();
  fetch('/api/schedule/restore').catch(()=>{});
}

init();
