#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif

[Setup]
AppId=org.pku-lemonade.pagecue
AppName=Presenteriyaki
AppVersion={#AppVersion}
AppPublisherURL=https://github.com/pku-lemonade/presenteriyaki
DefaultDirName={localappdata}\Programs\Presenteriyaki
PrivilegesRequired=lowest
MinVersion=10.0.17763
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
DisableProgramGroupPage=yes
DisableDirPage=auto
WizardStyle=modern
Compression=lzma2/fast
SolidCompression=yes
UninstallDisplayIcon={app}\Presenteriyaki.exe
CloseApplications=yes
RestartApplications=no

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Presenteriyaki"; Filename: "{app}\Presenteriyaki.exe"; WorkingDir: "{app}"; Comment: "Presenteriyaki PDF presenter (org.pku-lemonade.pagecue)"

[Run]
Filename: "{app}\Presenteriyaki.exe"; Description: "Open Presenteriyaki"; Flags: nowait postinstall skipifsilent
