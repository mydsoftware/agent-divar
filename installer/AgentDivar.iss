; نصب‌کننده رسمی Agent Divar برای ویندوز
#define MyAppName "Agent Divar"
#ifndef MyAppVersion
  #define MyAppVersion "1.0.0"
#endif
#define MyAppPublisher "Mydsoftware"
#define MyAppExeName "AgentDivar.exe"

[Setup]
AppId={{B71F7E42-5D6A-4C89-9F14-8B4E5D1A2026}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\AgentDivar
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=AgentDivar-Setup-{#MyAppVersion}-x64
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: "desktopicon"; Description: "ایجاد میانبر روی دسکتاپ"; GroupDescription: "میانبرها:"; Flags: unchecked

[Files]
Source: "..\dist\AgentDivar\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "اجرای Agent Divar"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; عمداً داده‌های کاربر در LocalAppData حذف نمی‌شوند.
