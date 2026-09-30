# พัฒนา All for Cabal สลับหลายเครื่อง

ใช้ GitHub ส่ง **โค้ดและบันทึกงาน** ระหว่างเครื่อง แต่ละเครื่อง clone แยกกัน
ไม่คัดลอก `.git`, `.worktrees` หรือ `.venv` จากเครื่องเดิม

## เตรียมเครื่องใหม่ครั้งแรก

ติดตั้ง Git และ Python **3.12 x64 พร้อม tkinter** (เลือก Add Python to PATH)
จากผู้ให้บริการอย่างเป็นทางการ จากนั้นเปิด PowerShell:

```powershell
git clone https://github.com/momozxmo/all-for-cabal.git
Set-Location all-for-cabal
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_dev.ps1
```

สคริปต์สร้าง `.venv` ลง dependency สำหรับพัฒนา/ทดสอบ และดาวน์โหลด Chromium
ลง `build-cache\ms-playwright` เฉพาะโปรเจกต์ ต้องต่ออินเทอร์เน็ต
ไม่ลง package ใน Python กลาง ไม่เขียน `.env` และไม่ติดตั้ง Setup ทับโปรแกรมเดิม
รันซ้ำได้เมื่อ dependency เปลี่ยนหรือการดาวน์โหลดขัดข้อง
FastAPI/Starlette ใน `requirements-dev.txt` ตรึงรุ่นที่ตรวจแล้ว เพื่อรักษาพฤติกรรม API
เมื่อต้องยกรุ่นให้ทำเป็นงานแยกพร้อมตรวจชุดทดสอบก่อน

ถ้า `python` ไม่ใช่ 3.12 ให้ระบุ path ของ Python 3.12 ที่ติดตั้งจริง:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_dev.ps1 -PythonExecutable 'C:\path\to\python.exe'
```

เปิดโฟลเดอร์ `all-for-cabal` ใน Codex แล้วบอกให้อ่าน `docs/HANDOFF.md` ก่อนทำงานต่อ
สกิลส่วนตัวและ plugin ของ Codex ต้องติดตั้งบนเครื่องใหม่แยกต่างหาก ไม่ได้มากับ Git
ก่อน commit ครั้งแรกให้ตั้ง `git config user.name` และ `git config user.email`
ของตัวเองใน repo นี้ ([ชื่อ](https://docs.github.com/en/get-started/getting-started-with-git/setting-your-username-in-git),
[อีเมล/noreply](https://docs.github.com/en/account-and-profile/how-tos/email-preferences/setting-your-commit-email-address))
การ push ต้องล็อกอิน GitHub บนเครื่องใหม่ด้วย ไม่คัดลอก token/ไฟล์ credential มาลง repo

## เปิดเว็บจากโค้ด

บันทึกร่างและรอให้งาน Aztek จบก่อนปิดโปรแกรม All for Cabal ที่ติดตั้งไว้
จากนั้นใช้:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_dev.ps1
```

ใช้ Local launcher เดิม เปิด `http://127.0.0.1:8000` โดยไม่มีหน้า login ของ All for Cabal
ถ้าพอร์ต 8000 ถูกใช้อยู่ สคริปต์หยุดและให้ปิดโปรแกรมเดิมเอง ไม่ฆ่า process
ข้อมูลสำหรับพัฒนาอยู่ใน `.local-runtime\developer-appdata\AllForCabalWeb`
แยกจาก `%LOCALAPPDATA%\AllForCabalWeb` ของโปรแกรมที่ติดตั้งไว้
ต้องเชื่อม Aztek ใหม่สำหรับ environment นี้ และต่อ VPN ถ้า Aztek ต้องใช้
แก้โค้ดแล้วปิด/เปิด launcher ใหม่เพื่อโหลดโค้ดล่าสุด
การอัปเดตผ่าน Setup ใช้กับโปรแกรมที่ติดตั้งไว้ ส่วนโค้ดพัฒนาใช้ `git pull`

ทดสอบจากโฟลเดอร์โปรเจกต์:

```powershell
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path (Get-Location) 'build-cache\ms-playwright'
.\.venv\Scripts\python.exe -X utf8 -B -m pytest -q tests --basetemp=build-cache\pytest-dev -p no:cacheprovider
```

## ก่อนออกจากเครื่องเดิม

ทำทีละเครื่อง เพื่อหลีกเลี่ยงแก้ไฟล์เดียวกันพร้อมกัน:

1. ตรวจ `git status --short --branch` และ `git diff` ก่อน commit
2. อัปเดต `docs/HANDOFF.md`: งานที่ทำแล้ว งานค้าง ผลตรวจ และสิ่งที่ต้องตัดสินใจ
3. เมื่ออนุมัติ commit/push แล้ว ให้ stage เฉพาะไฟล์ของงาน ไม่ใช้ `git add .`
4. push ไป repo **โค้ด** `momozxmo/all-for-cabal` และตรวจว่าสำเร็จก่อนเปลี่ยนเครื่อง

ตัวอย่างสำหรับ fresh clone ที่ทำงานอยู่บน `main`:

```powershell
git add -- path/to/changed-file docs/HANDOFF.md
git commit -m "describe the work"
git push origin main
```

เปลี่ยน path และข้อความให้ตรงงานจริง ถ้าอยู่ branch อื่นให้ตรวจวิธีส่งงานก่อน push
งานยังไม่เสร็จต้องระบุใน handoff ชัดเจน; checkpoint โค้ดไม่เท่ากับปล่อย Setup

## เริ่มทำต่อบนอีกเครื่อง

```powershell
git status --short --branch
git pull --ff-only origin main
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\setup_dev.ps1
```

คำสั่งนี้สำหรับ checkout บน `main` ถ้ามีไฟล์แก้ค้างหรืออยู่ branch อื่น ให้จัดการงานนั้นก่อน
ถ้า pull ไม่สำเร็จให้ตรวจเหตุผล ไม่ force/reset เพื่อล้างงาน แล้วให้ Codex อ่าน handoff

## ข้อมูลที่ไม่ส่งผ่าน Git

repo โค้ดเป็น **public**: เก็บ `.env`, DB, secrets, cookies/session, Chrome profile,
ไฟล์ Excel ต้นทาง และร่าง/คิวของผู้ใช้ไว้ส่วนตัว ไม่แนบลง handoff หรือ commit
Git ไม่ซิงก์ข้อมูลโปรแกรมหรือประวัติแชท Codex ระหว่างเครื่องให้อัตโนมัติ
หากต้องย้ายข้อมูลจริง ให้ทำ backup ผ่านขั้นตอนใน [LOCAL_INSTALL.md](LOCAL_INSTALL.md)
และย้ายแบบส่วนตัวหลังปิดโปรแกรม; ห้ามคัดลอกเฉพาะ DB โดยทิ้ง key/config ที่คู่กัน

ใช้เครื่องหลักหนึ่งเครื่องสำหรับ build และ publish Setup ตามขั้นตอนเดิม
repo `momozxmo/tool-cabal-local` สำหรับ release/เอกสารติดตั้งเท่านั้น ไม่ push โค้ดพัฒนาไปที่นั่น

อ้างอิง: [Python venv](https://docs.python.org/3.12/library/venv.html),
[Git pull](https://git-scm.com/docs/git-pull),
[Playwright installation](https://playwright.dev/python/docs/intro).
