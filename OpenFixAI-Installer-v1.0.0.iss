#define MyAppName "OpenFix AI"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Thirdeyegameing"
#define MyAppExeName "OpenFixAI.exe"

[Setup]
AppId={{D71F6E39-1F84-4C25-89EC-08D1B83D7E25}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\OpenFix AI
DefaultGroupName=OpenFix AI
DisableProgramGroupPage=yes
DisableDirPage=no
OutputDir=installer
OutputBaseFilename=OpenFixAI-Setup-v1.0.0
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
RestartIfNeededByRun=no
AllowNoIcons=yes
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "dist\OpenFixAI\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\OpenFix AI"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\OpenFix AI"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch OpenFix AI"; Flags: nowait postinstall skipifsilent
