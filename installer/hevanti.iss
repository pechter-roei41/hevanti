; Hevanti (הבנתי) - the Windows installer: Hevanti-Setup.exe - (c) 2026 Hevanti. MIT License, see LICENSE
; One file, no admin, nothing else to install: Hevanti's own Python with every package already inside.
; Installs for this user only (%LOCALAPPDATA%\Programs\Hevanti), so Windows does not ask for an administrator.
; The lectures are kept in Documents\הבנתי (not in the program's folder), so an update or uninstall never touches them.
; Built by .github/workflows/release.yml:  iscc /DAppVersion=2.21 /DSrc=<build folder> installer\hevanti.iss

#ifndef AppVersion
  #define AppVersion "2.21"
#endif
#ifndef Src
  #define Src "..\build\app"
#endif

[Setup]
AppId={{6B0E2A4C-9F3D-4E21-A7C5-48D1E2B0C9A1}
AppName=הבנתי (Hevanti)
AppVersion={#AppVersion}
AppPublisher=Hevanti
; the file information of Hevanti-Setup.exe: the same product name in every build, the version of the program
VersionInfoProductName=Hevanti
VersionInfoProductVersion={#AppVersion}
VersionInfoVersion={#AppVersion}.0.0
VersionInfoCompany=Hevanti
VersionInfoDescription=Hevanti Setup
VersionInfoCopyright=(c) 2026 Hevanti. MIT License
AppPublisherURL=https://github.com/pechter-roei41/hevanti
AppSupportURL=https://github.com/pechter-roei41/hevanti/issues
DefaultDirName={localappdata}\Programs\Hevanti
DefaultGroupName=הבנתי
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputBaseFilename=Hevanti-Setup
OutputDir=..\dist
SetupIconFile={#Src}\hevanti.ico
UninstallDisplayIcon={app}\hevanti.ico
UninstallDisplayName=הבנתי (Hevanti)
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
LicenseFile={#Src}\System\LICENSE.txt
InfoBeforeFile={#Src}\PRIVACY.txt
CloseApplications=yes

[Languages]
Name: "he"; MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
he.OcrTask=קריאת הטקסט שעל השקופיות (Tesseract, חינם - Windows יבקש אישור פעם אחת)
en.OcrTask=Read the text on the slides (Tesseract, free - Windows asks for permission once)
he.DesktopTask=קיצור דרך בשולחן העבודה
en.DesktopTask=A shortcut on the desktop
he.UpdatesTask=בדיקה אוטומטית של גרסה חדשה בכל הפעלה (בקשה ל-GitHub, בלי מידע עליך)
en.UpdatesTask=Check for a new version when Hevanti starts (a request to GitHub, nothing about you is sent)
he.RunNow=לפתוח את הבנתי עכשיו
en.RunNow=Open Hevanti now

[Tasks]
Name: "desktop"; Description: "{cm:DesktopTask}"
Name: "ocr"; Description: "{cm:OcrTask}"
Name: "updates"; Description: "{cm:UpdatesTask}"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; an older version's program files (never the lectures: they are in Documents\הבנתי)
Type: filesandordirs; Name: "{app}\System\Program\__pycache__"

[Icons]
Name: "{userprograms}\הבנתי"; Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --app"; WorkingDir: "{app}"; IconFilename: "{app}\hevanti.ico"; Flags: runminimized
Name: "{userdesktop}\הבנתי"; Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --app"; WorkingDir: "{app}"; IconFilename: "{app}\hevanti.ico"; Flags: runminimized; Tasks: desktop

[Run]
; the update check: the box of the installer decides (it can be changed later in Hevanti: Settings, Privacy)
Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --set-update-check off"; Flags: runhidden waituntilterminated; Tasks: not updates
Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --set-update-check on"; Flags: runhidden waituntilterminated; Tasks: updates
Filename: "{app}\System\install_ocr.bat"; Parameters: "nopause"; Flags: runhidden waituntilterminated; Tasks: ocr
Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --app"; WorkingDir: "{app}"; Description: "{cm:RunNow}"; Flags: postinstall nowait runminimized skipifsilent

[UninstallRun]
; take Hevanti out of Claude / ChatGPT / Gemini's settings, so they don't look for a program that is gone
Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --disconnect-ai"; Flags: runhidden waituntilterminated; RunOnceId: "DisconnectAI"

[UninstallDelete]
; the settings with the Gemini key (encrypted) and every copy of them (.bak, .corrupt, .tmp), and the models check
Type: files; Name: "{localappdata}\Hevanti\settings.json*"
Type: files; Name: "{localappdata}\Hevanti\gemini_models.json"
; the speech models (about 1.6GB each; since 2.21 in the student's own folder)
Type: filesandordirs; Name: "{localappdata}\Hevanti\models"
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\System"
