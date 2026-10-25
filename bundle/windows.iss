#ifndef AppVersion
  #error AppVersion is required
#endif
#ifndef SourceDir
  #error SourceDir is required
#endif
#ifndef WebViewSetup
  #error WebViewSetup is required
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
Source: "{#WebViewSetup}"; Flags: dontcopy

[Icons]
Name: "{autoprograms}\Presenteriyaki"; Filename: "{app}\Presenteriyaki.exe"; WorkingDir: "{app}"; Comment: "Presenteriyaki PDF presenter (org.pku-lemonade.pagecue)"

[Run]
Filename: "{app}\Presenteriyaki.exe"; Description: "Open Presenteriyaki"; Flags: nowait postinstall skipifsilent

[Code]
function WebViewInstalled: Boolean;
var
  Version: String;
  Key: String;
begin
  Key := 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  Result := (RegQueryStringValue(HKLM32, Key, 'pv', Version) and
             (Version <> '') and (Version <> '0.0.0.0')) or
            (RegQueryStringValue(HKCU32, Key, 'pv', Version) and
             (Version <> '') and (Version <> '0.0.0.0'));
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ExitCode: Integer;
begin
  Result := '';
  if WebViewInstalled then
  begin
    Log('Microsoft Edge WebView2 Runtime is already installed');
    Exit;
  end;
  WizardForm.StatusLabel.Caption := 'Installing Microsoft Edge WebView2 (internet connection required)...';
  ExtractTemporaryFile('MicrosoftEdgeWebview2Setup.exe');
  if not Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install',
              '', SW_HIDE, ewWaitUntilTerminated, ExitCode) then
    Log('Could not start the WebView2 installer')
  else
    Log(Format('WebView2 installer exit code: %d', [ExitCode]));
  if not WebViewInstalled then
    Result := 'Microsoft Edge WebView2 could not be installed. Connect to the internet and retry, ' +
              'or install the WebView2 Runtime from Microsoft before running Setup again.';
end;
