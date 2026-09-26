import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Ruuvi Gateway.indigoPlugin/Contents/Server Plugin'))
from ruuvi import advance, fresh, mac, parse, restore


class RuuviTests(unittest.TestCase):
    def setUp(self):
        self.doc = json.loads((ROOT / 'tests/fixtures/decoded-http-anonymized.json').read_text())
        self.now = self.doc['data']['timestamp']
        self.address = next(iter(self.doc['data']['tags']))

    def report(self, **changes):
        doc = copy.deepcopy(self.doc)
        doc['data']['tags'][self.address].update(changes)
        return parse(json.dumps(doc))[0][0]

    def test_real_http_fixture(self):
        reports, skipped = parse(json.dumps(self.doc))
        self.assertEqual(len(reports), 2)
        self.assertEqual(skipped, 0)
        self.assertEqual(reports[0].values['pressure'], 100491)
        self.assertEqual(reports[0].values['temperature'], 2.47)
        self.assertEqual(reports[1].values['voltage'], 2.556)

    def test_mqtt_not_http(self):
        with self.assertRaises(ValueError):
            parse((ROOT / 'tests/fixtures/decoded-mqtt-anonymized.json').read_text())

    def test_bad_envelopes(self):
        for body in ('', 'null', '[]', '{}', '{', '{"data":[]}', '{"data":{"tags":[]}}'):
            with self.subTest(body=body), self.assertRaises(ValueError):
                parse(body)

    def test_raw_only_requires_decoded_setting(self):
        self.doc['data']['tags'][self.address] = {'data': '020106'}
        with self.assertRaisesRegex(ValueError, 'decoded'):
            parse(json.dumps(self.doc))

    def test_unsupported_format_skipped(self):
        self.doc['data']['tags'][self.address]['dataFormat'] = 6
        reports, skipped = parse(json.dumps(self.doc))
        self.assertEqual((len(reports), skipped), (1, 1))

    def test_empty_batch(self):
        self.doc['data']['tags'] = {}
        self.assertEqual(parse(json.dumps(self.doc)), ([], 0))

    def test_mac_normalization_and_mismatch(self):
        self.assertEqual(mac('aa-bb-cc-dd-ee-02'), self.address)
        with self.assertRaises(ValueError):
            mac('FF:FF:FF:FF:FF:FF')
        self.doc['data']['tags'][self.address]['id'] = 'AA:BB:CC:DD:EE:99'
        with self.assertRaises(ValueError):
            parse(json.dumps(self.doc))

    def test_duplicate_json_and_normalized_mac_rejected(self):
        with self.assertRaises(ValueError):
            parse('{"data":{},"data":{}}')
        self.doc['data']['tags'][self.address.lower()] = self.doc['data']['tags'][self.address]
        with self.assertRaises(ValueError):
            parse(json.dumps(self.doc))

    def test_missing_readings_not_zero(self):
        report = self.report(temperature=None, humidity=float('nan'), pressure='bad',
                             voltage=3.647, accelX=-32.768, txPower=22,
                             measurementSequenceNumber=65535, movementCounter=255)
        for key in ('temperature', 'humidity', 'pressure', 'voltage', 'accelX',
                    'txPower', 'measurementSequenceNumber', 'movementCounter'):
            self.assertIsNone(report.values[key])

    def test_boolean_and_fractional_counters_invalid(self):
        report = self.report(temperature=True, movementCounter=2.5)
        self.assertIsNone(report.values['temperature'])
        self.assertIsNone(report.values['movementCounter'])

    def test_extremely_large_integer_reading_is_unavailable(self):
        report = self.report(temperature=10**400)
        self.assertIsNone(report.values['temperature'])

    def test_new_reception_duplicate_measurement_remains_fresh(self):
        first = self.report()
        state, _ = advance({}, first, self.now)
        newer = type(first)(first.mac, first.gateway, self.now + 60, self.now + 59,
                            first.values, first.rssi)
        state, kind = advance(state, newer, self.now + 60)
        self.assertEqual(kind, 'duplicate')
        self.assertEqual(state['lastHeard'], self.now + 60)
        self.assertEqual(state['measurementAt'], self.now)
        self.assertTrue(fresh(state, self.now + 70, 30))

    def test_cached_duplicate_becomes_stale_despite_last_heard(self):
        first = self.report()
        state, _ = advance({}, first, self.now)
        cached = type(first)(first.mac, first.gateway, self.now + 90, first.received,
                             first.values, first.rssi)
        state, kind = advance(state, cached, self.now + 90)
        self.assertEqual(kind, 'duplicate')
        self.assertEqual(state['lastHeard'], self.now + 90)
        self.assertFalse(fresh(state, self.now + 90, 30))

    def test_repeated_old_batches_never_become_clock_reset(self):
        state, _ = advance({}, self.report(), self.now)
        for i in range(3):
            old = self.report(timestamp=self.now - 900 + i)
            old = type(old)(old.mac, old.gateway, self.now - 899 + i, old.received,
                            old.values, old.rssi)
            state, kind = advance(state, old, self.now + 400 + i)
            self.assertEqual(kind, 'outOfOrder')
            self.assertFalse(fresh(state, self.now + 400 + i, 300))

    def test_sequence_rollover_restart_and_same_sequence_changed_value(self):
        state = {}
        for seq in (65534, 0, 9000, 1):
            state, kind = advance(state, self.report(measurementSequenceNumber=seq), self.now)
            self.assertEqual(kind, 'measurement')
        state, kind = advance(state, self.report(measurementSequenceNumber=1, temperature=10), self.now)
        self.assertEqual(kind, 'measurement')

    def test_missing_sequence_disables_deduplication(self):
        report = self.report(measurementSequenceNumber=None)
        state, _ = advance({}, report, self.now)
        self.assertEqual(advance(state, report, self.now)[1], 'measurement')

    def test_older_reception_does_not_replace_new_measurement(self):
        state, _ = advance({}, self.report(), self.now)
        before = copy.deepcopy(state)
        state, kind = advance(state, self.report(timestamp=self.now - 60, temperature=90), self.now + 1)
        self.assertEqual(kind, 'outOfOrder')
        self.assertEqual(state['signature'], before['signature'])
        self.assertEqual(state['freshAt'], before['freshAt'])

    def test_stale_at_threshold_and_recovery(self):
        state, _ = advance({}, self.report(), self.now)
        self.assertFalse(fresh(state, state['freshAt'] + 300, 300))
        report = self.report(timestamp=self.now)
        state, _ = advance(state, report, self.now)
        self.assertTrue(fresh(state, self.now, 300))

    def test_restart_preserves_dedup_and_freshness(self):
        state, _ = advance({}, self.report(), self.now)
        state = restore(json.dumps(state))
        self.assertEqual(advance(state, self.report(), self.now + 10)[1], 'duplicate')
        self.assertFalse(fresh(state, self.now + 400, 300))
        self.assertEqual(restore('{broken'), {})
        self.assertEqual(restore('{"version":1,"freshAt":"bad"}'), {})

    def test_gateway_clock_skew_uses_relative_age_without_cached_refresh(self):
        report = self.report()
        report = type(report)(report.mac, report.gateway, self.now+3600, self.now+3598,
                              report.values, report.rssi)
        state, _ = advance({}, report, self.now)
        self.assertEqual(state['timeQuality'], 'gatewayRelative')
        self.assertTrue(fresh(state, self.now, 300))
        state, _ = advance(state, report, self.now + 400)
        self.assertFalse(fresh(state, self.now + 400, 300))
        corrected = self.report(timestamp=self.now)
        state, kind = advance(state, corrected, self.now)
        self.assertEqual(kind, 'measurement')
        self.assertEqual(state['timeQuality'], 'sensorTimestamp')

    def test_missing_timestamp_explicit_report_receipt_fallback(self):
        state, _ = advance({}, self.report(timestamp=None), self.now)
        self.assertEqual(state['timeQuality'], 'reportReceipt')
        self.assertTrue(fresh(state, self.now, 300))

    def test_first_delayed_batch_cannot_claim_freshness(self):
        state, _ = advance({}, self.report(), self.now + 900)
        self.assertFalse(fresh(state, self.now + 900, 300))
        self.assertEqual(state['timeQuality'], 'clockUncertain')

    def test_source_timestamp_cannot_exceed_report_timestamp(self):
        with self.assertRaises(ValueError):
            self.report(timestamp=self.now+60)

    def test_body_and_tag_limits(self):
        with self.assertRaises(ValueError):
            parse(' ' * 262145)
        self.doc['data']['tags'] = {str(i): {} for i in range(257)}
        with self.assertRaises(ValueError):
            parse(json.dumps(self.doc))


if __name__ == '__main__':
    unittest.main()
