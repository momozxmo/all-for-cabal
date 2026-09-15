# Local release v0.1.33

- Build source: `f67e11390b16ef6e6317c0171b478a81551af8a3`
- Features: [Bundle template / bulk paste](bundle-template-import.md)
- Build: `scripts/build_local_installer.ps1 -Version 0.1.33 -SkipTests`
- Full tests before build: `1507 passed, 1 warning in 416.34s`; warning is the existing development-secret fixture.
- Build completed with exit code 0; release-tree privacy checks passed.
- Setup: `All.for.Cabal.Web.Setup-0.1.33.exe`, 279,055,785 bytes.
- SHA-256: `1C8912D63A70854D3255239D3ADBA370B89AC86B95BF750C698046D4A19E417A`
- Packaged version: 0.1.33; `web.bundle_import` exists in the executable archive.
- Packaged template and import JavaScript hashes match source.
- Unsigned installer; verify the SHA-256 sidecar before manual installation.
- User requested publishing only without closing the installed application. This release has not been installed/launched on the user's machine or tested on a clean VM.
- No real Aztek records were created during verification.
