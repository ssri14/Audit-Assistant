# Packaging and releases

The Windows x64 EXE and macOS Apple Silicon DMG include Python, Qt, PDFium, PDF libraries and four fictional demo PDFs. They do not include models, GPU servers, developer configuration, credentials, audit sessions or pilot evaluation answers.

## GitHub builds

After the repository is connected, push `main` using normal Git commands. **Actions → Build desktop packages** runs native Windows and Mac builds independently. **Run workflow** also starts a build. Each completed job uploads an artifact containing its package and SHA-256 checksum, retained for 30 days. Extract the downloaded artifact ZIP to obtain the EXE or DMG.

For a release, set `VERSION` in `version.py`, update `RELEASE_NOTES.md`, commit, and push a matching tag:

```sh
git tag v0.1.0
git push origin v0.1.0
```

After both builds and packaged-app tests pass, the workflow assembles a **draft pre-release** with both downloads and checksums. Review it under Releases and publish it when ready. Existing published releases are preserved; use a new version tag to replace a published build. The release job uses GitHub's built-in token, not a personal token stored in the repository.

Fine-grained token permissions for pushing source and workflow files: repository Contents and Workflows Read/Write. A local `.git-token`, if used, is ignored. The remote must contain the clean repository URL, never credentials. No custom Python push helper is needed.

The workflow uses `macos-15` (Apple Silicon) and `windows-2022` (x64). If Mac runners are unavailable, use the local fallback below and attach the resulting DMG to the same release as the Windows EXE. A draft-release assembly requires both CI jobs; a manual release can combine a successful Windows artifact with the locally tested DMG.

## Local fallback

Use an existing Python environment with `requirements-build.txt` installed:

```sh
python -m pip install -r requirements-build.txt
python build_package.py
python verify_package.py
```

Build on the destination operating system. Mac builds create `dist/AuditAssistant-0.1.0-macOS-arm64.dmg`; Windows builds create `dist/AuditAssistant-0.1.0-Windows-x64.exe`. These are portable app packages; the EXE is not an installation wizard. Existing same-name outputs are preserved and must be moved before rebuilding. `--build-dir` selects scratch storage, and `--skip-build` repackages an existing native build.

Native frameworks are staged in the OS temporary directory, outside OneDrive. On the development Mac, use the existing configured Python and dependency cache when building; `.local-runtime.json` and its machine-specific paths are not committed or bundled.

The verifier starts the actual frozen executable from a clean temporary working directory without `PYTHONPATH`, `PYTHONHOME` or `VIRTUAL_ENV`. The offline self-test checks bundled PDFs, native/scanned routing, PDF rendering, GUI controls, rule edits, actual activity entries, source highlights, export and version. Network requests are blocked during this test. Successful package verification is not a model-accuracy test.

## Configuration and supported targets

Use **GPU server settings** after opening the installed app. For a portable `.env` setup, put `.env` alongside the Windows EXE, or beside the macOS `.app` bundle. For an app installed in Applications, GUI settings are usually easier. Settings are saved per user in `~/.audit-assistant/servers.json`. Precedence: defaults → external `.env` → saved GUI settings → environment variables. No `.env` is included in the download.

Initial release targets: Windows x64 and macOS 14+ on Apple Silicon. Intel-Mac, Windows ARM and Linux downloads are not produced by this workflow. No Ollama or participant Python installation is required; reachable, compatible GPU inference endpoints are required for analysis.

Packages are unsigned and the Mac app is not notarized, so platform trust prompts may appear. Optional future Mac signing uses `AUDIT_ASSISTANT_CODESIGN_IDENTITY`, followed by notarization/stapling. Windows publisher signing can be added when a certificate is available.

Build references: [GitHub runner labels](https://docs.github.com/en/actions/reference/runners/github-hosted-runners), [artifact uploads](https://github.com/actions/upload-artifact), [artifact downloads](https://github.com/actions/download-artifact), [PyInstaller runtime paths](https://pyinstaller.org/en/stable/runtime-information.html).
