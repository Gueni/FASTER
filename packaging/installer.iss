; -------------------------------------------------------------------------------
;                         _________   _____________________
;                        / ____/   | / ___/_  __/ ____/ __ \
;                       / /_  / /| | \__ \ / / / __/ / /_/ /
;                      / __/ / ___ |___/ // / / /___/ _, _/
;                     /_/   /_/  |_/____//_/ /_____/_/ |_|
;
; Name:        installer.iss
; Purpose:     Inno Setup 6 installer for FASTER (built by packaging/build.py).
;
; Author:      Mohamed Gueni ( mohamedgueni@outlook.com)
;
; Created:     07/11/2026
; Licence:     Refer to the LICENSE file
; -------------------------------------------------------------------------------
; -------------------------------------------------------------------------------
;
; The program goes to the install folder (read-only); the user's work goes to
; the data folder chosen on the "Data folder" page. The choice is written to
; %APPDATA%\FASTER\preferences.json, which the app reads. Uninstalling never
; deletes the data folder.

#ifndef AppVersion
  #define AppVersion "3.1.1"
#endif
#define AppName      "FASTER"
#define AppLongName  "FASTER - Failure Analysis, Simulation, Testing and Evaluation Report"
#define AppPublisher "Mohamed Gueni"
#define AppExe       "FASTER.exe"
#ifndef SrcDir
  #define SrcDir     "..\dist\FASTER"
#endif

[Setup]
AppId={{8B3139E9-754D-4C0E-B3CC-C44D04E530C7}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppComments={#AppLongName}
VersionInfoVersion={#AppVersion}
VersionInfoDescription={#AppName} Setup
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
; per-user install without admin rights by default; "Install for all users" is offered
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir=..\dist\installer
OutputBaseFilename={#AppName}-{#AppVersion}-setup
SetupIconFile=..\build\faster.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName} {#AppVersion}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
ChangesEnvironment=yes
ChangesAssociations=yes
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "openwith";    Description: "Add FASTER to ""Open with"" for LTspice schematics (.asc)"; GroupDescription: "Integration:"
Name: "addtopath";   Description: "Add faster-cli to the PATH (command line use)"; GroupDescription: "Integration:"; Flags: unchecked

[Files]
Source: "{#SrcDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[InstallDelete]
; files of a previous version that the new build no longer ships
Type: filesandordirs; Name: "{app}\_internal"

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"; Comment: "{#AppLongName}"
Name: "{autodesktop}\{#AppName}";  Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; "Open with" entry only - the default program for .asc (LTspice) is not changed
Root: HKA; Subkey: "Software\Classes\.asc\OpenWithProgids"; ValueType: string; ValueName: "FASTER.asc"; ValueData: ""; Flags: uninsdeletevalue; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\FASTER.asc"; ValueType: string; ValueName: ""; ValueData: "LTspice schematic (FASTER)"; Flags: uninsdeletekey; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\FASTER.asc\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\FASTER.asc\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" --gui ""%1"""; Tasks: openwith
Root: HKA; Subkey: "Software\Classes\Applications\{#AppExe}\SupportedTypes"; ValueType: string; ValueName: ".asc"; ValueData: ""; Flags: uninsdeletekey; Tasks: openwith

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /IM {#AppExe} /F"; Flags: runhidden; RunOnceId: "KillFaster"

[Code]
var
  DataPage: TInputDirWizardPage;

function PrefsFile(): String;
begin
  Result := ExpandConstant('{userappdata}\FASTER\preferences.json');
end;

{ data_dir stored by an earlier install or by the app, '' if none }
function ExistingDataDir(): String;
var
  Text: AnsiString;
  S: String;
  P: Integer;
begin
  Result := '';
  if not LoadStringFromFile(PrefsFile(), Text) then
    exit;
  S := String(Text);
  P := Pos('"data_dir"', S);
  if P = 0 then
    exit;
  Delete(S, 1, P + Length('"data_dir"') - 1);
  P := Pos('"', S);
  if P = 0 then
    exit;
  Delete(S, 1, P);
  P := Pos('"', S);
  if P = 0 then
    exit;
  S := Copy(S, 1, P - 1);
  StringChangeEx(S, '\\', '\', True);
  Result := S;
end;

procedure InitializeWizard();
var
  Current: String;
begin
  DataPage := CreateInputDirPage(wpSelectDir, 'Data folder',
    'Where should FASTER keep your work?',
    'Analysis results, example circuits and config.json are stored in this folder. ' +
    'It is kept when FASTER is updated or uninstalled and can be changed later in Settings.' + #13#10#13#10 +
    'Choose a folder outside the program folder, then click Next.',
    False, 'FASTER');
  DataPage.Add('');
  Current := ExistingDataDir();
  if Current = '' then
    Current := ExpandConstant('{userdocs}\FASTER');
  DataPage.Values[0] := Current;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
var
  App, Data: String;
begin
  Result := True;
  if CurPageID = DataPage.ID then
  begin
    App  := AddBackslash(Lowercase(WizardDirValue()));
    Data := AddBackslash(Lowercase(DataPage.Values[0]));
    if Pos(App, Data) = 1 then
    begin
      MsgBox('The data folder must be outside the program folder:' + #13#10 + WizardDirValue(), mbError, MB_OK);
      Result := False;
    end;
  end;
end;

function JsonEscape(S: String): String;
begin
  Result := S;
  StringChangeEx(Result, '\', '\\', True);
  StringChangeEx(Result, '"', '\"', True);
end;

procedure SavePreferences();
var
  Data: String;
begin
  Data := RemoveBackslashUnlessRoot(DataPage.Values[0]);
  ForceDirectories(Data);
  ForceDirectories(ExtractFileDir(PrefsFile()));
  { preferences.json only holds the data folder; the GUI keeps its other settings in the registry }
  SaveStringToFile(PrefsFile(), '{' + #13#10 + '  "data_dir": "' + JsonEscape(Data) + '"' + #13#10 + '}' + #13#10, False);
end;

{ ---- PATH (user or machine, matching the install mode) ---- }
function PathRoot(): Integer;
begin
  if IsAdminInstallMode() then Result := HKEY_LOCAL_MACHINE else Result := HKEY_CURRENT_USER;
end;

function PathKey(): String;
begin
  if IsAdminInstallMode() then
    Result := 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment'
  else
    Result := 'Environment';
end;

procedure AddToPath(Dir: String);
var
  Paths: String;
begin
  if not RegQueryStringValue(PathRoot(), PathKey(), 'Path', Paths) then
    Paths := '';
  if Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Paths) + ';') > 0 then
    exit;
  if (Paths <> '') and (Copy(Paths, Length(Paths), 1) <> ';') then
    Paths := Paths + ';';
  RegWriteExpandStringValue(PathRoot(), PathKey(), 'Path', Paths + Dir);
end;

procedure RemoveFromPath(Dir: String);
var
  Paths: String;
  P: Integer;
begin
  if not RegQueryStringValue(PathRoot(), PathKey(), 'Path', Paths) then
    exit;
  Paths := ';' + Paths + ';';
  P := Pos(';' + Uppercase(Dir) + ';', Uppercase(Paths));
  if P = 0 then
    exit;
  Delete(Paths, P, Length(Dir) + 1);
  Paths := Copy(Paths, 2, Length(Paths) - 2);
  RegWriteExpandStringValue(PathRoot(), PathKey(), 'Path', Paths);
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    SavePreferences();
    if WizardIsTaskSelected('addtopath') then
      AddToPath(ExpandConstant('{app}'));
  end;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}'));
end;
