; Inno Setup script for DLPizer's Windows installer. CI compiles it with
;   ISCC /DAppVersion=1.7.0 packaging\windows\dlpizer.iss
; after PyInstaller has built dist\DLPizer.exe.
;
; It installs for the current user only, into a folder that user can write
; to, so no administrator rights are needed and the app can still replace
; itself when it updates.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

[Setup]
AppId={{C678D6F1-28CE-4B10-B18E-8A7AED2BF94C}
AppName=DLPizer
AppVersion={#AppVersion}
AppVerName=DLPizer {#AppVersion}
AppPublisher=m1omg
AppPublisherURL=https://github.com/m1omg/ytgrab
AppSupportURL=https://github.com/m1omg/ytgrab/issues
AppUpdatesURL=https://github.com/m1omg/ytgrab/releases
DefaultDirName={localappdata}\Programs\DLPizer
DisableProgramGroupPage=yes
DisableDirPage=auto
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\..
OutputBaseFilename=DLPizer-setup-windows-x86_64
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\DLPizer.exe
UninstallDisplayName=DLPizer
; Close a running DLPizer before replacing it.
CloseApplications=yes

[Languages]
Name: "en"; MessagesFile: "compiler:Default.isl"
#if FileExists(AddBackslash(CompilerPath) + "Languages\Slovak.isl")
Name: "sk"; MessagesFile: "compiler:Languages\Slovak.isl"
#endif

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\..\dist\DLPizer.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\DLPizer"; Filename: "{app}\DLPizer.exe"
Name: "{autodesktop}\DLPizer"; Filename: "{app}\DLPizer.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DLPizer.exe"; Description: "{cm:LaunchProgram,DLPizer}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; What the app's own updates leave beside it: the version they replaced, and
; a download that was cut short.
Type: files; Name: "{app}\.DLPizer.exe.*"
