# Local release v0.1.34

- Build source: `7a5f70ed142b3c7abe2c3bf4059c266e790e559c`
- Features: shared operator-workspace redesign across Item Finder, Bundle,
  Item Code, Event, Product, Account, Login, and Local Start.
- Usability: clearer work context and queue status, readable mobile layouts,
  keyboard navigation, calendar focus handling, and contained table overflow.
- Build: `scripts/build_local_installer.ps1 -Version 0.1.34 -SkipTests`
- Full tests before build: `1541 passed, 1 warning in 394.87s`; warning is the
  existing development-secret fixture.
- Build completed with exit code 0; release-tree privacy checks passed.
- Setup: `All.for.Cabal.Web.Setup-0.1.34.exe`, 279,069,384 bytes.
- SHA-256: `9EEC748C73EE70F3AA10EC75943CA4F1BAAE4ECA6A8AFC40BA03F107AD68DC7F`
- Packaged version: 0.1.34; packaged `workspace-ui.css` and
  `workspace-ui.js` hashes match source.
- Unsigned installer; verify the SHA-256 sidecar before manual installation.
- User requested publishing without closing the installed application and will
  start the update from the program. This release has not been installed or
  launched on the user's machine and was not tested on a clean VM.
- No real Aztek records were created during verification.
