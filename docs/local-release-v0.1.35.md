# Local release v0.1.35

- Build source: `b0f952565790713ba39d3f4fa59b849cfd4a531e`
- Excel upload cap increased to 64 MB, including Bundle browser validation.
- Installed Launcher rejects a running server whose version differs from its own.
- Targeted verification: 107 passed in 12.86s (request limits, Launcher, Bundle import/API/UI, updater and helper).
- Build: `scripts/build_local_installer.ps1 -Version 0.1.35 -SkipTests`, exit 0.
- Release-tree privacy checks passed; packaged version is 0.1.35.
- Packaged bundle_import.js SHA-256 matches source.
- Setup size: 279,082,952 bytes.
- SHA-256: `7F305FB0FC0CA3505BB631DE6143A964356312F5EC8935DDE6DFB962DB0C62F4`
- Full suite was not repeated for this patch; prior v0.1.34 full suite passed 1,541 tests.
- Not installed on the user's machine: user will initiate the update in the application. No clean-VM validation or real Aztek creation was performed.
