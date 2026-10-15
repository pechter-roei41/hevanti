; Hevanti (הבנתי) - the Windows installer: Hevanti-Setup.exe - (c) 2026 Roei Pechter. MIT License, see LICENSE
; One file, no admin, nothing else to install: Hevanti's own Python with every package already inside.
; Installs for this user only (%LOCALAPPDATA%\Programs\Hevanti), so Windows does not ask for an administrator.
; The lectures are kept in Documents\הבנתי (not in the program's folder), so an update or uninstall never touches them.
; Built by .github/workflows/release.yml:  iscc /DAppVersion=2.1 /DSrc=<build folder> installer\hevanti.iss

#ifndef AppVersion
  #define AppVersion "2.1"
#endif
#ifndef Src
  #define Src "..\build\app"
#endif

[Setup]
AppId={{6B0E2A4C-9F3D-4E21-A7C5-48D1E2B0C9A1}
AppName=הבנתי (Hevanti)
AppVersion={#AppVersion}
AppPublisher=Roei Pechter
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
CloseApplications=yes

[Languages]
Name: "he"; MessagesFile: "compiler:Languages\Hebrew.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
he.OcrTask=קריאת הטקסט שעל השקופיות (Tesseract, חינם - Windows יבקש אישור פעם אחת)
en.OcrTask=Read the text on the slides (Tesseract, free - Windows asks for permission once)
he.DesktopTask=קיצור דרך בשולחן העבודה
en.DesktopTask=A shortcut on the desktop
he.RunNow=לפתוח את הבנתי עכשיו
en.RunNow=Open Hevanti now

[Tasks]
Name: "desktop"; Description: "{cm:DesktopTask}"
Name: "ocr"; Description: "{cm:OcrTask}"

[Files]
Source: "{#Src}\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[InstallDelete]
; an older version's program files (never the lectures: they are in Documents\הבנתי)
Type: filesandordirs; Name: "{app}\System\Program\__pycache__"

[Icons]
Name: "{userprograms}\הבנתי"; Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --app"; WorkingDir: "{app}"; IconFilename: "{app}\hevanti.ico"; Flags: runminimized
Name: "{userdesktop}\הבנתי"; Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --app"; WorkingDir: "{app}"; IconFilename: "{app}\hevanti.ico"; Flags: runminimized; Tasks: desktop

[Run]
Filename: "{app}\System\install_ocr.bat"; Parameters: "nopause"; Flags: runhidden waituntilterminated; Tasks: ocr
Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --app"; WorkingDir: "{app}"; Description: "{cm:RunNow}"; Flags: postinstall nowait runminimized skipifsilent

[UninstallRun]
; take Hevanti out of Claude / ChatGPT / Gemini's settings, so they don't look for a program that is gone
Filename: "{app}\python\python.exe"; Parameters: """{app}\System\Program\live_transcribe.py"" --disconnect-ai"; Flags: runhidden waituntilterminated; RunOnceId: "DisconnectAI"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\python"
Type: filesandordirs; Name: "{app}\System"
