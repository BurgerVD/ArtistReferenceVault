[Setup]

AppName=Reference Vault

AppVersion=1.0.2

; Defaults to C:\Program Files\ReferenceVault

DefaultDirName={autopf}\ReferenceVault

; Forces the wizard to show the "Select Destination Location" screen

DisableDirPage=no

DefaultGroupName=Reference Vault

UninstallDisplayIcon={app}\ReferenceVault.exe

Compression=lzma2

SolidCompression=yes

OutputDir=userdocs:ReferenceVault_Setup

OutputBaseFilename=ReferenceVault_v1.0.2_Setup

SetupIconFile=app_icon.ico

; Asks for the Windows Admin Shield so it has permission to write to any folder the user chooses

PrivilegesRequired=admin

[Tasks]

Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";



[Files]

; This grabs everything PyInstaller made and packs it into the setup file

Source: "dist\ReferenceVault\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Grabs your icon

Source: "app_icon.ico"; DestDir: "{app}"; Flags: ignoreversion



[Icons]

; Creates the Start Menu and Desktop shortcuts

Name: "{group}\ReferenceVault"; Filename: "{app}\ReferenceVault.exe"

Name: "{autodesktop}\ReferenceVault"; Filename: "{app}\ReferenceVault.exe"; Tasks: desktopicon



