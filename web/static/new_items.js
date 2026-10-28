/* New Item workflow. Remote creation requires a fresh explicit selected scope. */
(() => {
  'use strict';
  let drafts = [], history = [], pending = null, confirmation = null;
  let existingDecision = null, existingFocus = null;
  let createDecision = null, createBusy = false, createUncertain = false;
  const editors = new Map();
  const fields = ['name','kind','option','duration','item_type','tradeable','description'];
  const createSupported = game => ['CabalPC TH','CabalPC SEA','CabalM TH','CabalM SEA'].includes(game);
  const createReadyType = record => createSupported(record.frozen?.game)&&
    (record.frozen?.submitted_values?.item_type==='GENERAL'||
      (record.frozen.game.startsWith('CabalPC ')&&record.frozen.submitted_values?.item_type==='CABALPC_PREMIUM'));
  const names = {name:'Name',kind:'Kind',option:'Option',duration:'Duration',item_type:'Type',tradeable:'Tradeable',description:'Description'};
  const states = {draft:'ร่าง',confirmed:'ยืนยันร่างแล้ว',submitting:'กำลังบันทึก',saved:'บันทึกแล้ว',unconfirmed:'ยังยืนยันการสร้างไม่ได้',skipped:'ข้ามแล้ว'};
  const outcomes = {passed:'ตรวจผ่านครบ',mismatch:'ข้อมูลไม่ตรง',failed:'ตรวจไม่สำเร็จ'};
  const images = {present_not_content_verified:'พบรูป แต่ยังไม่ได้ยืนยันว่าเนื้อภาพตรงกัน',missing:'ไม่พบรูปที่ต้องมี',unreadable:'ยังอ่านสถานะรูปไม่ได้',not_requested:'ไม่ได้ร้องขอการตรวจรูป'};
  const node = (tag, text, cls) => { const e=document.createElement(tag); if(text!==undefined)e.textContent=String(text); if(cls)e.className=cls; return e; };
  const printable = value => value === null || value === undefined ? 'ไม่มีข้อมูล' : String(value);
  async function api(path, options={}) {
    const response=await apiFetch('/api/new-items'+path,options);
    const data=await response.json();
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'ตรวจข้อมูลที่เลือกแล้วลองใหม่');
    return data;
  }
  const post = (path, body) => api(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  async function act(button, work) {
    button.disabled=true;
    try { clearNotice('newNotice'); await work(); }
    catch(error) { showNotice('newNotice','error','ทำรายการไม่สำเร็จ',error.message,'ตรวจข้อมูลแล้วลองใหม่ ร่างเดิมยังอยู่'); }
    finally { button.disabled=false; selectionChanged(); }
  }
  function selectionChanged() {
    $('confirmDrafts').disabled=!$('draftRows').querySelector('input[data-pick]:checked');
    $('handoffBtn').disabled=!$('historyRows').querySelector('input[data-occurrence]:checked');
    const supported=createSupported($('newGame').value);
    const problem=history.some(r=>r.frozen?.game===$('newGame').value&&hasProblem(r)&&!problemAcknowledged(r));
    const selected=$('historyRows').querySelector('input[data-create]:checked');
    $('createSelected').textContent=supported?'สร้าง Item ที่เลือก':'สร้าง Item (ยังไม่พร้อม)';
    $('createSelected').disabled=createBusy||createUncertain||!supported||problem||!selected;
    $('createReason').textContent=!supported?'เกมนี้ยังไม่เปิดสร้างใหม่ ใช้การเตรียมร่างหรือเลือก Item เดิมได้':
      createUncertain?'คำขออาจถูกบันทึกแล้ว โหลดประวัติใหม่และตรวจสถานะก่อนเลือกชุดใหม่ — อย่าสร้างซ้ำ':
      problem?'รับทราบ/ข้ามรายการที่มีปัญหาก่อน แล้วเลือกเฉพาะรายการถัดไปเอง':
      'เลือกสร้างใหม่เฉพาะร่างที่ยืนยันแล้ว ระบบจะให้ตรวจเกม จำนวน และค่าก่อนส่งจริง';
  }
  const hasProblem = r => r.result?.creation?.state==='unconfirmed'||['mismatch','failed'].includes(r.result?.recheck?.outcome)||
    (r.result?.creation?.state==='saved'&&(!r.result.recheck||r.result.recheck.incomplete!==false));
  function problemAcknowledged(record) {
    const entries=record.history||[],creation=record.result?.creation||{},checked=record.result?.recheck||{};
    const lastCheck=entries.map(e=>!!e.recheck).lastIndexOf(true);
    return entries.some((entry,index)=>index>lastCheck&&entry.event==='operator_acknowledgement'&&
      entry.creation_state===creation.state&&entry.recheck_outcome===(checked.outcome??null));
  }
  function labeledBox(label, checked=false) {
    const wrap=node('label',undefined,'draft-confirm'), box=node('input');box.type='checkbox';box.checked=checked;
    wrap.append(box,document.createTextNode(label));return [wrap,box];
  }
  function renderDrafts() {
    $('draftRows').replaceChildren();
    const visible=drafts.filter(d=>d.game===$('newGame').value);
    $('draftCount').textContent=`${visible.length} รายการ`;$('draftEmpty').hidden=visible.length>0;
    for(const draft of visible) {
      const initialValues=Object.fromEntries(fields.map(f=>[f,draft.values[f]===null||draft.values[f]===undefined?'':String(draft.values[f])]));
      let editor=editors.get(draft.draft_id);
      if(!editor||editor.revision!==draft.revision||draft.state!=='draft')editor={revision:draft.revision,values:{...initialValues},confirmed:[...draft.confirmed_fields]};
      editors.set(draft.draft_id,editor);
      const row=node('tr'), pickCell=node('td'), pick=node('input');pick.type='checkbox';pick.dataset.pick=draft.draft_id;
      pick.setAttribute('aria-label','เลือกร่าง');pick.disabled=draft.state!=='draft'||!draft.ready;
      pick.onchange=selectionChanged;pickCell.append(pick);row.append(pickCell);
      const controls={}, defaults={};
      for(const field of fields) {
        const cell=node('td');let input;
        if(field==='item_type'||field==='tradeable') {
          input=node('select');
          const values=field==='tradeable'?['false','true']:draft.game.startsWith('CabalPC ')?['GENERAL','CABALPC_PREMIUM']:['GENERAL'];
          if(field==='item_type'&&draft.values[field]&&!values.includes(draft.values[field]))values.push(draft.values[field]);
          for(const value of values) { const option=node('option',field==='tradeable'?(value==='true'?'แลกเปลี่ยนได้':'ผูกมัด'):value);option.value=value;input.append(option); }
        } else { input=node('input');input.type='text';if(['kind','option','duration'].includes(field))input.inputMode='numeric'; }
        input.dataset.key=field;input.setAttribute('aria-label',names[field]);
        input.value=editor.values[field];input.disabled=draft.state!=='draft';
        input.oninput=input.onchange=()=>{editor.values[field]=input.value;};
        controls[field]=input;cell.append(input);
        if(['item_type','tradeable'].includes(field)&&draft.occurrences.some(o=>o.original[field]===null)) {
          const [label,box]=labeledBox('ยืนยันค่า '+names[field],editor.confirmed.includes(field));
          box.onchange=()=>{editor.confirmed=editor.confirmed.filter(f=>f!==field);if(box.checked)editor.confirmed.push(field);};
          box.disabled=draft.state!=='draft';defaults[field]=box;cell.append(label);
        }
        row.append(cell);
      }
      const isDirty=()=>fields.some(f=>controls[f].value!==initialValues[f])||JSON.stringify([...editor.confirmed].sort())!==JSON.stringify([...draft.confirmed_fields].sort());
      editor.isDirty=isDirty;
      const media=node('td',undefined,'draft-media');
      media.append(node('p',draft.image?'แนบรูปแล้ว · ยังไม่ส่ง Aztek':'ไม่มีรูป · ไม่บังคับแนบ',draft.image?'ok':'hint'));
      if(draft.image){
        const preview=node('img');preview.alt='รูปที่แนบในร่าง';preview.src='/api/new-items/drafts/'+encodeURIComponent(draft.draft_id)+'/image';preview.width=64;preview.height=64;media.append(preview);
        media.append(node('p',`${draft.image.name} · ${draft.image.size} bytes`,'hint'));
      }
      if(draft.state==='draft'){
        const label=node('label','รูปสำหรับร่าง'), file=node('input');file.type='file';file.accept='image/png,image/jpeg,image/webp';label.append(file);media.append(label);
        const upload=node('button','แนบรูปในเครื่อง');media.append(upload);
        upload.onclick=()=>act(upload,async()=>{
          if(isDirty())throw new Error('บันทึกร่างก่อนแนบรูป เพื่อเก็บค่าที่แก้ไว้ แล้วเลือกไฟล์ใหม่');
          const image=file.files[0];if(!image)throw new Error('กรุณาเลือกไฟล์รูป');if(image.size>5000000)throw new Error('รูปต้องไม่เกิน 5 MB');
          const body=new FormData();body.append('revision',String(draft.revision));body.append('file',image);
          await api('/drafts/'+encodeURIComponent(draft.draft_id)+'/image',{method:'POST',body});await load();
        });
        if(draft.image){
          const remove=node('button','นำรูปออกจากร่าง');media.append(remove);
          remove.onclick=()=>act(remove,async()=>{
            if(isDirty())throw new Error('บันทึกร่างก่อนนำรูปออก เพื่อเก็บค่าที่แก้ไว้');
            await api('/drafts/'+encodeURIComponent(draft.draft_id)+'/image?revision='+draft.revision,{method:'DELETE'});await load();
          });
        }
      }
      row.append(media);
      const source=node('td'), state=node('p',draft.state==='draft'?(draft.ready?'พร้อมยืนยัน':'ต้องตรวจ/เติม: '+draft.errors.join(', ')):(states[draft.state]||draft.state));source.append(state);
      const details=node('details');details.append(node('summary',`${draft.occurrences.length} แถวต้นทาง`));
      for(const o of draft.occurrences)details.append(node('p',`${o.filename} · ${o.sheet}:${o.row??'?'} · จำนวน ${o.amount??'ไม่ระบุ'}`));
      source.append(details);row.append(source);
      const action=node('td'), save=node('button','บันทึกร่าง');save.disabled=draft.state!=='draft';action.append(save);row.append(action);
      save.onclick=()=>act(save,async()=>{
        const values=Object.fromEntries(fields.map(f=>[f,f==='tradeable'?controls[f].value==='true':controls[f].value]));
        const confirmed_fields=[...new Set([...draft.confirmed_fields.filter(f=>!defaults[f]),...Object.keys(defaults).filter(f=>defaults[f].checked)])];
        await api('/drafts/'+encodeURIComponent(draft.draft_id),{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({revision:draft.revision,values,confirmed_fields})});
        await load();showNotice('newNotice','success','บันทึกร่างแล้ว','ต้นฉบับและแถวอ้างอิงยังอยู่ครบ');
      });
      $('draftRows').append(row);
    }
    selectionChanged();
  }
  function comparisonDetails(checked, label='ดูต้นฉบับ / ค่าร่าง / ค่าที่อ่านได้') {
    const details=node('details');details.append(node('summary',label));
    const occurrences=Array.isArray(checked.per_occurrence)?checked.per_occurrence:[];
    if(!occurrences.length)details.append(node('p','ไม่มีข้อมูลเปรียบเทียบที่เก็บไว้สำหรับรอบนี้','hint'));
    for(const occurrence of occurrences) {
      const wrap=node('div',undefined,'table-wrap'), table=node('table',undefined,'detail-table'), head=node('tr');
      for(const label of ['ช่อง','ต้นฉบับ','ค่าที่ใช้เทียบ','ค่าร่าง','ค่าที่อ่านได้','ที่มาค่าอ้างอิง'])head.append(node('th',label));table.append(head);
      for(const field of fields){const tr=node('tr');for(const value of [names[field],occurrence.original?.[field],occurrence.reference?.[field],occurrence.submitted?.[field],occurrence.actual?.[field],occurrence.provenance?.[field]])tr.append(node('td',printable(value)));table.append(tr);}
      wrap.append(table);details.append(wrap);
    }
    return details;
  }
  function renderHistory() {
    $('historyRows').replaceChildren();let count=0;
    for(const record of history.filter(r=>r.frozen?.game===$('newGame').value)) {
      count++;const article=node('article',undefined,'history-item'), result=record.result||{}, creation=result.creation||{}, checked=result.recheck;
      article.append(node('h3',record.frozen.submitted_values.name),node('p',creation.source==='existing'?'ใช้ Item เดิม — ไม่ได้สร้างใหม่':states[creation.state||record.state]||'ยังไม่ได้สร้าง'));
      if(creation.item_id)article.append(node('p','Item ID: '+creation.item_id));
      if(creation.cohort_ids?.length>1)article.append(node('p',`กลุ่มสร้างร่วมกัน ${creation.cohort_ids.length} ร่าง — เก็บผลตรวจแยกตามต้นฉบับ`,'hint'));
      if(creation.state==='unconfirmed')article.append(node('p','อย่าสร้างซ้ำ ต้องยืนยันรายการจากหลักฐานเดิมก่อน','warning'));
      const receipt=creation.receipt;
      if(creation.state==='unconfirmed'&&receipt?.source==='matched_create_post_response'&&
          receipt.attempt_id===creation.attempt_id&&receipt.game===record.frozen.game&&
          receipt.revision===record.frozen.revision&&receipt.payload_hash===record.frozen.payload_hash&&
          /^[1-9][0-9]*$/.test(receipt.record_id||'')) {
        const recover=node('button',`กู้ Item ID ${receipt.record_id} จากคำตอบเดิมและตรวจ (ไม่สร้างใหม่)`);
        recover.onclick=()=>act(recover,async()=>{
          await post('/'+encodeURIComponent(record.id)+'/resolve',{
            game:record.frozen.game,revision:record.frozen.revision,item_id:receipt.record_id,
            expected_history_count:record.history.length});
          await loadHistory();
        });
        article.append(recover);
      }
      if(record.state==='confirmed') {
        if(createReadyType(record)) {
          const [label,box]=labeledBox('เลือกสร้างใหม่ '+record.frozen.submitted_values.name);
          box.disabled=!record.search||record.search.payload_hash!==record.frozen.payload_hash;
          label.classList.add('create-pick');box.dataset.create=record.id;box.onchange=selectionChanged;
          article.append(label);
        } else article.append(node('p','ประเภทนี้ยังไม่เปิดสร้างใหม่ — ไม่เปลี่ยนเป็น GENERAL ให้อัตโนมัติ','warning'));
        const search=node('button','ค้นหา Item เดิม');
        search.onclick=()=>act(search,async()=>{
          await post('/search',{game:record.frozen.game,selected:[{id:record.id,revision:record.frozen.revision}]});await loadHistory();
        });article.append(search);
        const snapshot=record.search;
        if(snapshot) {
          article.append(node('p','ผลค้นหาจาก Kind / Option / Duration — ยังไม่เลือก ID ให้ และยังไม่ใช่ผลตรวจ','hint'));
          if(!snapshot.candidates.length)article.append(node('p',createReadyType(record)?
            'ไม่พบ Item เดิมที่ตรงสามค่า หากต้องการสร้างใหม่ ให้เลือกและยืนยันเองด้านล่าง':
            'ไม่พบ Item เดิมที่ตรงสามค่า ร่างยังอยู่; ขั้นสร้างใหม่ของเกมนี้ยังไม่พร้อม','hint'));
          else {
            const choices=node('fieldset',undefined,'existing-candidates');choices.append(node('legend','เลือก Item เดิมที่จะอ่านตรวจ'));
            const use=node('button','ใช้ ID เดิมและตรวจข้อมูล');use.disabled=true;let selected=null;
            for(const candidate of snapshot.candidates) {
              const label=node('label'), radio=node('input');radio.type='radio';radio.name='existing-'+record.id;radio.value=candidate.item_id;
              radio.setAttribute('aria-label','เลือก Item ID '+candidate.item_id);
              radio.onchange=()=>{selected=candidate;use.disabled=false;};
              label.append(radio,node('span',`ID ${candidate.item_id} · ${candidate.name} · Kind ${candidate.kind} / Option ${candidate.option} / Duration ${candidate.duration}`));choices.append(label);
            }
            use.onclick=()=>{
              if(!selected)return;
              existingDecision={id:record.id,revision:record.frozen.revision,game:record.frozen.game,search_id:snapshot.search_id,item_id:selected.item_id};existingFocus=use;
              $('existingText').textContent=`${record.frozen.game} · Item ID ${selected.item_id} · ${selected.name}`;
              $('existingDialog').showModal();$('acceptExisting').focus();
            };
            article.append(choices,use);
          }
        }
      }
      if(checked) {
        article.append(node('p',outcomes[checked.outcome]||'ยังไม่มีผลตรวจ',checked.outcome==='passed'?'ok':'warning'));
        if(checked.incomplete)article.append(node('p','ยังตรวจไม่ครบทุกส่วน','warning'));
        if(checked.error)article.append(node('p',checked.error,'error'));
        article.append(node('p',images[checked.image_status]||'ยังไม่ได้ตรวจรูป','hint'),comparisonDetails(checked));
      } else article.append(node('p','ยังไม่มีผลตรวจ'));
      if(creation.state==='saved') {
        const retry=node('button','ตรวจซ้ำจาก Item ID เดิม');retry.onclick=()=>act(retry,async()=>{await post('/'+encodeURIComponent(record.id)+'/recheck',{});await loadHistory();});article.append(retry);
      }
      const acknowledged=problemAcknowledged(record);
      if(acknowledged)article.append(node('p','รับทราบแล้ว — ผลตรวจและสิทธิ์ส่งต่อไม่เปลี่ยน','hint'));
      if(!acknowledged&&hasProblem(record)){
        const acknowledge=node('button','รับทราบ/ข้ามรายการนี้');
        acknowledge.onclick=()=>act(acknowledge,async()=>{
          await post('/'+encodeURIComponent(record.id)+'/acknowledge',{action:'skip',expected_history_count:record.history.length});await loadHistory();
        });article.append(acknowledge);
        article.append(node('p','รับทราบไม่เปลี่ยนผลเป็นผ่าน และไม่เริ่มรายการอื่นหรือสร้างซ้ำเอง','hint'));
      }
      if(creation.state==='saved'&&checked?.outcome==='passed'&&checked.incomplete===false) {
        const picks=node('div',undefined,'occurrence-picks');
        for(const o of record.frozen.occurrences) {
          const [label,box]=labeledBox(`เลือกแถว ${o.sheet}:${o.row??'?'} — จำนวน ${o.amount??'ไม่ระบุ'}`);
          box.dataset.occurrence=o.occurrence_id;box.dataset.job=record.id;box.onchange=selectionChanged;picks.append(label);
        }
        article.append(picks);
      }
      const attempts=node('details');attempts.append(node('summary',`ประวัติ ${record.history.length} ครั้ง`));
      let checkRound=0;
      for(const attempt of record.history){
        if(attempt.recheck){
          checkRound++;const prior=attempt.recheck, entry=node('div');
          entry.append(node('h4',`รอบตรวจที่ ${checkRound} · ${outcomes[prior.outcome]||'ไม่มีผลตรวจที่ระบุไว้'}`),
            node('p','เวลา: '+printable(attempt.checked_at||attempt.recorded_at)),
            node('p',`เกม: ${printable(attempt.game||null)} · Item ID: ${printable(attempt.item_id||null)}`));
          if(prior.incomplete)entry.append(node('p','รอบนี้ยังตรวจไม่ครบทุกส่วน','warning'));
          if(prior.error)entry.append(node('p','ข้อผิดพลาดรอบนี้: '+prior.error,'error'));
          entry.append(node('p','สถานะรูป: '+(images[prior.image_status]||'ไม่มีข้อมูลสถานะรูป'),'hint'),
            comparisonDetails(prior,`ดูค่าที่เปรียบเทียบรอบที่ ${checkRound}`));
          attempts.append(entry);
        }else attempts.append(node('p',`${attempt.checked_at||attempt.recorded_at||''} · ${attempt.event==='operator_acknowledgement'?'รับทราบปัญหา (ผลเดิมไม่เปลี่ยน)':'กู้สถานะที่ค้างไว้'}`));
      }
      article.append(attempts);$('historyRows').append(article);
    }
    $('historyEmpty').hidden=count>0;selectionChanged();
  }
  async function loadHistory(){history=(await api('/history')).rows;renderHistory();}
  async function load(){drafts=(await api('/drafts')).drafts;renderDrafts();await loadHistory();}
  const picker=createSheetPickerSearch({list:$('sheetList'),input:$('sheetSearch'),count:$('sheetCount'),empty:$('sheetEmpty'),selectAllButton:$('sheetAll'),clearButton:$('sheetNone')});
  $('previewBtn').onclick=()=>act($('previewBtn'),async()=>{
    const file=$('newFile').files[0];if(!file)throw new Error('กรุณาเลือกไฟล์ Excel');
    const body=new FormData();body.append('file',file);body.append('game',$('newGame').value);body.append('mode',$('importMode').value);
    pending={...(await api('/import',{method:'POST',body})),game:$('newGame').value};$('sheetList').replaceChildren();
    for(const sheet of pending.sheets){const [label,box]=labeledBox(`${sheet.name} · ${sheet.row_count} แถว${sheet.hidden?' (ซ่อนอยู่)':''}`);label.className='sheet-row';label.dataset.sheetName=sheet.name;box.value=sheet.name;$('sheetList').append(label);}
    picker.refresh(true);$('sheetDialog').showModal();$('sheetSearch').focus();
  });
  $('applySheets').onclick=()=>act($('applySheets'),async()=>{
    const selected_sheets=[...$('sheetList').querySelectorAll('input:checked')].map(e=>e.value);
    await post('/import/apply',{pending_id:pending.pending_id,selected_sheets,game:pending.game});
    $('newGame').value=pending.game;$('sheetDialog').close();pending=null;await load();
  });
  $('cancelSheets').onclick=()=>$('sheetDialog').close();$('sheetDialog').addEventListener('close',()=>$('previewBtn').focus());
  $('confirmDrafts').onclick=()=>{
    const ids=[...$('draftRows').querySelectorAll('input[data-pick]:checked')].map(e=>e.dataset.pick);
    if(ids.some(id=>editors.get(id)?.isDirty())){
      showNotice('newNotice','warning','ยังยืนยันร่างไม่ได้','บันทึกร่างก่อนยืนยัน เพื่อเก็บค่าที่แก้ไว้','กดบันทึกร่างในแถวที่แก้แล้วเลือกใหม่');return;
    }
    confirmation={game:$('newGame').value,selected:drafts.filter(d=>ids.includes(d.draft_id)).map(d=>({id:d.draft_id,revision:d.revision}))};
    $('confirmText').textContent=`${confirmation.game} · ${confirmation.selected.length} รายการ`;$('confirmDialog').showModal();$('acceptDrafts').focus();
  };
  $('acceptDrafts').onclick=()=>act($('acceptDrafts'),async()=>{await post('/confirm',confirmation);$('confirmDialog').close();await load();});
  $('cancelDrafts').onclick=()=>$('confirmDialog').close();$('confirmDialog').addEventListener('close',()=>$('confirmDrafts').focus());
  $('acceptExisting').onclick=()=>act($('acceptExisting'),async()=>{
    if(!existingDecision)throw new Error('กรุณาเลือก ID จากผลค้นหาใหม่');
    const {id,...body}=existingDecision;
    await post('/'+encodeURIComponent(id)+'/use-existing',body);$('existingDialog').close();await load();
  });
  $('cancelExisting').onclick=()=>$('existingDialog').close();
  $('existingDialog').addEventListener('close',()=>{existingDecision=null;if(existingFocus?.isConnected)existingFocus.focus();});
  $('createSelected').onclick=()=>{
    if(createBusy||$('createSelected').disabled)return;
    const ids=[...$('historyRows').querySelectorAll('input[data-create]:checked')].map(e=>e.dataset.create);
    const chosen=history.filter(r=>ids.includes(r.id)&&r.state==='confirmed'&&r.frozen.game===$('newGame').value);
    if(!chosen.length||!createSupported($('newGame').value)||chosen.some(r=>!createReadyType(r)))return;
    createDecision={game:$('newGame').value,group_identical:true,selected:chosen.map(r=>({id:r.id,revision:r.frozen.revision,decision:'create_new',search_id:r.search?.search_id}))};
    const groups=new Map();
    for(const row of chosen){const key=row.frozen.payload_hash;if(!groups.has(key))groups.set(key,[]);groups.get(key).push(row);}
    $('createText').textContent=`${createDecision.game} · สร้าง ${groups.size} รายการ จาก ${chosen.length} ร่าง — ร่างที่มีค่าทุกช่องตรงกันจะใช้ Item ID เดียวกัน`;
    $('createSummary').replaceChildren();
    for(const rows of groups.values()){const v=rows[0].frozen.submitted_values,li=node('li',v.name);
      if(rows.length>1)li.append(node('span',`ใช้ร่วมกัน ${rows.length} ร่าง — เก็บผลตรวจแยกตามเอกสารเดิม`));
      li.append(node('span',`Kind ${v.kind} / Option ${v.option} / Duration ${v.duration}`),
        node('span',`${v.item_type} · ${v.tradeable?'แลกเปลี่ยนได้':'ผูกมัด'} · ${v.image_key?'แนบรูปจากร่าง':'ไม่แนบรูป'}`),
        node('span','คำอธิบาย: '+(v.description||'ไม่ระบุ')));$('createSummary').append(li);}
    $('createDialog').showModal();$('acceptCreate').focus();
  };
  $('acceptCreate').onclick=async()=>{
    if(createBusy||!createDecision)return;
    const decision=createDecision;createBusy=true;
    $('newControls').inert=true;$('createProgress').hidden=false;
    $('acceptCreate').disabled=true;$('cancelCreate').disabled=true;$('createDialog').setAttribute('aria-busy','true');
    let data=null,error=null,loaded=false;
    try { data=await post('/run',decision); }
    catch(problem){error=problem;createUncertain=true;}
    try { await load();loaded=true; } catch(problem){error=error||problem;createUncertain=true;}
    createBusy=false;$('newControls').inert=false;$('createProgress').hidden=true;
    $('acceptCreate').disabled=false;$('cancelCreate').disabled=false;$('createDialog').removeAttribute('aria-busy');
    for(const box of $('historyRows').querySelectorAll('input[data-create]'))box.checked=false;
    $('createDialog').close();selectionChanged();
    if(error)showNotice('newNotice','warning','ยังสรุปผลคำขอไม่ได้',
      'คำขออาจถูกบันทึกแล้ว อย่ากดสร้างซ้ำ'+(loaded?' — อ่านสถานะล่าสุดด้านล่าง':' — ยังโหลดประวัติไม่สำเร็จ'),
      'โหลดประวัติใหม่ ตรวจ Item ID และผลตรวจจากรายการเดิมก่อน');
    else showNotice('newNotice',data.remaining_ids.length?'warning':'success','อ่านผลล่าสุดแล้ว',
      data.remaining_ids.length?'หยุดชุดนี้แล้ว รายการถัดไปยังไม่ถูกสร้างและไม่ได้เลือกให้เอง':'ดูผลสร้างและผลตรวจแยกกันด้านล่าง',
      'รายการที่มีปัญหาต้องรับทราบก่อนเลือกชุดใหม่ ผลเดิมจะไม่เปลี่ยนเป็นผ่าน');
    $('newNotice').focus();
  };
  $('cancelCreate').onclick=()=>{if(!createBusy)$('createDialog').close();};
  $('createDialog').addEventListener('cancel',event=>{if(createBusy)event.preventDefault();});
  $('createDialog').addEventListener('close',()=>{createDecision=null;if(!createBusy&&!$('createSelected').disabled)$('createSelected').focus();});
  $('handoffBtn').onclick=()=>act($('handoffBtn'),async()=>{
    const boxes=[...$('historyRows').querySelectorAll('input[data-occurrence]:checked')];
    const data=await post('/handoff',{game:$('newGame').value,selected_ids:[...new Set(boxes.map(e=>e.dataset.job))],occurrence_ids:boxes.map(e=>e.dataset.occurrence)});
    // Finder's whole-workspace restore uses this established key. Its query
    // handoff is reserved for a workspace + one source-group pair.
    localStorage.setItem('afc.workspaceId',data.workspace_id);
    window.location.assign('/');
  });
  $('refreshHistory').onclick=()=>act($('refreshHistory'),async()=>{await load();createUncertain=false;selectionChanged();});
  $('newGame').onchange=()=>{renderDrafts();renderHistory();};
  const requestedGame=new URLSearchParams(location.search).get('game');
  if([...$('newGame').options].some(option=>option.value===requestedGame))$('newGame').value=requestedGame;
  load().catch(error=>showNotice('newNotice','error','โหลดร่างไม่สำเร็จ',error.message,'ลองโหลดหน้าใหม่ ข้อมูลที่บันทึกไว้ยังอยู่'));
})();
