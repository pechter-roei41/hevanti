# Code signing policy

Free code signing provided by [SignPath.io](https://about.signpath.io), certificate by [SignPath Foundation](https://signpath.org).

## What is signed

`Hevanti-Setup.exe`, the Windows installer attached to each [release](https://github.com/pechter-roei41/hevanti/releases). It is built from this repository by the public GitHub Actions workflow [`release.yml`](.github/workflows/release.yml), from the tagged commit only, and is submitted to SignPath from that workflow. Nothing built on a personal computer is signed.

## Team

| Role | Who |
|---|---|
| Committers and reviewers | [Roei Pechter](https://github.com/pechter-roei41) |
| Approvers (approve each signing request) | [Roei Pechter](https://github.com/pechter-roei41) |

Every signing request is approved by hand in SignPath. Accounts with access use multi-factor authentication.

## Privacy

Hevanti does not send anything anywhere by itself:

- Transcription and slide reading run on the student's computer. Transcripts and slides are saved in the "הקורסים שלי" (My Lectures) folder on that computer.
- The AI connector (`hevanti_mcp.py`) only reads that folder, and only when the student's own AI app asks it to. What the AI reads goes to that AI's provider, as in any conversation with it.
- "Sync to the cloud" is off until the student turns it on. When on, it copies each course's transcripts into the student's own Google Drive or OneDrive folder.
- The app's page loads its fonts from Google Fonts, and YouTube's own player when the student watches a YouTube video in it.
- Hevanti checks GitHub for a newer release, and downloads the transcription model (from Hugging Face) and, if the student agrees, Tesseract and its language files (from GitHub) the first time they are needed.

This program will not transfer any information to other networked systems unless specifically requested by the user or the person installing or operating it.
