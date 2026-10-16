import json
from pathlib import Path
import threading
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
import requests

from conxml import monitoreo


def configuration():
    return {"schema": 1, "service_url": "https://monitor.example", "device_id": str(uuid4()),
            "alias": "Oficina", "device_token": "test-only-" + "x" * 32}


def test_import_keeps_secret_in_keyring_and_metadata_outside_fiscal_data(tmp_path):
    config = configuration()
    source, destination = tmp_path / "import.json", tmp_path / "settings.json"
    source.write_text(json.dumps(config))
    with patch.object(monitoreo.keyring, "get_password", return_value=None), patch.object(monitoreo.keyring, "set_password") as save:
        clean = monitoreo.import_configuration(source, destination)
    save.assert_called_once_with(monitoreo.SERVICE, config["device_id"], config["device_token"])
    assert clean["enabled"] is True
    assert config["device_token"] not in destination.read_text()
    assert "device_token" not in json.loads(destination.read_text())
    assert monitoreo.validate_record(json.loads(destination.read_text())) == clean


def test_failed_keyring_does_not_activate_reporting_or_expose_secret(tmp_path):
    config = configuration()
    source, destination = tmp_path / "import.json", tmp_path / "settings.json"
    source.write_text(json.dumps(config))
    with patch.object(monitoreo.keyring, "get_password", side_effect=RuntimeError(config["device_token"])):
        with pytest.raises(monitoreo.MonitoringError) as error:
            monitoreo.import_configuration(source, destination)
    assert config["device_token"] not in str(error.value)
    assert not destination.exists()


def test_failed_settings_write_restores_existing_keyring_credential(tmp_path):
    config = configuration()
    source = tmp_path / "import.json"
    source.write_text(json.dumps(config))
    with patch.object(monitoreo.keyring, "get_password", return_value="previous"), patch.object(monitoreo.keyring, "set_password") as save, patch.object(monitoreo, "save_record", side_effect=OSError):
        with pytest.raises(monitoreo.MonitoringError):
            monitoreo.import_configuration(source, tmp_path / "settings.json")
    assert save.call_args_list[-1].args == (monitoreo.SERVICE, config["device_id"], "previous")


@pytest.mark.parametrize("url", ["http://remote.example", "https://u:password@host", "https://host?token=secret", "https://host/other", None])
def test_insecure_or_malformed_import_cannot_start_reporting(url):
    record = configuration()
    record["service_url"] = url
    with pytest.raises(monitoreo.MonitoringError):
        monitoreo.validate_record(record)


def test_unconfigured_or_disabled_installation_never_accesses_network_or_keyring(tmp_path):
    destination = tmp_path / "settings.json"
    with patch.object(monitoreo, "config_path", return_value=destination), patch.object(monitoreo.keyring, "get_password") as keyring, patch.object(monitoreo.requests, "post") as post:
        controller = monitoreo.MonitoringController()
        assert controller.reporter is None
        record = configuration()
        del record["device_token"]
        record["enabled"] = False
        destination.write_text(json.dumps(record))
        controller.reload()
        keyring.assert_not_called()
        post.assert_not_called()


def test_report_payload_contains_only_technical_allowlist_and_disables_redirects():
    config = configuration()
    reporter = monitoreo.PresenceReporter(monitoreo.ReporterConfig(config["service_url"], config["device_id"], config["device_token"]))
    response = Mock()
    response.status_code = 200
    with patch.object(monitoreo.requests, "post") as post:
        post.return_value.__enter__ = Mock(return_value=response)
        post.return_value.__exit__ = Mock(return_value=False)
        assert reporter._send("running")
    kwargs = post.call_args.kwargs
    assert set(kwargs["json"]) == {"session_id", "sequence", "version", "os", "state"}
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == (2, 3)
    assert config["device_token"] not in repr(reporter.config)


def test_network_outage_does_not_raise_and_revocation_stops_retries():
    config = configuration()
    reporter = monitoreo.PresenceReporter(monitoreo.ReporterConfig(config["service_url"], config["device_id"], config["device_token"]))
    with patch.object(monitoreo.requests, "post", side_effect=requests.ConnectionError):
        assert reporter._send("running") is False
    response = Mock(status_code=401)
    with patch.object(monitoreo.requests, "post") as post:
        post.return_value.__enter__ = Mock(return_value=response)
        post.return_value.__exit__ = Mock(return_value=False)
        reporter._send("running")
    assert reporter.stopped.is_set()


def test_stop_sends_closed_after_in_flight_heartbeat_and_never_concurrently():
    config = configuration()
    reporter = monitoreo.PresenceReporter(monitoreo.ReporterConfig(config["service_url"], config["device_id"], config["device_token"]))
    started, release = threading.Event(), threading.Event()
    states = []
    def send(state):
        states.append(state)
        if state == "running":
            started.set()
            release.wait(2)
    reporter._send = send
    reporter.start()
    assert started.wait(2)
    reporter.stop()
    release.set()
    reporter.thread.join(2)
    assert states == ["running", "closed"]
    assert not reporter.thread.is_alive()


def test_block_persists_across_restart_and_only_newer_policy_unlocks(tmp_path):
    record = configuration()
    path = tmp_path / "control.json"
    state = monitoreo.ControlState(record, path)
    state.apply_policy({"revision": 1, "blocked": True})
    assert state.acknowledgements()["control_ack"] == 0
    state.acknowledge_policy()
    reopened = monitoreo.ControlState(record, path)
    assert reopened.blocked is True
    assert reopened.acknowledgements()["control_ack"] == 1
    reopened.apply_policy({"revision": 0, "blocked": False})
    assert reopened.blocked is True
    reopened.apply_policy({"revision": 2, "blocked": False})
    assert reopened.blocked is False
    assert monitoreo.ControlState(record, path).blocked is False


def test_message_confirmations_survive_outage_and_only_clear_after_successful_delivery(tmp_path):
    record = configuration()
    path = tmp_path / "control.json"
    state = monitoreo.ControlState(record, path)
    state.apply_policy({"revision": 0, "blocked": False})
    identifier = str(uuid4())
    state.acknowledge_messages([identifier])
    reopened = monitoreo.ControlState(record, path)
    assert reopened.acknowledgements()["message_acks"] == [identifier]
    config = monitoreo.ReporterConfig(record["service_url"], record["device_id"], record["device_token"])
    reporter = monitoreo.PresenceReporter(config, control_state=reopened)
    with patch.object(monitoreo.requests, "post", side_effect=requests.ConnectionError):
        assert reporter._send("running") is False
    assert reopened.pending_acks == [identifier]
    response = Mock(status_code=200)
    response.iter_content.return_value = [json.dumps({"ok": True, "control": {"revision": 0, "blocked": False}, "messages": []}).encode()]
    with patch.object(monitoreo.requests, "post") as post:
        post.return_value.__enter__ = Mock(return_value=response)
        post.return_value.__exit__ = Mock(return_value=False)
        assert reporter._send("running")
    assert reopened.pending_acks == []
    assert identifier in monitoreo.ControlState(record, path).seen


def test_control_response_cannot_execute_commands_or_apply_malformed_policy(tmp_path):
    record = configuration()
    state = monitoreo.ControlState(record, tmp_path / "control.json")
    state.apply_policy({"revision": 1, "blocked": True})
    sink = Mock()
    reporter = monitoreo.PresenceReporter(monitoreo.ReporterConfig(record["service_url"], record["device_id"], record["device_token"]), control_state=state, on_control=sink)
    for result in ({"ok": True, "control": {"revision": True, "blocked": False}, "messages": []},
                   {"ok": True, "command": "unblock", "messages": []},
                   {"ok": True, "control": {"revision": 2, "blocked": False}, "messages": [{"id": "bad", "text": "malformed"}]}):
        response = Mock(status_code=200)
        response.iter_content.return_value = [json.dumps(result).encode()]
        with patch.object(monitoreo.requests, "post") as post:
            post.return_value.__enter__ = Mock(return_value=response)
            post.return_value.__exit__ = Mock(return_value=False)
            assert reporter._send("running") is False
    assert state.blocked
    sink.assert_not_called()


def test_failed_cache_write_does_not_acknowledge_or_replace_policy(tmp_path):
    state = monitoreo.ControlState(configuration(), tmp_path / "control.json")
    state.apply_policy({"revision": 1, "blocked": True})
    with patch.object(monitoreo, "save_record", side_effect=OSError):
        with pytest.raises(OSError):
            state.apply_policy({"revision": 2, "blocked": False})
    assert state.blocked
    assert state.revision == 1
    assert state.applied_revision == 0


def test_v2_payload_advertises_control_support_without_fiscal_data(tmp_path):
    record = configuration()
    state = monitoreo.ControlState(record, tmp_path / "control.json")
    response = Mock(status_code=200)
    response.iter_content.return_value = [b'{"ok":true,"control":{"revision":0,"blocked":false},"messages":[]}']
    sink = Mock()
    reporter = monitoreo.PresenceReporter(monitoreo.ReporterConfig(record["service_url"], record["device_id"], record["device_token"]), control_state=state, on_control=sink)
    with patch.object(monitoreo.requests, "post") as post:
        post.return_value.__enter__ = Mock(return_value=response)
        post.return_value.__exit__ = Mock(return_value=False)
        assert reporter._send("running")
    assert set(post.call_args.kwargs["json"]) == {"session_id", "sequence", "version", "os", "state", "protocol", "control_ack", "message_acks"}
    assert post.call_args.kwargs["json"]["protocol"] == 2
    sink.assert_called_once()


def test_corrupted_access_cache_does_not_silently_unlock(tmp_path):
    record = configuration()
    path = tmp_path / "control.json"
    path.write_text("broken")
    with pytest.raises(monitoreo.MonitoringError):
        monitoreo.ControlState(record, path)
    recovery = monitoreo.ControlState(record, path, recover=True)
    assert recovery.blocked
    recovery.apply_policy({"revision": 2, "blocked": False})
    assert monitoreo.ControlState(record, path).blocked is False


def test_old_reporter_cannot_overwrite_cache_after_installation_changes(tmp_path):
    first, second = configuration(), configuration()
    path = tmp_path / "control.json"
    old = monitoreo.ControlState(first, path)
    old.apply_policy({"revision": 1, "blocked": True})
    old.deactivate()
    new = monitoreo.ControlState(second, path)
    new.apply_policy({"revision": 2, "blocked": False})
    with pytest.raises(monitoreo.MonitoringError):
        old.acknowledge_messages([str(uuid4())])
    assert monitoreo.ControlState(second, path).blocked is False
    assert json.loads(path.read_text())["identity"]["device_id"] == second["device_id"]
