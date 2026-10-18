import json
from types import SimpleNamespace
from uuid import uuid4

import pytest

from conxml import telemetria as t


def journal(tmp_path, clock, device=None):
    return t.Journal(tmp_path, device or str(uuid4()), wall=lambda: clock.wall, monotonic=lambda: clock.mono)


def test_monotonic_duration_and_queued_close_survive_offline_restart(tmp_path):
    clock=SimpleNamespace(wall=1800000000, mono=0)
    first=journal(tmp_path,clock)
    opened=first.payload()
    clock.mono=91;clock.wall-=10000
    closed=first.payload(closed=True)
    assert closed['sessions'][0]['elapsed_seconds']==91
    assert closed['sessions'][0]['ended_at']==1800000091
    clock.wall=1800000200
    second=journal(tmp_path,clock,first.device_id)
    pending=second.payload()
    assert len(pending['sessions'])==2
    old=next(s for s in pending['sessions'] if s['id']==opened['current_session_id'])
    assert old['state']=='closed' and old['elapsed_seconds']==91
    second.acknowledge({'sessions':[{'id':s['id'],'sequence':s['sequence']} for s in pending['sessions']], 'diagnostics':[]}, pending)
    assert len(second.payload()['sessions'])==1


def test_unexpected_exit_preserves_last_observation_not_whole_offline_gap(tmp_path):
    clock=SimpleNamespace(wall=1800000000,mono=0)
    first=journal(tmp_path,clock)
    clock.mono=300;first.payload()
    clock.wall+=86400;clock.mono=0
    second=journal(tmp_path,clock,first.device_id)
    old=second.payload()['sessions'][0]
    assert old['state']=='interrupted'
    assert old['elapsed_seconds']==300
    assert old['ended_at']==1800000300


def test_error_privacy_and_acknowledgement_retries(tmp_path,monkeypatch):
    clock=SimpleNamespace(wall=1800000000,mono=0)
    j=journal(tmp_path,clock)
    monkeypatch.setattr(t,'_journal',j)
    @t.technical_diagnostic('update_download_failed')
    def fail():
        raise ValueError('SECRET RFC /private/customer.xml TOKEN')
    with pytest.raises(ValueError):fail()
    payload=j.payload()
    assert payload['diagnostics'][0]['exception_type']=='ValueError'
    assert 'SECRET' not in json.dumps(payload) and 'SECRET' not in j.path.read_text()
    j.acknowledge({'sessions':[], 'diagnostics':[str(uuid4())]},payload)
    assert len(j.payload()['diagnostics'])==1
    j.acknowledge({'sessions':[], 'diagnostics':[payload['diagnostics'][0]['id']]},payload)
    assert not j.payload()['diagnostics']


def test_history_is_bounded_and_identity_changes_drop_old_reports(tmp_path):
    clock=SimpleNamespace(wall=1800000000,mono=0)
    j=journal(tmp_path,clock)
    for _ in range(70):j.error('operation_failed',Exception('private'))
    for _ in range(40):
        j.close();j=journal(tmp_path,clock,j.device_id)
    assert len(j.sessions)==30 and len(j.diagnostics)==50
    assert len(j.payload()['sessions'])==5 and len(j.payload()['diagnostics'])==5
    other=journal(tmp_path,clock)
    assert len(other.sessions)==1 and not other.diagnostics


@pytest.mark.parametrize('raw',['broken','{}','{"sessions": null}','[1]'])
def test_corrupt_journal_never_changes_license_or_prevents_open(tmp_path,raw):
    (tmp_path/'telemetry.json').write_text(raw)
    j=journal(tmp_path,SimpleNamespace(wall=1800000000,mono=0))
    assert len(j.payload()['sessions'])==1


def test_update_helper_failure_is_reported_once_without_uploading_log(tmp_path):
    logs=tmp_path/'logs';logs.mkdir()
    (logs/'actualizacion.log').write_text('ERROR de actualización: PRIVATE PATH XML TOKEN\nRollback verificado.')
    clock=SimpleNamespace(wall=1800000000,mono=0)
    j=journal(tmp_path,clock)
    j.capture_update_result(logs);j.capture_update_result(logs)
    assert len(j.diagnostics)==1
    assert j.diagnostics[0]['code']=='update_install_failed'
    assert 'PRIVATE' not in j.path.read_text()
    j.close();second=journal(tmp_path,clock,j.device_id)
    second.capture_update_result(logs)
    assert len(second.diagnostics)==1
    with (logs/'actualizacion.log').open('a') as out:out.write('\nActualización completada exitosamente.')
    second.capture_update_result(logs)
    assert len(second.diagnostics)==1


def test_local_storage_failure_does_not_prevent_telemetry_or_change_permission(tmp_path,monkeypatch):
    def fail(*args):raise OSError('disk')
    monkeypatch.setattr(t,'save_record',fail)
    j=journal(tmp_path,SimpleNamespace(wall=1800000000,mono=0))
    j.error('operation_failed',ValueError('private'))
    assert j.payload()['diagnostics'][0]['exception_type']=='ValueError'
