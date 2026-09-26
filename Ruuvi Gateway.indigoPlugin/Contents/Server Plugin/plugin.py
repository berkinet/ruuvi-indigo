"""Ruuvi Gateway HTTP receiver hosted by Indigo's existing web server."""
import json
import threading
import time

import indigo
from ruuvi import FIELDS, MAX_BODY, advance, fresh, iso, mac, parse, restore


class Plugin(indigo.PluginBase):
    def __init__(self, *args):
        super().__init__(*args)
        self._lock = threading.RLock()
        self._wall = time.time()
        self._mono = time.monotonic()

    def _now(self):
        # Wall-clock jumps while running must not change elapsed freshness.
        return self._wall + time.monotonic() - self._mono

    def _stale_seconds(self):
        value = int(self.pluginPrefs.get('staleSeconds', 300))
        if not 30 <= value <= 86400:
            raise ValueError('Stale timeout must be 30–86400 seconds')
        return value

    def startup(self):
        try:
            self._stale_seconds()
            self.logger.info('HTTP receiver ready: /message/%s/receive/', self.pluginId)
        except Exception as exc:
            self.logger.error('Cannot start receiver: %s. Review plugin configuration.', exc)

    def validatePrefsConfigUi(self, values):
        errors = indigo.Dict()
        try:
            seconds = int(values.get('staleSeconds', 300))
            if not 30 <= seconds <= 86400:
                raise ValueError()
        except (ValueError, TypeError):
            errors['staleSeconds'] = 'Enter a whole number from 30 to 86400.'
        try:
            value = values.get('gatewayMac', '').strip()
            values['gatewayMac'] = mac(value) if value else ''
        except ValueError:
            errors['gatewayMac'] = 'Enter a valid MAC address or leave blank.'
        return (False, values, errors) if errors else (True, values)

    def validateDeviceConfigUi(self, values, typeId, devId):
        errors = indigo.Dict()
        try:
            address = mac(values.get('address', '').strip())
            for dev in indigo.devices.iter('self'):
                if dev.id != devId and mac(dev.address) == address:
                    errors['address'] = 'A device already exists for this MAC.'
            if devId and indigo.devices[devId].address != address:
                errors['address'] = 'MAC is the stable identity; create a different device to change it.'
            values['address'] = address
        except ValueError:
            errors['address'] = 'Enter the sensor MAC address.'
        except Exception as exc:
            self.logger.error('Device configuration validation failed (%s).', type(exc).__name__)
            errors['address'] = 'Unable to validate device; retry.'
        return (False, values, errors) if errors else (True, values)

    @staticmethod
    def _reply(status, **content):
        return indigo.Dict({'status': status,
                            'headers': indigo.Dict({'Content-Type': 'application/json'}),
                            'content': json.dumps(content)})

    def receive(self, action, dev=None, callerWaitingForResult=None):
        try:
            if action.props.get('incoming_request_method') != 'POST':
                return self._reply(405, error='POST required')
            body = action.props.get('request_body', '')
            if isinstance(body, str) and len(body.encode('utf-8')) > MAX_BODY:
                return self._reply(413, error='Report too large')
            try:
                reports, skipped = parse(body)
            except ValueError as exc:
                return self._reply(400, error=str(exc))
            allowed = self.pluginPrefs.get('gatewayMac', '').strip()
            # Empty batches must obey the allowlist too.
            gateway = mac(json.loads(body)['data']['gw_mac'])
            if allowed and gateway != mac(allowed):
                return self._reply(403, error='Gateway is not configured for this plugin')
            counts = dict(measurements=0, duplicates=0, outOfOrder=0, ignored=skipped)
            with self._lock:
                self._stale_seconds()
                devices = {}
                for sensor in indigo.devices.iter('self'):
                    address = mac(sensor.address)
                    if address in devices:
                        raise ValueError('Duplicate configured MAC; remove the duplicate device')
                    devices[address] = sensor
                for report in reports:
                    sensor = devices.get(report.mac)
                    if sensor is None:
                        if not self.pluginPrefs.get('autoCreate', True):
                            counts['ignored'] += 1
                            continue
                        sensor = indigo.device.create(
                            protocol=indigo.kProtocol.Plugin,
                            address=report.mac, name='RuuviTag ' + report.mac,
                            deviceTypeId='ruuviTag',
                            props={'address': report.mac, 'SupportsSensorValue': True,
                                   'SupportsOnState': False})
                        devices[report.mac] = sensor
                    if not sensor.enabled:
                        counts['ignored'] += 1
                        continue
                    result = self._update(sensor, report)
                    counts[{'measurement': 'measurements', 'duplicate': 'duplicates',
                            'outOfOrder': 'outOfOrder'}[result]] += 1
            return self._reply(200, **counts)
        except Exception as exc:
            self.logger.error('Gateway report could not be fully applied (%s). Check device configuration and Indigo connection.',
                              type(exc).__name__)
            return self._reply(500, error='Report not fully applied; retry is safe')

    def _update(self, dev, report):
        now = self._now()
        track, kind = advance(restore(dev.states.get('tracking', '')), report, now)
        updates = {
            'lastHeard': iso(now), 'gatewayMac': report.gateway,
            'duplicateCount': track.get('duplicates', 0),
            'outOfOrderCount': track.get('outOfOrder', 0),
            'lastReportKind': kind,
        }
        if kind != 'outOfOrder':
            updates.update(gatewayReportedAt=iso(report.reported),
                           sensorReceivedAt=iso(report.received),
                           timeQuality=track.get('timeQuality', 'unknown'))
            if report.rssi is not None:
                updates['rssi'] = report.rssi
            updates['rssiAvailable'] = report.rssi is not None
        if kind == 'measurement':
            updates['lastMeasurementAt'] = iso(now)
            for key, value in report.values.items():
                updates[key + 'Available'] = value is not None
                if value is not None:
                    updates[key] = value / 100 if key == 'pressure' else value
            if report.values['temperature'] is not None:
                updates['sensorValue'] = report.values['temperature']
            missing = [key for key, value in report.values.items() if value is None]
            updates['missingReadings'] = ', '.join(missing)
        temperature_ok = updates.get('temperatureAvailable', dev.states.get('temperatureAvailable', False))
        healthy = fresh(track, now, self._stale_seconds())
        updates.update(stale=not healthy, status='Stale' if not healthy else
                       ('Online' if temperature_ok else 'Temperature unavailable'))
        updates['tracking'] = json.dumps(track, sort_keys=True, allow_nan=False)
        self._write_states(dev, updates)
        self._set_health(dev, healthy, temperature_ok)
        return kind

    @staticmethod
    def _write_states(dev, updates):
        rows = []
        for key, value in updates.items():
            if dev.states.get(key) == value:
                continue
            row = {'key': key, 'value': value}
            if key in ('sensorValue', 'temperature'):
                row.update(decimalPlaces=3, uiValue=f'{value:.2f} °C')
            rows.append(row)
        if rows:
            dev.updateStatesOnServer(rows)

    @staticmethod
    def _set_health(dev, healthy, temperature_ok):
        error = 'Sensor stale' if not healthy else (None if temperature_ok else 'Temperature unavailable')
        dev.setErrorStateOnServer(error)
        dev.updateStateImageOnServer(indigo.kStateImageSel.TemperatureSensorOn if healthy
                                     else indigo.kStateImageSel.SensorOff)

    def deviceStartComm(self, dev):
        try:
            with self._lock:
                dev.stateListOrDisplayStateIdChanged()
                self._check_stale(dev)
        except Exception as exc:
            self.logger.error('Cannot initialize Ruuvi device %s (%s).', dev.id, type(exc).__name__)

    def _check_stale(self, dev):
        track = restore(dev.states.get('tracking', ''))
        healthy = fresh(track, self._now(), self._stale_seconds())
        temperature_ok = dev.states.get('temperatureAvailable', False)
        status = 'Stale' if not healthy else ('Online' if temperature_ok else 'Temperature unavailable')
        self._write_states(dev, {'stale': not healthy, 'status': status})
        self._set_health(dev, healthy, temperature_ok)

    def runConcurrentThread(self):
        try:
            while True:
                try:
                    with self._lock:
                        for dev in indigo.devices.iter('self'):
                            if dev.enabled:
                                try:
                                    self._check_stale(dev)
                                except Exception as exc:
                                    self.logger.error('Freshness check failed for device %s (%s).',
                                                      dev.id, type(exc).__name__)
                except Exception as exc:
                    self.logger.error('Freshness checks unavailable (%s).', type(exc).__name__)
                self.sleep(5)
        except self.StopThread:
            pass

    def actionControlSensor(self, action, dev):
        self.logger.info('%s is updated by Gateway HTTP pushes; no sensor polling is available.', dev.name)
