/* One Local update surface shared by all tool pages. */
(() => {
  'use strict';
  let status, dialog, openButton, message, notes, version, updateButton, staleButton, lastAttempt;
  const tabId = [...crypto.getRandomValues(new Uint32Array(4))].join('-');
  const snapshotKey = 'afc.update.resume.' + location.pathname;
  let prepared = '', saved = false, warnings = [], frozen = false, installing = false;
  let requestedHere = '', pageVersion = '', installIntent = 0;
  let pendingRequests = 0;
  const fetchOriginal = window.fetch.bind(window);
  window.fetch = async (...args) => {
    const url = String(args[0]?.url || args[0]);
    const tracked = !url.includes('/api/local/update');
    if (tracked) pendingRequests++;
    try { return await fetchOriginal(...args); }
    finally { if (tracked) setTimeout(() => {pendingRequests--;}, 0); }
  };
  function freeze(on) {
    frozen = on;
    for (const node of document.body.children) {
      if (node === dialog || node === openButton || ['SCRIPT','STYLE'].includes(node.tagName)) continue;
      if (on && !node.inert) {node.inert = true; node.dataset.afcFrozen = '1';}
      if (!on && node.dataset.afcFrozen) {node.inert = false; delete node.dataset.afcFrozen;}
    }
  }
  function capture(data) {
    const hook = window.afcUpdateDraft;
    if (!hook || !hook.ready()) throw new Error('หน้าเครื่องมือยังโหลดไม่เสร็จ');
    const snapshot = hook.capture();
    const files = [...document.querySelectorAll('input[type=file]')].flatMap(input => [...(input.files || [])].map(file => file.name));
    warnings = [...(snapshot.warnings || []), ...(files.length ? ['ไฟล์ที่เลือกค้าง: ' + files.join(', ') + ' — อาจต้องเลือกใหม่'] : [])];
    sessionStorage.setItem(snapshotKey, JSON.stringify({version:data.release.version, snapshot}));
    for (const [key, value] of Object.entries(snapshot.storage)) {
      localStorage.setItem(key, value);
      if (localStorage.getItem(key) !== value) throw new Error('เก็บร่างไม่สำเร็จ');
    }
  }
  async function syncTab(data) {
    const hook = window.afcUpdateDraft;
    const busy = pendingRequests > 0 || !!hook?.busy?.();
    if (data.state === 'preparing' && data.preparation) {
      freeze(true);
      if (prepared !== data.preparation && !busy) {
        try {capture(data); prepared = data.preparation; saved = true;}
        catch (error) {saved = false; warnings = ['เก็บร่างไม่สำเร็จ: ' + error.message];}
      }
    } else if (data.state !== 'installing') {
      if (frozen) freeze(false);
      prepared = ''; saved = false; warnings = [];
      const raw = sessionStorage.getItem(snapshotKey);
      if (raw) {
        const record = JSON.parse(raw);
        if (record.version === data.current_version && hook?.ready()) {
          hook.restore(record.snapshot);
          sessionStorage.removeItem(snapshotKey);
        } else if (record.version !== data.current_version) {
          sessionStorage.removeItem(snapshotKey);
        }
      }
    } else {
      freeze(true);
    }
    if (hook) return api('/tabs', {id:tabId,page:location.pathname,prepared,saved,busy,warnings});
    return data;
  }
  async function api(suffix = '', body) {
    const response = await fetch('/api/local/update' + suffix, {
      credentials: 'same-origin', method: body === undefined ? 'GET' : 'POST',
      headers: body === undefined ? {} : {'Content-Type': 'application/json'},
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'อัปเดตไม่สำเร็จ กรุณาลองใหม่');
    return data;
  }
  function element(tag, text, parent) {
    const node = document.createElement(tag);
    if (text) node.textContent = text;
    if (parent) parent.appendChild(node);
    return node;
  }
  function paint(data) {
    status = data;
    version.textContent = 'รุ่นปัจจุบัน ' + data.current_version + (data.release ? ' → รุ่นใหม่ ' + data.release.version : '');
    notes.textContent = data.release?.notes || 'ไม่มีรายละเอียดเวอร์ชันใหม่';
    message.textContent = data.message || '';
    lastAttempt.textContent = data.last_attempt ? 'อัปเดตครั้งก่อน (' + data.last_attempt.version + '): ' + data.last_attempt.message : '';
    staleButton.hidden = !data.stale_tabs?.length;
    staleButton.disabled = ['preparing','installing'].includes(data.state);
    updateButton.disabled = !data.release || data.checking || installing || ['downloading','preparing','installing'].includes(data.state);
    if (data.state === 'downloading') message.textContent += ' ' + Math.round((data.downloaded || 0) / 1024) + ' / ' + Math.round((data.total || 0) / 1024) + ' KB';
  }
  function build() {
    const style = element('style');
    style.textContent = '#afc-update-open{position:fixed;bottom:14px;right:18px;z-index:1000;padding:10px 16px;background:#354bcc;color:white;border:1px solid #6578eb;border-radius:8px;cursor:pointer}#afc-update-dialog{color:#eef0fa;background:#1b2231;border:1px solid #6b789a;border-radius:12px;padding:24px;width:min(580px,85vw);max-height:80vh;overflow:auto}#afc-update-dialog::backdrop{background:#0009}#afc-update-dialog pre{white-space:pre-wrap;font:inherit;max-height:40vh;overflow:auto}#afc-update-dialog button{padding:9px 14px;margin:6px 6px 0 0;cursor:pointer}';
    document.head.appendChild(style);
    openButton = element('button', 'อัปเดตโปรแกรม', document.body);
    openButton.id = 'afc-update-open';
    dialog = element('dialog', '', document.body);
    dialog.id = 'afc-update-dialog';
    dialog.setAttribute('aria-label', 'อัปเดต All for Cabal');
    element('h2', 'อัปเดต All for Cabal', dialog);
    version = element('p', '', dialog);
    notes = element('pre', '', dialog);
    message = element('p', '', dialog);
    lastAttempt = element('p', '', dialog);
    message.setAttribute('role', 'status');
    updateButton = element('button', 'อัปเดต', dialog);
    updateButton.disabled = true;
    updateButton.onclick = async () => {
      const intent = ++installIntent;
      updateButton.disabled = true;
      try {
        let data = await api('/download', {});
        paint(data);
        if (data.state === 'ready' && intent === installIntent) {
          data = await api('/prepare', {});
          if (intent !== installIntent) {paint(await api('/cancel', {})); return;}
          requestedHere = data.preparation;
          paint(data);
        }
      } catch (error) {message.textContent = error.message; updateButton.disabled = false;}
    };
    const check = element('button', 'ตรวจอัปเดต', dialog);
    check.onclick = async () => {
      check.disabled = true;
      try { paint(await api('/check', {})); } catch (error) { message.textContent = error.message; }
      finally { check.disabled = false; }
    };
    const close = element('button', 'ไว้ก่อน', dialog);
    staleButton = element('button', 'จัดการแท็บที่ไม่ตอบสนอง', dialog);
    staleButton.hidden = true;
    staleButton.onclick = async () => {
      const tabs = status.stale_tabs || [];
      if (!tabs.length || !confirm('แท็บไม่ตอบสนอง: ' + tabs.map(tab => tab.page).join(', ') +
          '\nกรุณากลับไปบันทึกงานและปิดแท็บเหล่านี้ก่อน หากยังเปิดอยู่ห้ามนำออก\nยืนยันว่าปิดแท็บเหล่านี้แล้วและนำออกจากรายการรออัปเดต?')) return;
      try {paint(await api('/forget-tabs', {ids:tabs.map(tab => tab.id),confirmed_closed:true}));}
      catch (error) {message.textContent = error.message;}
    };
    close.onclick = async () => {
      if (status?.state === 'installing' || installing) return;
      installIntent++; requestedHere = '';
      if (status?.state === 'preparing') {paint(await api('/cancel', {})); freeze(false);}
      dialog.close();
    };
    dialog.addEventListener('cancel', event => {
      event.preventDefault(); close.click();
    });
    openButton.onclick = () => dialog.showModal();
  }
  async function refresh() {
    try {
      let data = await api();
      if (!data.supported) return;
      if (pageVersion && pageVersion !== data.current_version) {location.reload(); return;}
      pageVersion = data.current_version;
      if (!dialog) build();
      data = await syncTab(data);
      if (data.state !== 'installing') installing = false;
      paint(data);
      if (data.state === 'preparing' && data.tabs_ready && requestedHere === data.preparation && !installing) {
        installing = true;
        const problems = [...(data.warnings || [])];
        if (data.preview_count) problems.push('มีหน้า Aztek ที่กรอกค้าง ' + data.preview_count + ' หน้า โปรแกรมจะปิดหน้าเหล่านี้โดยไม่กดบันทึกให้');
        if (problems.length && !confirm(problems.join('\n') + '\n\nยอมรับและติดตั้งอัปเดตต่อหรือไม่?')) {
          paint(await api('/cancel', {})); requestedHere = ''; installing = false; freeze(false);
        } else {
          try {
            const result = await api('/install', {preparation:requestedHere,accept_warnings:true});
            installing = result.state === 'installing';
            requestedHere = '';
            paint(result);
          }
          catch (error) {message.textContent = error.message; installing = false; requestedHere = ''; paint(await api('/cancel', {}));}
        }
      }
      if (data.release && document.visibilityState === 'visible') {
        const claim = await api('/seen', {});
        if (claim.show && !dialog.open) dialog.showModal();
      }
      setTimeout(refresh, 2000);
    } catch (error) {
      if (dialog) { message.textContent = 'เชื่อมต่อโปรแกรมไม่ได้ กำลังรอโปรแกรมกลับมา'; setTimeout(refresh, 3000); }
    }
  }
  window.addEventListener('pagehide', () => {
    if (!dialog || !window.afcUpdateDraft) return;
    fetchOriginal('/api/local/update/tabs', {method:'POST',credentials:'same-origin',keepalive:true,
      headers:{'Content-Type':'application/json'},body:JSON.stringify({id:tabId,closed:true})}).catch(() => {});
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', refresh, {once: true});
  else refresh();
})();
