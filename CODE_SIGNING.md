# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io/), certificate by [SignPath Foundation](https://signpath.org/).

> Status: the first application to the SignPath Foundation was declined for lack of proof of users; the project will apply again once it has them. Until it is approved, `Hevanti-Setup.exe` is **not** signed
> and Windows SmartScreen shows a warning ("Windows protected your PC": More info, then Run anyway). This page will be
> updated when the first signed release is published.

## What is signed

- `Hevanti-Setup.exe`, the Windows installer of Hevanti (הבנתי), built from the source code in this repository.
- Product name: `Hevanti`. Product version: the version in `System/Program/live_transcribe.py` (`VERSION`), the same value
  in every build.
- Not signed by this project: the Python runtime and the Python packages that are copied into the installer as they
  are (they are third-party components, included unmodified). `Hevanti.zip` (the same app as a folder) is not signed.

## How a release is made

1. Changes are committed to this repository (GitHub). A release is a tag `v*` on a commit of the `main` branch.
2. GitHub Actions (`.github/workflows/release.yml`) builds the program folder and the installer from that commit.
   The build scripts are in this repository (`installer/`, `tools/`, `.github/workflows/`), so anyone can read how the
   installer is made.
3. The installer is sent to SignPath for signing. **An approver approves every signing request by hand.**
4. The signed installer is attached to the GitHub release.

## Team and roles

| Role | Who | What they do |
| --- | --- | --- |
| Author | Hevanti maintainer ([pechter-roei41](https://github.com/pechter-roei41)) | Writes and commits the code. |
| Reviewer | Hevanti maintainer ([pechter-roei41](https://github.com/pechter-roei41)) | Reviews every change from other contributors (pull requests) before it is merged. |
| Approver | Hevanti maintainer ([pechter-roei41](https://github.com/pechter-roei41)) | Approves each signing request, after checking that the release was built from this repository. |

Hevanti is a one-person project today. If other people join, they are listed here with their roles.
All team members use multi-factor authentication on GitHub and on SignPath.

## Privacy policy

The full, current policy is [PRIVACY.md](PRIVACY.md) (with the [terms of use](TERMS.md)); it also comes with the installer. The table below is the short list of what leaves the computer.

Hevanti runs on your computer. It has no server and no account of its own, and it does not collect statistics.
The transcript and the slide pictures are saved only on your computer (in your Documents folder).

The program sends information to other computers only in these cases:

| When | What is sent, and to whom |
| --- | --- |
| You ask a question ("תשובה כאן", or Enter in the small window) | The question, the last minutes of the transcript and the slide on the screen are sent to Google's Gemini API (`generativelanguage.googleapis.com`), with the Gemini key that you created and saved in the settings. |
| You save a Gemini key: "read formulas and handwriting" then starts **on** (you can turn it off in the settings, under the key) | Each new slide picture that is saved is sent to Google's Gemini API, in the same way, so that formulas and handwriting are read. Someone who already had a key before this change keeps the choice they made. Turned off, only the slide that goes with a question is sent. |
| First lecture, or a new language | The speech-recognition model is downloaded from Hugging Face (`huggingface.co`). Nothing about you is sent. |
| You open a recording from a link (YouTube, Google Drive, Panopto) | The file is downloaded from the address you gave. The first time, the helper `yt-dlp` may be installed from PyPI (`pypi.org`). |
| The program starts, unless you turned the check off (a box in the installer, or Settings, Privacy) | A request to GitHub (`api.github.com`) asks which version is the latest. No information about you is sent. |
| You choose "copy to ChatGPT / Gemini / Claude" | The question is copied to your clipboard and you paste it yourself. The program opens the AI's website or app, and sends nothing to it. |

Google may use what is sent to the Gemini API according to its own terms; see Google's terms for the free tier
(the settings page and the guide say this too). The program does not transfer any other information to other networked
systems.

If you use "cloud sync" (off by default), the transcripts are written to a Google Drive or OneDrive folder on your
computer, and that service syncs them under its own terms.

## Checking a download, and antivirus warnings

Every release lists the SHA-256 of `Hevanti-Setup.exe` and `Hevanti.zip` in its notes, and attaches them as `*.sha256` files. To check a download in PowerShell: `Get-FileHash Hevanti-Setup.exe` and compare the value. The installer is built from the tagged commit by the public release workflow, and the packages and downloads it uses are pinned by SHA-256 (`System/requirements.txt`).

The installer is not signed yet, so Windows SmartScreen or an antivirus may warn about it (a program that carries its own Python and installs for one user looks like many harmful ones). Each release is submitted to Microsoft Security Intelligence (<https://www.microsoft.com/wdsi/filesubmission>) as "incorrectly detected", and the result of a VirusTotal scan is kept in the README. If your antivirus blocks Hevanti, write to <hevanti.support@gmail.com> with its name and the version.

## Uninstall

The installer adds an entry in Windows Settings, Apps. Removing it deletes the program. Your lectures, in
`Documents\הבנתי`, are never deleted by an update or an uninstall.

## Reporting a problem

If you think a signed file is wrong or harmful, write to <hevanti.support@gmail.com> or open an
[issue](https://github.com/pechter-roei41/hevanti/issues). Reports about a signed release are answered first.
