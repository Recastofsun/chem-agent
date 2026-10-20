; Скрипт для Inno Setup
#define MyAppName "Chem-Agent"
#define MyAppVersion "2.0.0"
#define MyAppPublisher "Recastofsun"
#define MyAppURL "https://github.com/Recastofsun/chem-agent"
#define MyAppExeName "Chem-Agent.exe"

[Setup]
AppId={{B4F2A1C3-8D7E-4F6A-9B0C-1D2E3F4A5B6C}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; Устанавливаем для текущего пользователя (без запроса прав администратора)
PrivilegesRequired=lowest
OutputDir=installer_output
OutputBaseFilename=Chem-Agent-Setup-v{#MyAppVersion}
SetupIconFile=C:\work\chem-agent\chem-agent.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
; Оставили только ярлык на рабочем столе
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function IsWebView2Installed: Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
  if not Result then
    Result := RegQueryStringValue(HKCU, 'Software\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}', 'pv', Version);
  if Result then
    if (Version = '') or (Version = '0.0.0.0') then
      Result := False;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ErrorCode: Integer;
begin
  if CurStep = ssPostInstall then
  begin
    if not IsWebView2Installed then
    begin
      if MsgBox('Для работы Chem-Agent требуется компонент Microsoft Edge WebView2.' + #13#10 +
                'Установить его сейчас?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        ShellExec('open', 'https://go.microsoft.com/fwlink/p/?LinkId=2124703', '', '', SW_SHOWNORMAL, ewNoWait, ErrorCode);
        MsgBox('Пожалуйста, установите WebView2, а затем запустите Chem-Agent.', mbInformation, MB_OK);
      end;
    end;
  end;
end;