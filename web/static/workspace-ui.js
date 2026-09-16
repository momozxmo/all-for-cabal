/* Presentation only: never fetch, change a queue, or decide whether a job runs. */
(() => {
  'use strict';
  const main = document.querySelector('main');
  if (!main) return;
  main.id = 'main-content';
  main.tabIndex = -1;
  const skip = document.createElement('a');
  skip.className = 'skip-link'; skip.href = '#main-content';
  skip.textContent = 'ข้ามไปพื้นที่ทำงาน';
  document.body.prepend(skip);
  const tools = {'/':'Item Finder','/bundles':'Bundle','/itemcodes':'Item Code',
    '/events':'Event','/products':'Product'};
  if (Object.hasOwn(tools, location.pathname)) {
    document.querySelectorAll('[data-account-link]').forEach(link => {
      link.href = '/account?from=' + encodeURIComponent(location.pathname);
    });
  } else if (location.pathname === '/account') {
    const from = new URLSearchParams(location.search).get('from');
    const back = document.querySelector('.topbar > a');
    if (back && Object.hasOwn(tools, from)) {
      back.href = from; back.textContent = '← กลับไป ' + tools[from];
    }
  }

  const nav = document.querySelector('.spine');
  if (nav) {
    nav.setAttribute('aria-label', 'เครื่องมือ All for Cabal');
    nav.querySelectorAll('.k').forEach(node => node.setAttribute('aria-hidden', 'true'));
    nav.querySelector('.active')?.setAttribute('aria-current', 'page');
    const guide = document.createElement('section');
    guide.className = 'work-guide'; guide.setAttribute('aria-label', 'แนวทางทำงาน');
    const title = document.createElement('strong');
    title.textContent = nav.querySelector('.active b')?.textContent || 'พื้นที่ทำงาน';
    const hint = document.createElement('p');
    hint.textContent = location.pathname === '/'
      ? 'เลือกชนิดแผนและเกม → นำเข้า → ค้นหาไอเทม → เลือกเครื่องมือปลายทาง'
      : 'นำเข้าหรือเพิ่มรายการ → ตรวจข้อมูลในคิว → เปิดเว็บดูก่อน → สร้างและส่งต่อ';
    guide.append(title, hint); nav.after(guide);
  }

  const pick = document.querySelector('#queuePick, #productQueue');
  if (pick) {
    const status = document.createElement('div'); status.className = 'work-status';
    status.setAttribute('role', 'status');
    pick.closest('.card-body').append(status);
    const update = () => {
      const selected = pick.selectedOptions[0]?.textContent || '';
      const text = pick.options.length
        ? `${pick.options.length} รายการในคิว · ที่เลือก: ${selected} · จำนวนในคิวยังไม่ใช่จำนวนที่ผ่านการตรวจ`
        : 'คิวว่าง · เริ่มจากนำเข้าข้อมูลหรือเพิ่มรายการใหม่';
      if (status.textContent !== text) status.textContent = text;
    };
    pick.addEventListener('change', update);
    new MutationObserver(update).observe(pick, {childList:true,subtree:true,characterData:true});
    update();
    const preview = document.getElementById('btnPreview');
    if (preview) {
      const card = preview.closest('.card'); card.id = 'run-actions';
      const jump = document.createElement('a'); jump.href = '#run-actions';
      jump.className = 'work-jump'; jump.textContent = 'ไปส่วนตรวจและสร้าง ↓';
      pick.closest('.card-body').append(jump);
      const hint = document.createElement('p'); hint.className = 'run-guide';
      hint.textContent = 'ตรวจเกม รายการ และช่องบังคับก่อนสร้าง · “เปิดหน้าเว็บดูก่อน” ยังไม่บันทึกจริง · ปุ่มสร้างทั้งหมดใช้ขอบเขตคิวตามเดิม';
      preview.closest('.result-actions').before(hint);
    }
  }

  const log = document.getElementById('log');
  if (log) {
    const card = log.closest('.card');
    const details = document.createElement('details'); details.className = 'log-details';
    const summary = document.createElement('summary'); summary.textContent = 'บันทึกการทำงาน (Log)';
    details.append(summary, ...card.childNodes); card.append(details);
    const update = () => {
      summary.textContent = `บันทึกการทำงาน (Log) · ${log.children.length} รายการ`;
      if (log.querySelector('.ERROR,.WARNING')) details.open = true;
    };
    new MutationObserver(update).observe(log, {childList:true}); update();
  }

  document.querySelectorAll('.table-wrap,#bundleResults,#productResults').forEach(box => {
    box.tabIndex = 0;
    box.setAttribute('role', 'region');
    box.setAttribute('aria-label', 'ตารางข้อมูล เลื่อนแนวนอนเพื่อดูคอลัมน์เพิ่มเติม');
  });
  const results = document.getElementById('bundleResults');
  if (results) {
    const note = document.createElement('p'); note.className = 'result-context';
    note.textContent = 'ผลการทำงานที่เก็บไว้ในเบราว์เซอร์ · อาจเป็นคนละรอบกับคิวปัจจุบัน ตรวจชื่อและเลข Bundle ก่อนส่งต่อ';
    results.before(note);
    const update = () => { note.hidden = !results.children.length; };
    new MutationObserver(update).observe(results, {childList:true}); update();
  }

  document.querySelectorAll('[role=tablist]').forEach(list => {
    const tabs = [...list.querySelectorAll('button[data-tab]')];
    if (!tabs.length) return;
    const update = () => tabs.forEach(tab => {
      const active = tab.classList.contains('active');
      tab.setAttribute('role','tab'); tab.setAttribute('aria-selected', String(active));
      tab.tabIndex = active ? 0 : -1;
    });
    tabs.forEach((tab, index) => tab.addEventListener('keydown', event => {
      const offsets = {ArrowRight:1,ArrowLeft:-1,Home:-index,End:tabs.length-1-index};
      if (!(event.key in offsets)) return;
      event.preventDefault();
      const next = tabs[(index + offsets[event.key] + tabs.length) % tabs.length];
      next.click(); next.focus();
    }));
    new MutationObserver(update).observe(list, {subtree:true,attributes:true,attributeFilter:['class']});
    update();
  });
})();
