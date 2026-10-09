"""Run the generated PowerShell with simulated Windows processes and real files."""
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

import pytest

from conxml.updates import Release, UpdateError, Updater, generar_script_actualizador


@pytest.mark.parametrize('scenario', [
    'child_window', 'root_window', 'root_exited', 'no_window', 'start_failure',
    'rollback_locked', 'rollback_failed', 'backup_failed', 'copy_failed',
    'missing_cli', 'version_mismatch', 'bootloader_busy',
])
def test_powershell_recovery(tmp_path, scenario):
    shell = shutil.which('powershell.exe') or shutil.which('pwsh')
    if not shell:
        pytest.skip('Requiere PowerShell (Windows PowerShell o pwsh)')
    target = tmp_path / "app [prueba]'á"
    target.mkdir()
    staging = tmp_path / 'staging'
    staging.mkdir()
    for name in ('conxml.exe', 'conxml-cli.exe'):
        (target / name).write_bytes(b'old ' + name.encode())
        (staging / name).write_bytes(b'new ' + name.encode())
    if scenario == 'missing_cli':
        (staging / 'conxml-cli.exe').unlink()
    backup = tmp_path / 'backup'
    log = tmp_path / 'update.log'
    script = generar_script_actualizador(
        tmp_path / 'update.ps1', parent_pid=0, target_dir=target,
        staging_dir=staging, backup_dir=backup, log_file=log,
    )
    syntax = subprocess.run(
        [shell, '-NoProfile', '-NonInteractive', '-Command',
         "$tokens=$null; $errors=$null; "
         "[System.Management.Automation.Language.Parser]::ParseFile($env:CONXML_TEST_SCRIPT, [ref]$tokens, [ref]$errors) | Out-Null; "
         "if ($errors.Count) { $errors | Out-String | Write-Output; exit 1 }"],
        env={**os.environ, 'CONXML_TEST_SCRIPT': str(script)},
        capture_output=True, timeout=20,
    )
    assert syntax.returncode == 0, syntax.stdout + syntax.stderr
    content = script.read_text(encoding='utf-8-sig')
    # Only replace the presentation layer; exercise the real transaction functions.
    start = content.index('try {\n    Add-Type')
    end = content.index('function Set-UpdateStatus', start)
    content = content[:start] + '$form = $null\n' + content[end:]
    mocks = r'''
$script:scenario = 'SCENARIO'
$script:restoreAttempts = 0
$script:root = [pscustomobject]@{Id=100; StartTime=(Get-Date).AddSeconds(-2); Handle=1; HasExited=$false; MainWindowHandle=[IntPtr]0}
$script:child = [pscustomobject]@{Id=101; StartTime=(Get-Date).AddSeconds(-1); Handle=2; HasExited=$false; MainWindowHandle=[IntPtr]0}
if ($scenario -eq 'root_exited') { $root.HasExited = $true; $child.MainWindowHandle = [IntPtr]42 }
if ($scenario -eq 'child_window') { $child.MainWindowHandle = [IntPtr]42 }
if ($scenario -eq 'root_window') { $root.MainWindowHandle = [IntPtr]42 }
foreach ($p in @($root, $child)) {
    $p | Add-Member ScriptMethod Refresh {}
    $p | Add-Member ScriptMethod Kill { $this.HasExited = $true; Write-Log "KILL $($this.Id)" }
    $p | Add-Member ScriptMethod WaitForExit { param($ms) return $this.HasExited }
}
function Start-Sleep { param($Milliseconds) }
function Get-Date { (Microsoft.PowerShell.Utility\Get-Date).AddSeconds($script:clock++ * 61) }
$script:clock = 0
function Get-FileHash { throw "Esta prueba no ofrece Get-FileHash" }
function Get-InstalledVersion { param($cliExe) if ($scenario -eq 'version_mismatch') { return 'conxml 0.0.1' }; return "conxml $ExpectedVersion" }
function Get-CimInstance {
    param($ClassName, $ErrorAction)
    if ($scenario -eq 'bootloader_busy') {
        [pscustomobject]@{ProcessId=88; ExecutablePath=(Join-Path $TargetDir 'conxml.exe')}
        return
    }
    [pscustomobject]@{ProcessId=101; ParentProcessId=100; ExecutablePath=$nuevoExe; CreationDate=$child.StartTime}
    # An unrelated application must never count as success or be stopped.
    [pscustomobject]@{ProcessId=999; ParentProcessId=777; ExecutablePath=$nuevoExe; CreationDate=$child.StartTime}
}
function Get-Process {
    param($Id, $ErrorAction)
    if ($Id -eq 101) { return $child }
    throw "Unexpected process $Id"
}
function Start-Process {
    param($FilePath, $WorkingDirectory, [switch]$PassThru)
    if ($env:PYINSTALLER_RESET_ENVIRONMENT -ne '1') { throw 'Environment not reset' }
    if ($WorkingDirectory -ne $TargetDir) { throw 'Wrong working directory' }
    if ($PassThru) {
        if ($scenario -eq 'start_failure') { throw 'Launch failed' }
        return $root
    }
    Write-Log 'RELAUNCH'
}
function Copy-Item {
    param($LiteralPath, $Destination, [switch]$Force, $ErrorAction)
    if ($scenario -eq 'backup_failed' -and $Destination.StartsWith($BackupDir)) { throw 'Backup denied' }
    if ($scenario -eq 'copy_failed' -and $LiteralPath.StartsWith($StagingDir)) { throw 'Install locked' }
    if ($LiteralPath.StartsWith($BackupDir)) {
        $script:restoreAttempts++
        if ($scenario -eq 'rollback_failed') { throw 'Restore locked permanently' }
        if ($scenario -eq 'rollback_locked' -and $restoreAttempts -le 2) { throw 'Restore locked temporarily' }
        if ($script:launched.Count -gt 0 -and (-not $root.HasExited -or -not $child.HasExited)) { throw 'Live process during rollback' }
    }
    Microsoft.PowerShell.Management\Copy-Item -LiteralPath $LiteralPath -Destination $Destination -Force -ErrorAction Stop
}
'''.replace('SCENARIO', scenario)
    content = content.replace('Set-UpdateStatus "Cerrando ConXml', mocks + '\nSet-UpdateStatus "Cerrando ConXml', 1)
    script.write_text(content, encoding='utf-8-sig')
    result = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File', str(script)],
                            capture_output=True, timeout=30)
    output = (result.stdout + result.stderr).decode('utf-8', errors='replace')
    log_text = log.read_text(encoding='utf-8-sig') if log.exists() else ''
    success = scenario in ('root_window', 'child_window', 'root_exited')
    assert result.returncode == (0 if success else 1), output
    if success:
        assert (target / 'conxml.exe').read_bytes() == b'new conxml.exe'
        assert 'Actualización completada exitosamente' in log_text
        assert 'KILL' not in log_text
        assert not staging.exists()
        assert f'Ventana detectada en PID {100 if scenario == "root_window" else 101}' in log_text
    else:
        assert staging.exists()
        assert 'Actualización completada exitosamente' not in log_text
        if scenario in ('rollback_failed', 'backup_failed', 'missing_cli', 'bootloader_busy'):
            assert 'RELAUNCH' not in log_text
            if scenario in ('backup_failed', 'missing_cli', 'bootloader_busy'):
                assert (target / 'conxml.exe').read_bytes() == b'old conxml.exe'
        else:
            for name in ('conxml.exe', 'conxml-cli.exe'):
                assert (target / name).read_bytes() == b'old ' + name.encode()
            assert 'RELAUNCH' in log_text
        if scenario == 'rollback_locked':
            assert 'Copia bloqueada (2/30)' in log_text
            assert log_text.index('KILL 101') < log_text.index('KILL 100') < log_text.index('Rollback verificado')
    assert 'KILL 999' not in log_text
    if scenario not in ('backup_failed', 'missing_cli', 'bootloader_busy'):
        assert (backup / 'conxml.exe').read_bytes() == b'old conxml.exe'


@pytest.mark.parametrize('mode', ['ready', 'crashed', 'timeout'])
def test_helper_handshake_and_persistent_output(tmp_path, monkeypatch, mode):
    import conxml.updates as updates
    from types import SimpleNamespace

    cache = tmp_path / 'cache'
    cache.mkdir()
    archive = cache / 'update.zip'
    with zipfile.ZipFile(archive, 'w') as zipped:
        zipped.writestr('conxml.exe', b'new executable')
        zipped.writestr('conxml-cli.exe', b'new cli')
    data = archive.read_bytes()
    release = Release('0.3.0', 'https://example.com/update.zip', hashlib.sha256(data).hexdigest(), len(data), archive.name)
    updater = Updater(cache, current='0.2.0')
    monkeypatch.setattr(updates, 'Config', lambda: SimpleNamespace(logs_dir=tmp_path / 'logs'))
    monkeypatch.setattr(sys, 'platform', 'win32')
    monkeypatch.setattr(sys, 'frozen', True, raising=False)
    monkeypatch.setattr(updates.time, 'sleep', lambda _: None)
    ticks = iter([0, 16])
    monkeypatch.setattr(updates.time, 'monotonic', lambda: next(ticks))
    calls = []
    def popen(args, **kwargs):
        calls.append((args, kwargs))
        kwargs['stdout'].write(b'early PowerShell diagnostic\n')
        if mode == 'ready':
            next((cache / 'backup').iterdir()).joinpath('helper.ready').write_text('ready')
        return SimpleNamespace(returncode=1 if mode == 'crashed' else None, poll=lambda: 1 if mode == 'crashed' else None,
                               terminate=lambda: calls.append('terminated'), wait=lambda **kw: 0)
    monkeypatch.setattr(updates.subprocess, 'Popen', popen)
    if mode == 'ready':
        assert updater.apply_update(release, archive, target_dir=tmp_path / 'app').is_file()
    else:
        with pytest.raises(UpdateError, match='actualizador'):
            updater.apply_update(release, archive, target_dir=tmp_path / 'app')
    args, kwargs = calls[0]
    assert '-STA' in args
    assert kwargs['env']['PYINSTALLER_RESET_ENVIRONMENT'] == '1'
    assert kwargs['stdin'] == subprocess.DEVNULL
    assert kwargs['stderr'] == subprocess.STDOUT
    assert b'early PowerShell diagnostic' in (tmp_path / 'logs' / 'actualizacion-launcher.log').read_bytes()
    if mode == 'timeout':
        assert 'terminated' in calls


@pytest.mark.skipif(sys.platform != 'win32', reason='Requiere PyInstaller y PowerShell en Windows')
def test_frozen_windowed_launcher_starts_system_powershell(tmp_path):
    """Exercise the real PyInstaller onefile environment that the installed GUI uses."""
    import importlib.util

    if importlib.util.find_spec('PyInstaller') is None:
        pytest.skip('PyInstaller no está instalado')
    marker = tmp_path / 'helper.ready'
    script = tmp_path / 'probe.ps1'
    script.write_text(
        "Set-Content -LiteralPath '" + str(marker).replace("'", "''") + "' -Value ready -Encoding ascii\n",
        encoding='utf-8-sig',
    )
    probe = tmp_path / 'frozen_probe.py'
    probe.write_text(
        "from pathlib import Path\n"
        "import sys\n"
        "from conxml.windows_process import launch_powershell\n"
        "with Path(sys.argv[2]).open('ab', buffering=0) as output:\n"
        "    process = launch_powershell(Path(sys.argv[1]), Path(sys.argv[1]).parent, output)\n"
        "    raise SystemExit(process.wait(timeout=20))\n",
        encoding='utf-8',
    )
    package_root = Path(__file__).resolve().parents[1] / 'src'
    dist = tmp_path / 'dist'
    built = subprocess.run(
        [sys.executable, '-m', 'PyInstaller', '--onefile', '--noconsole', '--noconfirm',
         '--distpath', str(dist), '--workpath', str(tmp_path / 'work'),
         '--specpath', str(tmp_path / 'spec'), '--paths', str(package_root), str(probe)],
        capture_output=True, text=True, timeout=180,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    log = tmp_path / 'powershell.log'
    result = subprocess.run([str(dist / 'frozen_probe.exe'), str(script), str(log)],
                            capture_output=True, timeout=40)
    assert result.returncode == 0, log.read_bytes() if log.exists() else result.stderr
    assert marker.read_text(encoding='ascii').strip() == 'ready'
