#ifndef AppVersion
  #error AppVersion es obligatorio
#endif
[Setup]
AppId={{E6F86B49-B895-4A95-92FA-3BB737511230}
AppName=ConXml
AppVersion={#AppVersion}
AppPublisher=ConXml
DefaultDirName={localappdata}\Programs\ConXml
DefaultGroupName=ConXml
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir=..\dist\installer
OutputBaseFilename=ConXml-Setup-{#AppVersion}-windows-x64
SetupIconFile=..\src\conxml\ui\assets\logo_conxml.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
DisableProgramGroupPage=yes
AppMutex=ConXmlApplication
CloseApplications=no
RestartApplications=no
UninstallDisplayIcon={app}\conxml.exe
[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
[Tasks]
Name: "desktopicon"; Description: "Crear acceso directo en el escritorio"
[Files]
Source: "..\dist\conxml.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\dist\conxml-cli.exe"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\ConXml"; Filename: "{app}\conxml.exe"
Name: "{autodesktop}\ConXml"; Filename: "{app}\conxml.exe"; Tasks: desktopicon
[Run]
Filename: "{app}\conxml.exe"; Description: "Abrir ConXml"; Flags: nowait postinstall skipifsilent
; No se borran datos, XML ni respaldos al desinstalar. La app crea sus carpetas.
