# Local release v0.1.43 — New Item Creation / Recheck

Status: delivered28October2026 — stable/latest0.1.43 published, public Setup/sidecar downloaded and size/SHA256/API digests equalbuild, updater discovery verified, issue#12CLOSED/COMPLETED. Actualuserinstallation/reopen remainsunverified.

## Publication and completion

- [Release v0.1.43](https://github.com/momozxmo/tool-cabal-local/releases/tag/v0.1.43), release426574351, published2026-10-28T11:19:35Z/18:19:35Bangkok; draftfalse/prereleasefalse/stablelatesttrue.
- Source394af5647645d0b33a550e5ef2f9009a694eb1d0 andacceptance/package-docs323e3945de0a6dbbf3c81f45a14a599cf2430a99 pushednormalfastforward toorigin/main. Publicdocs/tag32661245b027510a51f87e0e4765d89fea6590e6 pushedatomically tolocal-release/main+v0.1.43; noforce/PR.
- Freshpublicdownloadwrapper0 at18:21:04Bangkok: Setup281178982bytes/hash609F98EFE3EBE0BEC5C8A762DD24F8B7731E079AC583CD8A288CC6A99135A3B3; sidecar102bytes/hash6D31ED8D4AE0B7120FFFD95ABA4A6445D9016FD72D8365B4760944B4221B9061. BothmatchactualbuildandAPIdigests; sidecarbinarymarker/originalspacedfilenameaccepted, actualGitHubassetnamesusedots. Evidence release-v043-public-verification-20261028.json.
- RealLocalUpdate/UpdateIO publiclatestcheckwitholdversion0.1.42simulation reportsavailable0.1.43/notesidentical/assets2. No updaterdownload/install called; evidence release-v043-updater-discovery-verification-20261028.json. Existinginstallation/runtimeuntouched.
- [Issue#12](https://github.com/momozxmo/all-for-cabal/issues/12) closedcompletedafterallgates at2026-10-28T11:22:45Z/18:22:45Bangkok, thenreadbackCLOSED/COMPLETED. Closurecommentlinkscode/acceptance/release andexplicitlimits. No otherissueaction.
- Finaldelivery-statusdocscommittedseparatelyafterpublication; no source/test/dependencybytechangeoradditionalfull/build/smokerun. Worktrees/runtime/evidence preserved.

## Verified package

- Source commit394af5647645d0b33a550e5ef2f9009a694eb1d0:37approvedsource/testfilesonly, no runtime/data/artifact. Commitdoesnotchangefrozenworkingbytes; docs separate.
- Buildsession77120 finished wrapperexit0. Setup281178982bytes SHA256 `609F98EFE3EBE0BEC5C8A762DD24F8B7731E079AC583CD8A288CC6A99135A3B3`; sidecar102bytes SHA256 `6D31ED8D4AE0B7120FFFD95ABA4A6445D9016FD72D8365B4760944B4221B9061`. SetupProductVersion0.1.43, NotSigned.
- Tree/privacy/key/profile/DB/workbookchecks pass; publicbundletemplate only. All185passedsourcehashesunchanged. Installed265packageversions unchanged; basePillow11.1.0 stillbase/isolatedPillow13.0.0 unchanged.
- Embedded21codemodulesincludingall7NewItemmodules+updatehelper equalcompiledtestedsource; all21staticfiles SHAequal. PIL andPIL._version+nativedecoder equalisolatedPillow13. Evidence release-v043-packaged-source-verification2-20261028.json. FirstverifierattemptfailedbecausePIL.__init__del _version hidesparentattribute; correctedverifierusesimportlib.import_module, no product/artifact/rebuild. Prior0byteevidencefilepreserved.
- Smoke1wrapperexit0: freshLOCALAPPDATA/ownheadlessbundledChromiumprofile, health0.1.43/Localbootstrap/7toolpages/NewItemtemplate/import/apply/privatePNGimageupload+readbackhash allpass. NoAztek/create/confirmAPIcalled. OwnedPID/path/starttimecleanup+independentport8000free/packageprocess0 confirmed. No userappstop/install. Evidence release-v043-smoke-verification-20261028.json andsmoke1-exitJSON.

Historicalpackaging checkpoints below retain earlier pending state; do not rerunbuild/smoke/full because of those historical lines.

CURRENT BUILD session77120: unchanged build_local_installer.ps1 -Version0.1.43 -SkipTests, isolatedvenv PATH/command-scopedUTF8/TEMP/TMP/PIP_NO_INDEX/PyInstaller config cache restoredfinally. ActualISCC33920created18:06:57.642207Bangkok/exactInnoSetup6path/MyAppVersion043command verifiedread-only; compressinginprogress, nofinalexityet. Transcript build-cache/build-v043-20261028.log canbebuffered, do notinfercompletionfromfilepresence orrebuild. Beforeactualbuild firstcacheconsumerguard countedthecheckingPowerShellcommanditself; stoppedBEFOREwrites/reset/build. NarrowedguardtoactualPython/browserexecutable/command consumers, all0; candidatecacheabsent and allancestorsnoreparse. No previouscache/userdata removed. Build packages allalreadyfulfilled; no upgrades. PyInstaller/header/hooks warnings preserved, notwarning-free.

Preparedverification scripts outsidefrozen185: verify-v043-artifact.ps1, verify-v043-packaged-source.py (21modules+PIL/native/static/version), release-smoke-v043.ps1. No script invoked beforebuildexit0; onlysyntaxreadchecks. Package/smoke/publicgates stillpending.

User directly replied “ต่อเลย” to the explicit request to package Setup, commit/push/publish and close#12 after delivery gates. This supersedes earlier deferred release authority for#12 only. No new liveAztek create/edit/delete/upload/replay or user app installation/stop authority.

## Intended user-facing changes

- เตรียม Item ใหม่จาก Excel แบบเลือก Sheet หรือรายการที่ Finder หาไม่พบ แล้วตรวจและยืนยันก่อนสร้าง
- ค้นและเลือกใช้ Item เดิมได้ สร้างใหม่เฉพาะรายการที่เลือก พร้อมอ่านข้อมูลกลับเทียบต้นฉบับ
- PC TH/SEAรองรับGENERAL/CABALPC_PREMIUM และM TH/SEAรองรับGENERAL
- เก็บID/ต้นทาง/Amt/ประวัติ หยุดเมื่อผลไม่ตรงหรือยังยืนยันไม่ได้ ไม่สร้างซ้ำ และส่งต่อเฉพาะผลผ่านที่เลือก
- รวมร่างค่าตรงกันและกู้IDจากคำตอบเดิมที่โปรแกรมเก็บไว้ได้ตามหลักฐาน ไม่เดาIDเมื่อคำตอบหายทั้งหมด

## Exact source gate

Candidate branchcodex/new-item-issue12/HEAD78fdc749; FULL6 passed3108tests1existingwarning10333.65s, ended28October17:47:41.844849Bangkok. Native/raw/signed/wrapper0, actual/aggregate/uniqueJUnit3108/0failure0error0skip, independentfreeze185/originalprotectedhashesmatch/evidence_errors[]. Acceptance22criteria/179distinctcase references, notadditionaltests. FULL5 remainsfailed3104+4; repairedonlytwoUItestlocators, productionbytesunchanged. See [acceptance](tickets/new-item/acceptance-final-20261028.md).

Preflight origin/main78fdc7494d56dbc30ac54a301adbeecc1edf2044; local-release/mainbfe6cfbcf042570ef5c18c8a8358863820961eee; stable/latestv0.1.42; v0.1.43tag/release absent. Public release docs checkout clean oncodex/local-release-docs-v0.1.13, noAGENTS/HANDOFFfiles inthatpublicdocsrepo; currentREADME/workflowread. No force/PR/worktree/evidence cleanup.

Build uses the approved isolatedmediaenvironment withPillow13.0.0; base environment staysunchanged. Dry-run/no-index confirmsallrequirementsalreadyinstalled aftercommand-scopedPYTHONUTF8=1; firstdry-runfailedcp874decodebeforeinstall, preservedasdiagnostic, no source/settingschange. BuilderPATH/TEMP/TMP/UTF8/browser/PyInstaller cachevariables must becommand-scoped/restoredfinally. VersionfromAFC_BUILD_VERSION, noteditingtestedversionfile. -SkipTests onlyfor exactpassedsource.

## Historical planned gates — completed above

Build exit0; releaseprivacy/version/helper/static/embeddedsource/Pillow proof; isolatedpackage smoke withownedPID/path/starttimecleanup andnoAztek; selective source/docs commits andnormalfastforward; publicnotes/tag/stablerelease; freshdownloadSetup+sidecar size/hashmatch; issue#12closure andreadback. No completionclaimbeforeallgates.

User installation/reopen/draft-preservation, signing, cleanVM, Premiumlivecreate/alllivevariants/imagepixelacceptance remainunverified. Existingoldreleases andoriginal/WR/workbook/evidence arepreserved.
