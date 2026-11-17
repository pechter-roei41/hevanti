# Building Hevanti locally

Most people only need the release (`Hevanti-Setup.exe` or `Hevanti.zip` from GitHub). To run from the source or build the packages:

**Run from the source (Windows, or Linux for the pages and the server only)**
1. Python 3.12 (the version the installer ships). `python -m pip install numpy pillow` is enough for the tests; the app itself needs
   `System/requirements.txt` (pinned with SHA-256: `tools/pin_requirements.py` updates it).
2. `python System/Program/live_transcribe.py --app` serves the app at `http://127.0.0.1:8765/` (the port can be 8766 to 8769) and
   opens it. Set `BZM_NO_BROWSER=1` to open nothing, `BZM_DATA_DIR` and `LOCALAPPDATA` to keep a test library apart.
3. Tests: see `CLAUDE.md` (plain scripts, each prints `all passed`; set `PYTHONUTF8=1`).

**Build the packages (what the release workflow does, `.github/workflows/release.yml`)**
- ZIP: `python tools/build_zip.py [out.zip]` (Install downloads Python), or with its own Python inside:
  `python tools/build_zip.py --python-zip <python-3.12-embed-amd64.zip> --get-pip <get-pip.py> out.zip`.
- Installer: `python tools/build_setup_dir.py <python-3.12-embed-amd64.zip> <get-pip.py> <out folder>`, install the packages into
  that Python on a Windows machine, then compile `installer/hevanti.iss` with Inno Setup 6 (`ISCC.exe`).
  The installer is not signed (see `CODE_SIGNING.md`).
- A release is a tag `v*` on `main`; the workflow runs every test first. Keep the version number in step in the places listed in
  `CLAUDE.md` ("Releasing a version").
