[Setup]
; Keep the name standard so Windows sees it as the same app
AppName=Reference Vault
AppVersion=1.0.2
; Installs to the exact same folder as the CPU version
DefaultDirName={autopf}\ReferenceVault
DisableDirPage=no
DefaultGroupName=Reference Vault
UninstallDisplayIcon={app}\ReferenceVault.exe
Compression=lzma2
SolidCompression=yes
OutputDir=userdocs:ReferenceVault_Setup
; Output a distinctly named installer for your GitHub Releases
OutputBaseFilename=ReferenceVault_v1.0.2_GPUSetup
SetupIconFile=app_icon.ico
PrivilegesRequired=admin

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
; Pulls from the newly generated, unified folder
Source: "dist\ReferenceVault\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
; Creates standard shortcuts that work for whichever version is currently installed
Name: "{group}\Reference Vault"; Filename: "{app}\ReferenceVault.exe"
Name: "{autodesktop}\Reference Vault"; Filename: "{app}\ReferenceVault.exe"; Tasks: desktopicon