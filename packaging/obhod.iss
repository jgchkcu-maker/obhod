; Inno Setup script: builds dist\installer\Obhod-Setup-<version>.exe from dist\Obhod.
; Build with packaging\build.ps1, which runs PyInstaller first.

#define AppVersion "0.1.0"

[Setup]
AppId={{DB31F051-041E-417A-81DC-8AB052B71350}
AppName=Обход
AppVersion={#AppVersion}
AppVerName=Обход {#AppVersion}
AppPublisher=Outlik
AppPublisherURL=https://github.com/jgchkcu-maker/obhod
AppSupportURL=https://github.com/jgchkcu-maker/obhod/issues
DefaultDirName={autopf}\Obhod
DefaultGroupName=Обход
DisableProgramGroupPage=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=Obhod-Setup-{#AppVersion}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\Obhod.exe
UninstallDisplayName=Обход
CloseApplications=yes

[Languages]
Name: "ru"; MessagesFile: "compiler:Languages\Russian.isl"

[Tasks]
Name: "desktopicon"; Description: "Создать ярлык на рабочем столе"; GroupDescription: "Ярлыки:"

[Files]
Source: "..\dist\Obhod\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\LICENSE"; DestDir: "{app}\licenses"; DestName: "LICENSE-Obhod.txt"; Flags: ignoreversion
Source: "..\THIRD_PARTY_NOTICES.md"; DestDir: "{app}\licenses"; Flags: ignoreversion
Source: "..\licenses\*"; DestDir: "{app}\licenses"; Flags: ignoreversion

[Icons]
Name: "{group}\Обход"; Filename: "{app}\Obhod.exe"
Name: "{group}\Лицензии и авторы"; Filename: "{app}\licenses"
Name: "{group}\Удалить Обход"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Обход"; Filename: "{app}\Obhod.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\Obhod.exe"; Description: "Запустить Обход"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\sc.exe"; Parameters: "stop obhod"; Flags: runhidden; RunOnceId: "StopService"
Filename: "{sys}\sc.exe"; Parameters: "delete obhod"; Flags: runhidden; RunOnceId: "DeleteService"
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM Obhod.exe"; Flags: runhidden; RunOnceId: "KillApp"
Filename: "{sys}\WindowsPowerShell\v1.0\powershell.exe"; Parameters: "-NoProfile -Command ""Get-Process winws -ErrorAction SilentlyContinue | Where-Object {{ $_.Path -like '{app}\*' } | Stop-Process -Force"""; Flags: runhidden; RunOnceId: "KillWinws"

[UninstallDelete]
Type: filesandordirs; Name: "{app}"

[Code]
var
  CheckPage: TOutputMsgMemoWizardPage;

function RunHidden(const FileName, Params: String): Integer;
begin
  if not Exec(FileName, Params, '', SW_HIDE, ewWaitUntilTerminated, Result) then
    Result := -1;
end;

function ServiceExists(const Name: String): Boolean;
begin
  Result := RunHidden(ExpandConstant('{sys}\sc.exe'), 'query "' + Name + '"') = 0;
end;

function ProcessRunning(const Image: String): Boolean;
begin
  Result := RunHidden(ExpandConstant('{cmd}'),
    '/C tasklist /NH /FI "IMAGENAME eq ' + Image + '" | find /I "' + Image + '" >nul') = 0;
end;

function RunningOf(const Images: array of String): String;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to GetArrayLength(Images) - 1 do
    if ProcessRunning(Images[I]) then
    begin
      if Result <> '' then Result := Result + ', ';
      Result := Result + Images[I];
    end;
end;

function SystemReport: String;
var
  Found: String;
  Warnings: Integer;
begin
  Warnings := 0;
  Result := '✓ Windows 10/11, 64-bit' + #13#10 + '✓ Права администратора есть' + #13#10;

  if ServiceExists('obhod') then
    Result := Result + '✓ Найдена служба автозапуска прошлой версии Обхода — будет остановлена и обновлена' + #13#10;

  Found := '';
  if ServiceExists('zapret') then Found := 'zapret';
  if ServiceExists('GoodbyeDPI') then
  begin
    if Found <> '' then Found := Found + ', ';
    Found := Found + 'GoodbyeDPI';
  end;
  if Found <> '' then
  begin
    Result := Result + '⚠ Установлена служба другого обхода: ' + Found + '.' + #13#10 +
      '    Два обхода одновременно мешают друг другу. Удалите её (для zapret от Flowseal —' + #13#10 +
      '    service.bat → Remove Services) или остановите перед запуском Обхода.' + #13#10;
    Warnings := Warnings + 1;
  end;

  Found := RunningOf(['winws.exe', 'goodbyedpi.exe']);
  if Found <> '' then
  begin
    Result := Result + '⚠ Сейчас запущен ' + Found + ' (другой обход или прошлая версия Обхода).' + #13#10 +
      '    Если это не Обход — закройте его.' + #13#10;
    Warnings := Warnings + 1;
  end;

  Found := RunningOf(['FlClash.exe', 'FlClashCore.exe', 'Happ.exe', 'v2rayN.exe', 'nekoray.exe',
                      'Hiddify.exe', 'sing-box.exe', 'xray.exe', 'AmneziaVPN.exe', 'clash-verge.exe']);
  if Found <> '' then
  begin
    Result := Result + '⚠ Запущен VPN/прокси-клиент: ' + Found + '.' + #13#10 +
      '    Установке он не мешает, но перед автоподбором стратегий его нужно закрыть.' + #13#10;
    Warnings := Warnings + 1;
  end;

  Result := Result + 'ℹ Антивирус может ругаться на WinDivert/winws.exe — это драйвер перехвата пакетов,' + #13#10 +
    '    на котором работает zapret. При блокировке добавьте папку программы в исключения.' + #13#10 + #13#10;
  if Warnings = 0 then
    Result := Result + 'Всё готово к установке.'
  else
    Result := Result + 'Установку можно продолжить, но лучше сначала разобраться с пунктами ⚠.';
end;

procedure InitializeWizard;
begin
  CheckPage := CreateOutputMsgMemoPage(wpWelcome, 'Проверка системы',
    'Перед установкой проверяем, что ничего не помешает обходу.',
    'Результаты проверки:', '');
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = CheckPage.ID then
    CheckPage.RichEditViewer.Lines.Text := SystemReport;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  // Free locked files when upgrading: autostart service, the app itself and its winws.
  if ServiceExists('obhod') then
    RunHidden(ExpandConstant('{sys}\sc.exe'), 'stop obhod');
  RunHidden(ExpandConstant('{sys}\taskkill.exe'), '/F /IM Obhod.exe');
  RunHidden(ExpandConstant('{sys}\WindowsPowerShell\v1.0\powershell.exe'),
    '-NoProfile -Command "Get-Process winws -ErrorAction SilentlyContinue | Where-Object { $_.Path -like ''' +
    ExpandConstant('{app}') + '\*'' } | Stop-Process -Force"');
  Result := '';
end;
