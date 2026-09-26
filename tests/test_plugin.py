"""Indigo boundary tests with a stateful fake bridge, no live sensor changes."""
import copy
import importlib.util
import json
import logging
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
SERVER = ROOT / 'Ruuvi Gateway.indigoPlugin/Contents/Server Plugin'
sys.path.insert(0, str(SERVER))


class FakeDevice:
    def __init__(self, ident, address, name):
        self.id, self.address, self.name = ident, address, name
        self.enabled = True
        self.states = {'sensorValue': 0}
        for state in ET.parse(SERVER / 'Devices.xml').findall('.//State'):
            self.states[state.attrib['id']] = {'Number': 0, 'Boolean': False, 'String': ''}[state.findtext('ValueType')]
        self.writes = []
        self.fail = False
        self.error = None

    def updateStatesOnServer(self, rows):
        if self.fail:
            raise RuntimeError('bridge unavailable')
        for row in rows:
            if row['key'] not in self.states:
                raise ValueError('undefined Indigo state: ' + row['key'])
            self.states[row['key']] = row['value']
        self.writes.append(copy.deepcopy(rows))

    def setErrorStateOnServer(self, value):
        self.error = value

    def updateStateImageOnServer(self, value):
        self.image = value

    def stateListOrDisplayStateIdChanged(self):
        pass


class FakeDevices(dict):
    def iter(self, selector):
        return iter(list(self.values()))


class Base:
    class StopThread(Exception):
        pass

    def __init__(self, plugin_id, name, version, prefs):
        self.pluginId = plugin_id
        self.pluginPrefs = prefs
        self.logger = logging.getLogger('ruuvi-test')


class PluginTests(unittest.TestCase):
    def setUp(self):
        self.devices = FakeDevices()
        def create(**kw):
            dev = FakeDevice(len(self.devices) + 1, kw['address'], kw['name'])
            self.devices[dev.id] = dev
            return dev
        self.fake = types.SimpleNamespace(PluginBase=Base, Dict=dict, devices=self.devices,
                                          device=types.SimpleNamespace(create=create),
                                          kProtocol=types.SimpleNamespace(Plugin='plugin'),
                                          kStateImageSel=types.SimpleNamespace(TemperatureSensorOn='on', SensorOff='off'))
        with patch.dict(sys.modules, {'indigo': self.fake}):
            spec = importlib.util.spec_from_file_location('tested_plugin', SERVER / 'plugin.py')
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        self.plugin = mod.Plugin('com.berkinet.indigoplugin.ruuvi', 'Ruuvi', '2026.1.0', {})
        self.doc = json.loads((ROOT / 'tests/fixtures/decoded-http-anonymized.json').read_text())
        self.now = self.doc['data']['timestamp']
        self.plugin._now = lambda: self.now

    def send(self, doc=None, method='POST', body=None):
        return self.plugin.receive(types.SimpleNamespace(props={
            'incoming_request_method': method,
            'request_body': body if body is not None else json.dumps(doc or self.doc)}))

    def test_creates_two_native_sensors_and_converts_pressure_only(self):
        self.assertEqual(self.send()['status'], 200)
        self.assertEqual(len(self.devices), 2)
        d = self.devices[1]
        self.assertEqual(d.states['sensorValue'], 2.47)
        self.assertEqual(d.states['pressure'], 1004.91)
        self.assertEqual(d.states['voltage'], 2.967)
        self.assertEqual(d.states['accelX'], -0.1)
        self.assertFalse(d.states['stale'])
        self.assertIsNone(d.error)

    def test_duplicate_does_not_rewrite_measurements_or_rename(self):
        self.send()
        d = self.devices[1]
        d.name = 'Chosen refrigerator name'
        d.writes.clear()
        self.now += 30
        result = self.send()
        self.assertEqual(json.loads(result['content'])['duplicates'], 2)
        self.assertEqual(len(self.devices), 2)
        self.assertEqual(d.name, 'Chosen refrigerator name')
        keys = {r['key'] for rows in d.writes for r in rows}
        self.assertNotIn('sensorValue', keys)
        self.assertNotIn('temperature', keys)
        self.assertIn('lastHeard', keys)

    def test_missing_temperature_marks_unavailable_without_zero(self):
        self.send()
        d = self.devices[1]
        next(iter(self.doc['data']['tags'].values()))['temperature'] = None
        self.send()
        self.assertEqual(d.states['sensorValue'], 2.47)
        self.assertFalse(d.states['temperatureAvailable'])
        self.assertEqual(d.error, 'Temperature unavailable')
        self.assertFalse(d.states['stale'])

    def test_stale_recovers_with_unchanged_sequence_and_new_reception(self):
        self.send()
        self.now += 400
        for d in self.devices.values():
            self.plugin._check_stale(d)
            self.assertTrue(d.states['stale'])
        self.doc['data']['timestamp'] = self.now
        for tag in self.doc['data']['tags'].values():
            tag['timestamp'] = self.now - 1
        result = self.send()
        self.assertEqual(json.loads(result['content'])['duplicates'], 2)
        self.assertTrue(all(not d.states['stale'] for d in self.devices.values()))

    def test_restart_reuses_devices_and_tracking(self):
        self.send()
        plugin = type(self.plugin)(self.plugin.pluginId, 'Ruuvi', '2026.1.0', {})
        plugin._now = lambda: self.now + 10
        self.plugin = plugin
        for d in self.devices.values():
            self.plugin.deviceStartComm(d)
        self.assertEqual(json.loads(self.send()['content'])['duplicates'], 2)
        self.assertEqual(len(self.devices), 2)

    def test_invalid_requests_no_device_side_effects(self):
        for expected, opts in [(405, {'method':'GET'}), (400, {'body':'bad'}),
                               (413, {'body':' '*262145})]:
            self.assertEqual(self.send(**opts)['status'], expected)
        self.assertFalse(self.devices)

    def test_full_envelope_validated_before_creating_any_device(self):
        self.doc['data']['tags']['bad-mac'] = {}
        self.assertEqual(self.send()['status'], 400)
        self.assertFalse(self.devices)

    def test_allowlist_disabled_discovery_and_disabled_device(self):
        self.plugin.pluginPrefs['gatewayMac'] = 'AA:BB:CC:DD:EE:99'
        self.assertEqual(self.send()['status'], 403)
        self.doc['data']['tags'] = {}
        self.assertEqual(self.send()['status'], 403)
        self.setUp()
        self.plugin.pluginPrefs['autoCreate'] = False
        self.assertEqual(self.send()['status'], 200)
        self.assertFalse(self.devices)
        self.plugin.pluginPrefs['autoCreate'] = True
        self.send()
        self.devices[1].enabled = False
        before = copy.deepcopy(self.devices[1].states)
        self.now += 30
        self.send()
        self.assertEqual(self.devices[1].states, before)

    def test_state_write_failure_returns_retryable_failure_and_preserves_tracking(self):
        self.send()
        d = self.devices[1]
        before = copy.deepcopy(d.states)
        d.fail = True
        self.now += 30
        with self.assertLogs('ruuvi-test', level='ERROR'):
            self.assertEqual(self.send()['status'], 500)
        self.assertEqual(d.states, before)
        d.fail = False
        self.assertEqual(self.send()['status'], 200)

    def test_duplicate_configured_mac_fails_without_creating_another(self):
        self.send()
        self.devices[3] = FakeDevice(3, self.devices[1].address, 'Copy')
        with self.assertLogs('ruuvi-test', level='ERROR'):
            self.assertEqual(self.send()['status'], 500)
        self.assertEqual(len(self.devices), 3)

    def test_configuration_validation(self):
        self.assertFalse(self.plugin.validatePrefsConfigUi({'staleSeconds':'0'})[0])
        self.assertFalse(self.plugin.validatePrefsConfigUi({'staleSeconds':'bad'})[0])
        self.assertFalse(self.plugin.validatePrefsConfigUi({'gatewayMac':'bad'})[0])
        self.assertTrue(self.plugin.validatePrefsConfigUi({'staleSeconds':'300'})[0])
        self.send()
        self.assertFalse(self.plugin.validateDeviceConfigUi({'address':self.devices[1].address}, 'ruuviTag', 0)[0])


if __name__ == '__main__':
    unittest.main()
