/**
 * SF Annotation Studio — overlay script injected via proxy
 * Inspired by Agentation (https://agentation.dev)
 */
(function() {
  'use strict';
  if (window.__SF_ANNOTATE_LOADED) return;
  window.__SF_ANNOTATE_LOADED = true;

  const CFG = window.SF_ANNOTATE || {};
  const PROJECT_ID = CFG.projectId || '';
  const API_BASE = CFG.apiBase || `/api/projects/${PROJECT_ID}`;
  const PAGE_URL = location.href;

  // ── State ──────────────────────────────────────────────────────
  let active = false;
  let annotType = 'comment';
  let annotations = [];
  let markersVisible = true;
  let paused = false;
  let areaStart = null;
  let areaRect = null;
  let hoveredEl = null;

  // ── Feather icons (inline SVG) ─────────────────────────────────
  const ICONS = {
    'edit-2': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>',
    'alert-circle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>',
    'message-square': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/></svg>',
    'move': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="5 9 2 12 5 15"/><polyline points="9 5 12 2 15 5"/><polyline points="15 19 12 22 9 19"/><polyline points="19 9 22 12 19 15"/><line x1="2" y1="12" x2="22" y2="12"/><line x1="12" y1="2" x2="12" y2="22"/></svg>',
    'sliders': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="4" y1="21" x2="4" y2="14"/><line x1="4" y1="10" x2="4" y2="3"/><line x1="12" y1="21" x2="12" y2="12"/><line x1="12" y1="8" x2="12" y2="3"/><line x1="20" y1="21" x2="20" y2="16"/><line x1="20" y1="12" x2="20" y2="3"/><line x1="1" y1="14" x2="7" y2="14"/><line x1="9" y1="8" x2="15" y2="8"/><line x1="17" y1="16" x2="23" y2="16"/></svg>',
    'eye': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>',
    'eye-off': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17.94 17.94A10.07 10.07 0 0112 20c-7 0-11-8-11-8a18.45 18.45 0 015.06-5.94M9.9 4.24A9.12 9.12 0 0112 4c7 0 11 8 11 8a18.5 18.5 0 01-2.16 3.19m-6.72-1.07a3 3 0 11-4.24-4.24"/><line x1="1" y1="1" x2="23" y2="23"/></svg>',
    'clipboard': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M16 4h2a2 2 0 012 2v14a2 2 0 01-2 2H6a2 2 0 01-2-2V6a2 2 0 012-2h2"/><rect x="8" y="2" width="8" height="4" rx="1" ry="1"/></svg>',
    'trash-2': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"/><path d="M19 6v14a2 2 0 01-2 2H7a2 2 0 01-2-2V6m3 0V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>',
    'pause-circle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/></svg>',
    'play-circle': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>',
    'type': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"/><line x1="9" y1="20" x2="15" y2="20"/><line x1="12" y1="4" x2="12" y2="20"/></svg>',
    'square': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"/></svg>',
    'zap': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>',
    'x': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>',
    'check': '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>',
  };

  // ── CSS injection ──────────────────────────────────────────────
  const styleEl = document.createElement('style');
  styleEl.textContent = `
    .sf-ann-highlight { outline: 2px solid #3b82f6 !important; outline-offset: 2px !important; cursor: crosshair !important; }
    .sf-ann-highlight-bug { outline-color: #ef4444 !important; }
    .sf-ann-highlight-move { outline-color: #f59e0b !important; }
    .sf-ann-highlight-ux { outline-color: #8b5cf6 !important; }
    .sf-ann-highlight-text { outline-color: #10b981 !important; }
    .sf-ann-marker { position: fixed; z-index: 2147483640; width: 22px; height: 22px; border-radius: 50%; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; font-family: system-ui, sans-serif; cursor: pointer; box-shadow: 0 2px 8px rgba(0,0,0,.4); transition: transform .15s; pointer-events: all; }
    .sf-ann-marker:hover { transform: scale(1.2); }
    .sf-ann-marker.type-bug { background: #ef4444; color: #fff; }
    .sf-ann-marker.type-comment { background: #3b82f6; color: #fff; }
    .sf-ann-marker.type-move { background: #f59e0b; color: #fff; }
    .sf-ann-marker.type-ux { background: #8b5cf6; color: #fff; }
    .sf-ann-marker.type-text { background: #10b981; color: #fff; }
    .sf-ann-marker.type-area { background: #22c55e; color: #fff; }
    .sf-ann-area-rect { position: fixed; z-index: 2147483639; border: 2px dashed #22c55e; background: rgba(34,197,94,.08); pointer-events: none; }
  `;
  document.head.appendChild(styleEl);

  // ── Type metadata ──────────────────────────────────────────────
  const TYPE_META = {
    bug:     { label: 'Bug',     icon: 'alert-circle' },
    comment: { label: 'Comment', icon: 'message-square' },
    move:    { label: 'Move',    icon: 'move' },
    ux:      { label: 'UX',      icon: 'sliders' },
    text:    { label: 'Text',    icon: 'type' },
    area:    { label: 'Area',    icon: 'square' },
  };

  // ── CSS selector ───────────────────────────────────────────────
  function getSelector(el) {
    if (el.id) return `#${el.id}`;
    const parts = [];
    let cur = el;
    while (cur && cur !== document.body && parts.length < 4) {
      let part = cur.tagName.toLowerCase();
      if (cur.id) { part = `#${cur.id}`; parts.unshift(part); break; }
      const cls = Array.from(cur.classList).filter(c => !c.startsWith('sf-ann')).slice(0, 2);
      if (cls.length) part += '.' + cls.join('.');
      const siblings = cur.parentElement ? Array.from(cur.parentElement.children).filter(c => c.tagName === cur.tagName) : [];
      if (siblings.length > 1) part += `:nth-of-type(${siblings.indexOf(cur) + 1})`;
      parts.unshift(part);
      cur = cur.parentElement;
    }
    return parts.join(' > ');
  }

  // ── Computed CSS ───────────────────────────────────────────────
  function getComputedStylesStr(el) {
    try {
      const cs = window.getComputedStyle(el);
      const props = ['color','background-color','font-size','font-family','padding','margin','border-radius','display','position','width','height'];
      return props.map(p => `${p}: ${cs.getPropertyValue(p)}`).filter(s => !s.includes('rgba(0, 0, 0, 0)')).slice(0,8).join('; ');
    } catch { return ''; }
  }

  // ── React tree ─────────────────────────────────────────────────
  function getReactTree(el) {
    try {
      const key = Object.keys(el).find(k => k.startsWith('__reactFiber') || k.startsWith('__reactInternalInstance'));
      if (!key) return '';
      let fiber = el[key];
      const names = [];
      while (fiber && names.length < 5) {
        const name = fiber.type?.displayName || fiber.type?.name;
        if (name && !name.startsWith('_') && name !== 'Fragment') names.push(name);
        fiber = fiber.return;
      }
      return names.reverse().join(' > ');
    } catch { return ''; }
  }

  // ── Toolbar ────────────────────────────────────────────────────
  function buildToolbar() {
    // Inject theme-aware CSS for toolbar
    const style = document.createElement('style');
    style.textContent = `
      #sf-ann-toolbar {
        position: fixed; z-index: 2147483647; bottom: 24px; right: 24px;
        background: var(--bg-secondary, #ffffff);
        border: 1px solid var(--border, #d0d7de);
        border-radius: 12px; padding: 8px;
        display: flex; align-items: center; gap: 4px;
        box-shadow: 0 4px 20px rgba(0,0,0,.12);
        user-select: none; font-family: system-ui, -apple-system, sans-serif;
        transition: box-shadow .2s;
      }
      #sf-ann-toolbar button {
        background: transparent;
        color: var(--text-secondary, #57606a);
        border: none; border-radius: 7px; padding: 0;
        cursor: pointer; display: inline-flex; align-items: center; justify-content: center;
        width: 28px; height: 28px; transition: background .12s, color .12s;
      }
      #sf-ann-toolbar button:hover {
        background: var(--bg-tertiary, #f6f8fa);
        color: var(--text-primary, #1f2328);
      }
      #sf-ann-toolbar button.sf-tb-active {
        background: var(--accent, #0969da);
        color: #fff !important;
      }
      #sf-ann-toolbar button.sf-tb-accent {
        background: #7c3aed; color: #fff;
      }
      #sf-ann-toolbar button.sf-tb-accent:hover { background: #6d28d9; }
      #sf-tb-toggle { width: auto !important; padding: 0 10px !important; gap: 6px; }
      #sf-tb-toggle svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2; flex-shrink: 0; }
      #sf-tb-label { font-size: 11px; font-weight: 600; white-space: nowrap; }
      #sf-ann-toolbar .sf-tb-sep {
        width: 1px; height: 20px;
        background: var(--border, #d0d7de); margin: 0 2px; flex-shrink: 0;
      }
      #sf-ann-toolbar button svg { width: 14px; height: 14px; stroke: currentColor; fill: none; stroke-width: 2; }
      #sf-tb-type-bar button.sf-tb-selected {
        background: var(--bg-tertiary, #f6f8fa);
        color: var(--text-primary, #1f2328);
        outline: 2px solid var(--accent, #0969da);
        outline-offset: -2px;
      }
      #sf-ann-mode-banner {
        display: none; position: fixed; top: 0; left: 0; right: 0; z-index: 2147483646;
        background: var(--accent, #0969da); color: #fff;
        font-family: system-ui, sans-serif; font-size: 12px; font-weight: 600;
        padding: 5px 16px; align-items: center; justify-content: space-between; gap: 12px;
        box-shadow: 0 2px 8px rgba(0,0,0,.15);
      }
      #sf-ann-mode-banner button {
        background: rgba(255,255,255,.2); border: none; color: #fff;
        border-radius: 4px; padding: 2px 10px; cursor: pointer;
        font-size: 11px; font-weight: 600; white-space: nowrap;
        width: auto !important; height: auto !important;
      }
    `;
    document.head.appendChild(style);

    const tb = document.createElement('div');
    tb.id = 'sf-ann-toolbar';
    tb.innerHTML = `
      <button id="sf-tb-toggle" title="Annoter cette page (Ctrl+Shift+A)">
        <svg viewBox="0 0 24 24"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
        <span id="sf-tb-label">Annoter</span>
      </button>
      <div id="sf-tb-expanded" style="display:none;align-items:center;gap:3px">
        <div id="sf-tb-type-bar" style="display:flex;align-items:center;gap:3px">
          ${Object.entries(TYPE_META).map(([k,v]) => `
            <button class="sf-tb-type" data-type="${k}" title="${v.label}">
              <svg viewBox="0 0 24 24">${ICONS[v.icon].replace(/<svg[^>]*>/,'').replace('</svg>','')}</svg>
            </button>
          `).join('')}
        </div>
        <div class="sf-tb-sep"></div>
        <button id="sf-tb-pause" title="Pause animations (P)">
          <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/></svg>
        </button>
        <button id="sf-tb-visibility" title="Afficher/masquer marqueurs (H)">
          <svg viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/></svg>
        </button>
        <button id="sf-tb-copy" title="Copier markdown (C)">
          <svg viewBox="0 0 24 24"><rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 01-2-2V4a2 2 0 012-2h9a2 2 0 012 2v1"/></svg>
        </button>
        <button id="sf-tb-clear" title="Effacer tout (X)">
          <svg viewBox="0 0 24 24"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 011-1h4a1 1 0 011 1v2"/></svg>
        </button>
        <div class="sf-tb-sep"></div>
        <button id="sf-tb-fixall" class="sf-tb-accent" title="Fix All — créer une mission agent">
          <svg viewBox="0 0 24 24"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>
        </button>
        <button id="sf-tb-view" title="Voir toutes les annotations">
          <svg viewBox="0 0 24 24"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/></svg>
        </button>
      </div>
    `;
    document.body.appendChild(tb);

    // Mode banner
    const banner = document.createElement('div');
    banner.id = 'sf-ann-mode-banner';
    banner.innerHTML = `
      <span style="display:flex;align-items:center;gap:8px">
        <svg style="width:13px;height:13px;stroke:rgba(255,255,255,.8);fill:none;stroke-width:2" viewBox="0 0 24 24"><path d="M17 3a2.828 2.828 0 114 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
        Mode Annotation actif — cliquez un élément pour annoter · <kbd style="background:rgba(255,255,255,.2);border-radius:3px;padding:0 4px">Ctrl+Shift+A</kbd> pour désactiver
      </span>
      <button onclick="window.toggleAnnotate()">
        <svg style="width:11px;height:11px;stroke:currentColor;fill:none;stroke-width:2.5;margin-right:4px" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        Désactiver
      </button>
    `;
    document.body.appendChild(banner);

    // Make draggable
    let tbDrag = null;
    tb.addEventListener('mousedown', e => {
      if (e.target.closest('button')) return;
      tbDrag = {x: e.clientX - tb.offsetLeft, y: e.clientY - tb.offsetTop};
      tb.style.cursor = 'grabbing';
    });
    document.addEventListener('mousemove', e => {
      if (!tbDrag) return;
      tb.style.left = (e.clientX - tbDrag.x) + 'px';
      tb.style.top = (e.clientY - tbDrag.y) + 'px';
      tb.style.right = 'auto'; tb.style.bottom = 'auto';
    });
    document.addEventListener('mouseup', () => { tbDrag = null; tb.style.cursor = ''; });

    // Events
    document.getElementById('sf-tb-toggle').addEventListener('click', toggleAnnotate);
    document.getElementById('sf-tb-pause').addEventListener('click', togglePause);
    document.getElementById('sf-tb-visibility').addEventListener('click', toggleVisibility);
    document.getElementById('sf-tb-copy').addEventListener('click', copyMarkdown);
    document.getElementById('sf-tb-clear').addEventListener('click', clearAll);
    document.getElementById('sf-tb-fixall').addEventListener('click', fixAll);
    document.getElementById('sf-tb-view').addEventListener('click', () => window.open('/annotate/_sf', '_blank'));
    document.querySelectorAll('.sf-tb-type').forEach(btn => {
      btn.addEventListener('click', () => setType(btn.dataset.type));
    });

    setType('comment');
    return tb;
  }

  function btnStyle(bg, color) {
    return `background:${bg};color:${color};border:none;border-radius:7px;padding:0;cursor:pointer;display:inline-flex;align-items:center;justify-content:center;width:28px;height:28px;transition:background .12s,color .12s;`;
  }

  // ── Toggle Annotate ────────────────────────────────────────────
  function toggleAnnotate() {
    active = !active;
    const btn = document.getElementById('sf-tb-toggle');
    const expanded = document.getElementById('sf-tb-expanded');
    const lbl = document.getElementById('sf-tb-label');
    btn.classList.toggle('sf-tb-active', active);
    if (lbl) lbl.textContent = active ? 'Annoter ON' : 'Annoter';
    if (expanded) expanded.style.display = active ? 'flex' : 'none';
    document.body.style.cursor = active ? 'crosshair' : '';
    if (!active && hoveredEl) { hoveredEl.classList.remove('sf-ann-highlight', `sf-ann-highlight-${annotType}`); hoveredEl = null; }
    const banner = document.getElementById('sf-ann-mode-banner');
    if (banner) banner.style.display = active ? 'flex' : 'none';
    // Show wireframe button only when annotation is active
    const wfBtn = document.getElementById('sfWireframeBtn');
    if (wfBtn) wfBtn.style.display = active ? '' : 'none';
    // Turn off wireframe when annotation is deactivated
    if (!active && document.body.classList.contains('sf-wireframe') && window.toggleWireframeMode) {
      window.toggleWireframeMode();
    }
  }

  // ── Capture-phase click interceptor — blocks ALL navigation when active ──
  document.addEventListener('click', e => {
    if (!active) return;
    if (e.target.closest('#sf-ann-toolbar') || e.target.closest('#sf-ann-popover') || e.target.closest('.sf-ann-marker')) return;
    e.preventDefault();
    e.stopImmediatePropagation();
  }, true);

  function setType(type) {
    annotType = type;
    document.querySelectorAll('.sf-tb-type').forEach(btn => {
      btn.classList.toggle('sf-tb-selected', btn.dataset.type === type);
    });
  }

  function togglePause() {
    paused = !paused;
    document.querySelectorAll('*').forEach(el => {
      el.style.animationPlayState = paused ? 'paused' : '';
      el.style.transitionDuration = paused ? '0s' : '';
    });
    const btn = document.getElementById('sf-tb-pause');
    btn.innerHTML = paused
      ? `<svg viewBox="0 0 24 24" style="width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2"><circle cx="12" cy="12" r="10"/><polygon points="10 8 16 12 10 16 10 8"/></svg>`
      : `<svg viewBox="0 0 24 24" style="width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2"><circle cx="12" cy="12" r="10"/><line x1="10" y1="15" x2="10" y2="9"/><line x1="14" y1="15" x2="14" y2="9"/></svg>`;
    btn.style.color = paused ? '#fbbf24' : 'rgba(255,255,255,.5)';
  }

  function toggleVisibility() {
    markersVisible = !markersVisible;
    document.querySelectorAll('.sf-ann-marker').forEach(m => {
      m.style.display = markersVisible ? '' : 'none';
    });
    const btn = document.getElementById('sf-tb-visibility');
    btn.innerHTML = ICONS[markersVisible ? 'eye' : 'eye-off'];
  }

  async function copyMarkdown() {
    const resp = await fetch(`${API_BASE}/annotations/export`);
    const data = await resp.json();
    await navigator.clipboard.writeText(data.markdown).catch(() => {
      prompt('Copy this markdown:', data.markdown);
    });
    flashBtn('sf-tb-copy');
  }

  function clearAll() {
    if (!confirm('Clear all annotations on this page?')) return;
    document.querySelectorAll('.sf-ann-marker').forEach(m => m.remove());
    annotations = [];
  }

  async function fixAll() {
    const resp = await fetch(`${API_BASE}/annotations/fix-all`, {method: 'POST'});
    const data = await resp.json();
    if (data.mission_id) alert(`Mission created! ID: ${data.mission_id}`);
    else alert(data.error || 'Error');
  }

  function flashBtn(id) {
    const btn = document.getElementById(id);
    if (!btn) return;
    btn.style.color = '#4ade80';
    setTimeout(() => { btn.style.color = ''; }, 1500);
  }

  // ── Hover ──────────────────────────────────────────────────────
  document.addEventListener('mouseover', e => {
    if (!active) return;
    const el = e.target;
    if (el.id?.startsWith('sf-ann') || el.closest('#sf-ann-toolbar')) return;
    if (hoveredEl && hoveredEl !== el) {
      hoveredEl.classList.remove('sf-ann-highlight', `sf-ann-highlight-${annotType}`);
    }
    hoveredEl = el;
    el.classList.add('sf-ann-highlight', `sf-ann-highlight-${annotType}`);
  });

  // ── Click / area annotation ────────────────────────────────────
  document.addEventListener('mousedown', e => {
    if (!active) return;
    if (e.target.closest('#sf-ann-toolbar')) return;
    if (annotType === 'area') {
      areaStart = {x: e.clientX, y: e.clientY};
      areaRect = document.createElement('div');
      areaRect.className = 'sf-ann-area-rect';
      areaRect.style.cssText = `left:${e.clientX}px;top:${e.clientY}px;width:0;height:0`;
      document.body.appendChild(areaRect);
      e.preventDefault();
    }
  });

  document.addEventListener('mousemove', e => {
    if (!active || !areaStart || !areaRect) return;
    const x = Math.min(e.clientX, areaStart.x);
    const y = Math.min(e.clientY, areaStart.y);
    const w = Math.abs(e.clientX - areaStart.x);
    const h = Math.abs(e.clientY - areaStart.y);
    areaRect.style.left = x + 'px';
    areaRect.style.top = y + 'px';
    areaRect.style.width = w + 'px';
    areaRect.style.height = h + 'px';
  });

  document.addEventListener('mouseup', e => {
    if (!active) return;
    if (e.target.closest('#sf-ann-toolbar')) return;

    if (annotType === 'area' && areaStart) {
      const r = {
        x: Math.min(e.clientX, areaStart.x),
        y: Math.min(e.clientY, areaStart.y),
        w: Math.abs(e.clientX - areaStart.x),
        h: Math.abs(e.clientY - areaStart.y),
      };
      areaRect && areaRect.remove();
      areaRect = null; areaStart = null;
      if (r.w > 20 && r.h > 20) showPopover(null, r);
      return;
    }

    const el = document.elementFromPoint(e.clientX, e.clientY);
    if (!el || el.closest('#sf-ann-toolbar') || el.classList.contains('sf-ann-marker')) return;
    e.preventDefault();
    e.stopPropagation();
    showPopover(el, null);
  }, true);

  // ── Text selection ─────────────────────────────────────────────
  document.addEventListener('mouseup', e => {
    if (!active) return;
    const sel = window.getSelection();
    if (sel && sel.toString().trim().length > 3) {
      const range = sel.getRangeAt(0);
      const rect = range.getBoundingClientRect();
      const text = sel.toString().trim();
      sel.removeAllRanges();
      showPopover(range.commonAncestorContainer.parentElement, null, text, {x: rect.left, y: rect.top});
    }
  });

  // ── Popover ────────────────────────────────────────────────────
  let currentPopover = null;
  function showPopover(el, areaR, quotedText, pos) {
    if (currentPopover) currentPopover.remove();

    const popup = document.createElement('div');
    popup.id = 'sf-ann-popover';
    const selector = el ? getSelector(el) : '';
    const elText = el ? (el.textContent || '').trim().substring(0, 40) : '';
    const css = el ? getComputedStylesStr(el) : '';
    const reactTree = el ? getReactTree(el) : '';

    const pLeft = pos?.x ?? (areaR ? areaR.x : (el ? el.getBoundingClientRect().left : 200));
    const pTop = pos?.y ?? (areaR ? areaR.y + areaR.h + 8 : (el ? el.getBoundingClientRect().bottom + 8 : 300));

    const effectiveType = quotedText ? 'text' : annotType;

    popup.style.cssText = `
      position: fixed; z-index: 2147483646;
      left: ${Math.min(pLeft, window.innerWidth - 320)}px;
      top: ${Math.min(pTop, window.innerHeight - 200)}px;
      width: 300px;
      background: var(--bg-secondary, #ffffff);
      border: 1px solid var(--border, #d0d7de);
      border-radius: 10px; padding: 12px;
      box-shadow: 0 8px 32px rgba(0,0,0,.12);
      font-family: system-ui, sans-serif;
    `;

    popup.innerHTML = `
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:10px">
        <div style="display:flex;gap:4px">
          ${Object.entries(TYPE_META).filter(([k]) => !quotedText || k === 'text').map(([k,v]) => `
            <button class="sf-pop-type" data-type="${k}" style="padding:3px 8px;border-radius:5px;border:1px solid var(--border,#d0d7de);background:${k===effectiveType?'var(--accent,#0969da)':'transparent'};color:${k===effectiveType?'#fff':'var(--text-secondary,#57606a)'};cursor:pointer;font-size:11px">
              ${v.label}
            </button>
          `).join('')}
        </div>
        <button onclick="this.closest('#sf-ann-popover').remove()" style="background:none;border:none;color:var(--text-tertiary,#6e7781);cursor:pointer;padding:2px;display:inline-flex;align-items:center;justify-content:center;width:24px;height:24px;border-radius:4px">
          <svg style="width:14px;height:14px;stroke:currentColor;fill:none;stroke-width:2" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
        </button>
      </div>
      ${quotedText ? `<div style="font-size:11px;color:var(--text-secondary,#57606a);font-style:italic;margin-bottom:8px;padding:6px;background:var(--bg-tertiary,#f6f8fa);border-radius:5px;border-left:3px solid var(--accent,#0969da)">"${quotedText.substring(0,80)}"</div>` : ''}
      ${selector ? `<div style="font-size:10px;font-family:monospace;color:var(--text-tertiary,#6e7781);margin-bottom:8px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">${selector}</div>` : ''}
      <textarea id="sf-pop-msg" placeholder="Décrire le problème ou le feedback..." style="width:100%;min-height:64px;background:var(--bg-primary,#ffffff);border:1px solid var(--border,#d0d7de);border-radius:6px;color:var(--text-primary,#1f2328);font-size:12px;padding:8px;resize:vertical;font-family:inherit;outline:none;box-sizing:border-box">${quotedText ? 'Correction texte' : ''}</textarea>
      ${css ? `<details style="margin-top:6px"><summary style="font-size:10px;color:var(--text-tertiary,#6e7781);cursor:pointer">CSS styles</summary><div style="font-size:9px;font-family:monospace;color:var(--text-tertiary,#6e7781);margin-top:4px;white-space:pre-wrap;max-height:80px;overflow-y:auto">${css}</div></details>` : ''}
      <div style="display:flex;justify-content:flex-end;gap:6px;margin-top:10px">
        <button onclick="this.closest('#sf-ann-popover').remove()" style="padding:5px 12px;border-radius:6px;border:1px solid var(--border,#d0d7de);background:transparent;color:var(--text-secondary,#57606a);cursor:pointer;font-size:12px">Annuler</button>
        <button id="sf-pop-save" style="padding:5px 14px;border-radius:6px;border:none;background:var(--accent,#0969da);color:#fff;cursor:pointer;font-size:12px;font-weight:600">Ajouter</button>
      </div>
    `;

    document.body.appendChild(popup);
    currentPopover = popup;
    popup.querySelector('#sf-pop-msg').focus();

    let popType = effectiveType;
    popup.querySelectorAll('.sf-pop-type').forEach(btn => {
      btn.addEventListener('click', () => {
        popType = btn.dataset.type;
        popup.querySelectorAll('.sf-pop-type').forEach(b => {
          const sel = b.dataset.type === popType;
          b.style.background = sel ? 'var(--accent,#0969da)' : 'transparent';
          b.style.color = sel ? '#fff' : 'var(--text-secondary,#57606a)';
        });
      });
    });

    popup.querySelector('#sf-pop-save').addEventListener('click', async () => {
      const msg = popup.querySelector('#sf-pop-msg').value.trim();
      if (!msg) return;

      const vw = window.innerWidth, vh = window.innerHeight;
      const data = {
        type: popType,
        selector,
        element_text: elText,
        page_url: PAGE_URL,
        viewport_w: vw,
        viewport_h: vh,
        quoted_text: quotedText || '',
        computed_css: css,
        react_tree: reactTree,
        message: msg,
      };

      if (areaR) {
        data.x_pct = +(areaR.x / vw * 100).toFixed(1);
        data.y_pct = +(areaR.y / vh * 100).toFixed(1);
        data.w_pct = +(areaR.w / vw * 100).toFixed(1);
        data.h_pct = +(areaR.h / vh * 100).toFixed(1);
      } else if (el) {
        const r = el.getBoundingClientRect();
        data.x_pct = +(r.left / vw * 100).toFixed(1);
        data.y_pct = +(r.top / vh * 100).toFixed(1);
      }

      const resp = await fetch(`${API_BASE}/annotations`, {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify(data),
      });
      const saved = await resp.json();

      placeMarker(saved.seq_num, data, areaR ? {x: areaR.x, y: areaR.y} : (el ? el.getBoundingClientRect() : {left: 100, top: 100}));
      popup.remove(); currentPopover = null;
      // Notify parent frame
      if (window.parent !== window) window.parent.postMessage({type: 'sf-annotation', id: saved.id}, '*');
    });
  }

  // ── Markers ────────────────────────────────────────────────────
  function placeMarker(seqNum, data, rect) {
    const m = document.createElement('div');
    m.className = `sf-ann-marker type-${data.type}`;
    m.textContent = seqNum;
    const x = rect.left ?? rect.x ?? 0;
    const y = rect.top ?? rect.y ?? 0;
    m.style.left = (x - 8) + 'px';
    m.style.top = (y - 8) + 'px';
    m.title = `#${seqNum}: ${data.message}`;
    m.addEventListener('click', () => { if (confirm('Remove this annotation?')) m.remove(); });
    document.body.appendChild(m);
    return m;
  }

  // ── Keyboard shortcuts ─────────────────────────────────────────
  document.addEventListener('keydown', e => {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) return;
    if ((e.ctrlKey || e.metaKey) && e.shiftKey && e.key === 'A') { e.preventDefault(); toggleAnnotate(); }
    if (!active) return;
    if (e.key === 'Escape') { if (currentPopover) { currentPopover.remove(); currentPopover = null; } else { toggleAnnotate(); } }
    if (e.key === 'p' || e.key === 'P') togglePause();
    if (e.key === 'h' || e.key === 'H') toggleVisibility();
    if (e.key === 'c' || e.key === 'C') copyMarkdown();
    if (e.key === 'x' || e.key === 'X') clearAll();
  });

  // ── Init ───────────────────────────────────────────────────────
  function init() {
    buildToolbar();
    // Do NOT auto-activate — user clicks "Annoter" button to start
  }

  window.toggleAnnotate = toggleAnnotate;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
