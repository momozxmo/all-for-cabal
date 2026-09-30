# Local release v0.1.39

Build date: 2026-10-01. Source snapshot:
`d1a3d18b1eb5f97e7d0d795a8c58d3bd89340c73`.

## Scope

- Item Finder ส่งเฉพาะที่เลือกหรือส่งทั้งหมดแยกกัน พร้อมขอบเขต Product ที่แสดง
- Clear ข้อความ/พรีวิว Bulk Paste โดยคงคิว Bundle และทิ้ง late response
- เรต RANDOM `0` สำหรับไอเทมและ Currency ตั้งแต่ import จนกรอก stable ID
- ชื่อ Currency แยกบรรทัดเต็ม รองรับชื่อยาว/จอเล็ก โดยไม่เปลี่ยน payload/พฤติกรรมเดิม

## Verification

- Fresh full suite: **1,701 passed, 1 warning in 653.30s**
  (`python -X utf8 -B -m pytest tests -q --basetemp=build-cache/pytest-release-v039-20261001-7b82`)
  warning เดิมเรื่อง process-local development secrets
- Build: `scripts/build_local_installer.ps1 -Version 0.1.39 -SkipTests`
  ใช้ source ที่เพิ่งทดสอบครบ ไม่รันทดสอบซ้ำใน basetemp เก่า
- PyInstaller โปรแกรมและ update helper, release tree privacy check และ Inno Setup ผ่าน
- Runtime และ Setup แสดงรุ่น `0.1.39`; helper รวมอยู่ในแพ็กแล้ว
- Static SHA-256 ตรงกับ source: `index.html`, `bundles.html`, `bundle_import.js`, `workspace-ui.css`
- Packaged executable ใช้ runtime ใหม่แยกจากข้อมูลผู้ใช้ ผ่าน health, Local session,
  Item Finder/Account/Bundle/Item Code/Event/Product, UI ใหม่,
  import RANDOM เรต 0 และ empty Recheck history โดยไม่สร้างข้อมูลจริง
- UI regression ครอบคลุม Keyboard/visible focus และ Overflow 360/768/1280/1600px;
  Finder และ Bulk Paste ตรวจ Desktop 1280px/Mobile 390px

## Artifact

- Setup: `All.for.Cabal.Web.Setup-0.1.39.exe`
- Size: **279,111,803 bytes**
- SHA-256: **EF72023BD2B005CDCAA6A39030A5D1DABB9053BA62606090131E68C72027FCE3**
- Setup/checksum ต้องเผยแพร่จาก build เดียวกันที่
  [GitHub Release v0.1.39](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.39)
- สถานะ: build ตรวจครบ กำลังเผยแพร่; ต้องตรวจ production updater/download หลัง publish

## Boundaries

- ไม่ติดตั้งทับ/ปิดโปรแกรมเดิม ไม่แตะ runtime data ของผู้ใช้ และไม่สร้างจริงบน Aztek
- ไม่รวม CONTEXT.md ที่ผู้ใช้แก้ค้าง, outputs, workbook, profile, session หรือ secrets ใน commit/release
- Document Reference ยังคงต้นฉบับครบ การเลือกบางไอเทมอาจขึ้นรายการขาดใน Recheck
- Setup ยังไม่ลง digital signature; ยังไม่ทดสอบติดตั้งบน clean VM
- การติดตั้งอัปเดตจริง/เปิดกลับและร่าง/คิวของผู้ใช้ต้องตรวจหลังผู้ใช้กดอัปเดตเอง
