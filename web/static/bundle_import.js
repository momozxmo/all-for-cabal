/* Direct-ID Excel import only prepares the existing Bundle queue. */
(() => {
  let sheets = [], revision = 0, preview = null;
  const added = new Set();
  const fileInput = $('bundleImportFile'), sheetPicker = $('bundleImportSheet');
  const readButton = $('btnBundleImportRead'), previewButton = $('btnBundleImportPreview');
  const addButton = $('btnBundleImportAdd'), panel = $('bundleImportPreview');
  const pasteInput = $('bundlePasteText'), pasteButton = $('btnBundlePastePreview');
  const notice = (tone, title, detail, next = '') =>
    showNotice('bundleImportMsg', tone, title, detail, next);

  function clearPreview() {
    preview = null;
    panel.replaceChildren(); panel.hidden = true; addButton.disabled = true;
  }
  function reset() {
    revision++; sheets = []; added.clear(); clearPreview();
    sheetPicker.replaceChildren(); sheetPicker.disabled = true;
    readButton.disabled = false; previewButton.disabled = true;
    pasteButton.disabled = false;
    clearNotice('bundleImportMsg');
  }
  fileInput.addEventListener('change', reset);
  pasteInput.addEventListener('input', reset);
  sheetPicker.addEventListener('change', () => {
    clearPreview(); clearNotice('bundleImportMsg');
  });
  $('game').addEventListener('change', clearPreview);

  function loadSheets(result) {
    sheets = result.sheets;
    for (const [index, sheet] of sheets.entries()) {
      const option = document.createElement('option');
      option.value = String(index); option.textContent = sheet.name;
      sheetPicker.append(option);
    }
    sheetPicker.disabled = previewButton.disabled = !sheets.length;
  }

  pasteButton.addEventListener('click', async () => {
    reset();
    if (!pasteInput.value.trim()) { notice('error', 'ยังไม่มีข้อมูล', 'ก็อปเซลล์จาก Excel แล้ววางก่อน'); return; }
    const token = revision;
    pasteButton.disabled = true;
    try {
      const response = await apiFetch('/api/bundles/import-text', {method:'POST',
        headers:{'Content-Type':'application/json'}, body:JSON.stringify({text:pasteInput.value})});
      const result = await response.json();
      if (token !== revision) return;
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'ข้อมูลใหญ่เกินไปหรือรูปแบบไม่ถูกต้อง');
      loadSheets(result); previewButton.click();
    } catch (error) {
      if (token === revision) notice('error', 'อ่านข้อมูลไม่สำเร็จ', error.message);
    } finally {
      if (token === revision) pasteButton.disabled = false;
    }
  });

  readButton.addEventListener('click', async () => {
    reset();
    const file = fileInput.files[0];
    if (!file || !file.name.toLowerCase().endsWith('.xlsx')) {
      notice('error', 'ยังอ่านไฟล์ไม่ได้', 'กรุณาเลือกไฟล์ Excel .xlsx จาก Template Bundle'); return;
    }
    if (file.size > 32 * 1024 * 1024) {
      notice('error', 'ไฟล์ใหญ่เกินกำหนด', 'กรุณาแบ่งไฟล์ให้เล็กกว่า 32 MB'); return;
    }
    const token = revision;
    readButton.disabled = true;
    notice('info', 'กำลังอ่านไฟล์', file.name);
    try {
      const body = new FormData(); body.append('file', file);
      const response = await apiFetch('/api/bundles/import', {method: 'POST', body});
      const result = await response.json();
      if (token !== revision) return;
      if (!response.ok) throw new Error(typeof result.detail === 'string' ? result.detail : 'อ่านไฟล์ไม่สำเร็จ');
      loadSheets(result);
      notice('info', 'อ่านไฟล์แล้ว', `พบ ${sheets.length} Sheet ที่ไม่ถูกซ่อน`, 'เลือก Sheet แล้วกดพรีวิวข้อมูลก่อนเพิ่มเข้าคิว');
    } catch (error) {
      if (token === revision) notice('error', 'อ่านไฟล์ไม่สำเร็จ', error.message, 'ตรวจไฟล์แล้วกดอ่านไฟล์อีกครั้ง');
    } finally {
      if (token === revision) readButton.disabled = false;
    }
  });

  previewButton.addEventListener('click', () => {
    clearPreview();
    const index = Number(sheetPicker.value), sheet = sheets[index];
    if (!sheet) return;
    if (added.has(index)) {
      notice('info', 'Sheet นี้เพิ่มเข้าคิวแล้ว', 'เลือก Sheet อื่น หรือเลือกไฟล์ใหม่'); return;
    }
    if (sheet.errors.length) {
      const details = sheet.errors.map(e => `แถว ${e.row}: ${e.message}`).join('\n');
      notice('error', 'ยังเพิ่มเข้าคิวไม่ได้', details, 'แก้แถวที่แจ้งแล้วพรีวิวข้อความหรืออ่านไฟล์ใหม่ (แสดงสูงสุด 100 ข้อผิดพลาด)');
      return;
    }
    if (!sheet.bundles.length) {
      notice('info', 'Sheet นี้ไม่มีรายการ', 'กรอกข้อมูลใต้หัวตาราง หรือเลือก Sheet อื่น'); return;
    }
    const game = $('game').value;
    if (!game) { notice('error', 'ยังไม่ได้เลือกเกม', 'เลือกเกม / เซิร์ฟก่อนพรีวิว'); return; }
    // The existing creation/handoff flow correlates results by bundle name.
    // Resolve collisions visibly here, never rename after the user has reviewed.
    const taken = new Set(state.queue.map(bundle => bundle.name));
    const bundles = sheet.bundles.map(bundle => {
      let name = bundle.name, sequence = 2;
      while (taken.has(name)) {
        const suffix = ` (${sequence++})`;
        name = bundle.name.slice(0, 200 - suffix.length) + suffix;
      }
      taken.add(name);
      return {...bundle, name};
    });
    const table = document.createElement('table');
    const head = table.createTHead().insertRow();
    for (const title of ['บันเดิล', 'ประเภท', 'แถวต้นฉบับ', 'Item ID / Currency', 'ชื่อไอเทม (จากไฟล์)', 'จำนวน', 'Rarity', 'เรท %']) {
      const th = document.createElement('th'); th.textContent = title; head.append(th);
    }
    const body = table.createTBody();
    let count = 0;
    for (const bundle of bundles) {
      for (const item of [...bundle.items, ...bundle.rewards]) {
        const row = body.insertRow(); count++;
        for (const value of [bundle.name, bundle.type, item.source_row, item.id || `${item.type}: ${item.value}`, item.name || '—', item.qty, item.tier, item.rate || '—']) {
          row.insertCell().textContent = String(value);
        }
      }
    }
    panel.append(table); panel.hidden = false;
    preview = {index, game, bundles}; addButton.disabled = false;
    const renamed = bundles.some((bundle, i) => bundle.name !== sheet.bundles[i].name);
    notice('info', `พรีวิว ${sheet.name}`, `${game} · ${bundles.length} บันเดิล · ${count} แถวไอเทม`,
      renamed ? 'ชื่อซ้ำกับคิวเดิม: เติมเลขท้ายชื่อแล้วตามพรีวิว กรุณาตรวจชื่อก่อนเพิ่มเข้าคิว' : 'ตรวจ Item ID และเกมให้ตรงกัน แล้วกดเพิ่มเข้าคิว');
  });

  addButton.addEventListener('click', () => {
    if (!preview || added.has(preview.index)) return;
    if ($('game').value !== preview.game) {
      clearPreview(); notice('error', 'เกมเปลี่ยนแล้ว', 'กรุณาพรีวิวใหม่ก่อนเพิ่มเข้าคิว'); return;
    }
    const index = preview.index, sheet = sheets[index];
    if (preview.bundles.some(bundle => state.queue.some(existing => existing.name === bundle.name))) {
      clearPreview(); notice('error', 'ชื่อในคิวเปลี่ยนแล้ว', 'กรุณาพรีวิวใหม่เพื่อจัดชื่อไม่ให้ซ้ำ'); return;
    }
    const incoming = preview.bundles.map(bundle => ({...bundle, key: nextKey(),
      items: bundle.items.map(item => ({...item})), rewards: bundle.rewards.map(reward => ({...reward}))}));
    const queue = [...state.queue, ...incoming];
    try {
      // Persist first: a full browser store must not produce a false success.
      localStorage.setItem(QUEUE_KEY, JSON.stringify(queue));
    } catch (error) {
      notice('error', 'ยังเพิ่มเข้าคิวไม่ได้', 'พื้นที่บันทึกในเบราว์เซอร์ไม่พอหรือถูกปิดกั้น', 'คิวเดิมยังอยู่ กรุณาตรวจพื้นที่แล้วลองอีกครั้ง'); return;
    }
    state.queue = queue; added.add(index); clearPreview();
    select(incoming[0].key);
    notice('success', 'เพิ่มเข้าคิวแล้ว', `${sheet.name} · ${incoming.length} บันเดิล`, 'แก้ไขจำนวน / Tier ในคิวได้ ยังไม่ได้สร้างบน Aztek');
  });
})();
