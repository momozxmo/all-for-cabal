# พัฒนา All for Cabal Web ด้วย Docker

## ขอบเขต

Docker ชุดนี้ใช้เฉพาะเครื่องผู้พัฒนาเพื่อให้ Python, Playwright และ Chromium เป็นเวอร์ชันเดียวกันทุกครั้ง ไม่ได้แทนที่โปรแกรม Local ของทีม และไม่ใช่การ Deploy Production

ผู้ใช้งานในทีมยังดาวน์โหลดและติดตั้ง Windows Setup เหมือนเดิม

## สิ่งที่ต้องมี

- Windows 10/11 x64
- Docker Desktop ที่เปิดทำงานอยู่ใน Linux container mode
- PowerShell
- VPN บริษัทเมื่อจำเป็นต้องตรวจการเชื่อมต่อ IPA หรือ Aztek

หากเพิ่งติดตั้ง Docker หลังจากเปิด PowerShell หรือ Codex ให้ปิดแล้วเปิดโปรแกรมใหม่เพื่อรีเฟรช `PATH` สคริปต์รองรับการค้นหา Docker Desktop แบบ per-user ให้อีกทางหนึ่งด้วย

## เริ่มใช้งานครั้งแรก

จากโฟลเดอร์โปรเจกต์ รัน:

```powershell
.\scripts\docker_dev.ps1 start
```

ครั้งแรกสคริปต์จะ:

1. ตรวจว่า Docker Desktop Engine พร้อมใช้งาน
2. สร้าง `.env.docker.local` พร้อมรหัสแบบสุ่มสำหรับเครื่องนี้
3. Build image ที่ล็อก Playwright และ Chromium เป็นเวอร์ชันเดียวกัน
4. เปิดเว็บที่ `http://127.0.0.1:8000`
5. แสดง Username และ Password สำหรับ Development Login

หลังแก้ source ให้รันคำสั่ง `start` อีกครั้งเพื่อ rebuild และใช้โค้ดล่าสุด

## คำสั่ง start / test / logs / stop

เปิดหรือ rebuild เว็บ:

```powershell
.\scripts\docker_dev.ps1 start
```

รัน tests ทั้งหมดใน Docker:

```powershell
.\scripts\docker_dev.ps1 test
```

ติดตาม log ของเว็บ:

```powershell
.\scripts\docker_dev.ps1 logs
```

ปิด container โดยเก็บฐานข้อมูลเดิมไว้:

```powershell
.\scripts\docker_dev.ps1 stop
```

คำสั่ง `stop` ไม่ลบ Docker volume และชุดคำสั่งนี้ไม่มีคำสั่งลบ volume อัตโนมัติ

## ข้อมูลและรหัสผ่านถูกเก็บที่ไหน

- `.env.docker.local` เก็บ Development Secret และรหัส Login บนเครื่องนี้
- Named volume `all-for-cabal-dev-data` เก็บ SQLite และ Session ที่เข้ารหัส
- `.env.docker.local`, ฐานข้อมูล, Session, Cookie, Browser Profile และไฟล์ Excel ถูกกันออกจาก Git และ Docker image

ห้ามแชร์หรือ commit `.env.docker.local` เด็ดขาด หากไฟล์สูญหาย ระบบจะสร้าง Secret ชุดใหม่และ Session เก่าจะอ่านต่อไม่ได้

## การทดสอบ VPN, IPA และ Aztek

Container ใช้ network ผ่าน Docker Desktop จึงยังขึ้นกับ VPN, Firewall และนโยบายของบริษัท

- ใช้ Docker ตรวจการ Import, Preview, Queue และ Browser tests แบบ headless
- ทดสอบ IPA Login และ Aztek Session จริงแยกบน Windows ก่อนปล่อย Setup
- การทดสอบ Docker ต้องไม่สร้างข้อมูลจริงใน Aztek
- ห้ามกดบันทึก Bundle, Item Code, Event หรือ Product จริงถ้ายังไม่ได้รับอนุญาตแยกต่างหาก

หาก Container เข้า Aztek ไม่ได้ แต่ Windows เข้าได้ ให้เก็บ log ด้วยคำสั่ง `logs` และใช้ native Windows smoke test แทน ห้ามปิด TLS หรือทำให้ค่าความปลอดภัยอ่อนลง

## การสร้าง Windows Setup สำหรับทีม

Docker ไม่ได้ใช้สร้างตัวติดตั้ง การสร้าง Setup ยังคงทำบน Windows ผ่านสคริปต์ `scripts/build_local_installer.ps1` ด้วยคำสั่งเดิม:

```powershell
.\scripts\build_local_installer.ps1 -Version <version>
```

ขั้นตอนนี้ยังรัน tests, PyInstaller, Inno Setup และตรวจ release ตามกระบวนการเดิม

## การแก้ปัญหา Docker CLI, Engine, Build และ Health Check

### ไม่พบ Docker CLI

เปิด Docker Desktop แล้วเปิด PowerShell/Codex ใหม่ หากยังไม่พบให้ตรวจว่ามีไฟล์นี้:

```text
%LOCALAPPDATA%\Programs\DockerDesktop\resources\bin\docker.exe
```

### Docker Engine ยังไม่พร้อม

รอให้ Docker Desktop แสดงสถานะ Running แล้วรันคำสั่งเดิมอีกครั้ง

### Build หรือ tests ไม่ผ่าน

ดู error จากคำสั่งที่รัน และเปิด log เพิ่มด้วย:

```powershell
.\scripts\docker_dev.ps1 logs
```

### Health Check ไม่ผ่าน

ตรวจว่า port `8000` ไม่ถูกโปรแกรมอื่นใช้อยู่ จากนั้นดู log ของ service ข้อผิดพลาดจะถูกแสดงก่อนสคริปต์หยุด
