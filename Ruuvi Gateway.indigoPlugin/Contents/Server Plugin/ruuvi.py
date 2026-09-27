"""Decoded HTTP push validation and sensor tracking; no Indigo or network code."""
import copy
import hashlib
import json
import math
import re
from dataclasses import dataclass
from datetime import datetime, timezone

MAX_BODY = 262144
MAX_TAGS = 256
MAX_CLOCK_SKEW = 300

# Decoded RAWv2 values, not the packed Bluetooth integers. Upper bounds exclude
# the decoded unavailable sentinels (e.g. -163.84 C, 3.647 V, 65535).
FIELDS = {
    'temperature': (-163.835, 163.835, False),
    'humidity': (0, 163.835, False),
    'pressure': (50000, 115534, False),
    'accelX': (-32.767, 32.767, False),
    'accelY': (-32.767, 32.767, False),
    'accelZ': (-32.767, 32.767, False),
    'movementCounter': (0, 254, True),
    'voltage': (1.6, 3.646, False),
    'txPower': (-40, 20, True),
    'measurementSequenceNumber': (0, 65534, True),
}


def mac(value):
    if not isinstance(value, str) or not re.fullmatch(r'(?:[0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', value):
        raise ValueError('Invalid MAC address')
    value = value.upper().replace('-', ':')
    if value in ('FF:FF:FF:FF:FF:FF', '00:00:00:00:00:00'):
        raise ValueError('Unavailable MAC address')
    return value


def number(value, low, high, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not low <= value <= high or not math.isfinite(value):
        return None
    if integer and int(value) != value:
        return None
    return int(value) if integer else float(value)


def timestamp(value):
    if value is None or value == '':
        return None
    if isinstance(value, str):
        try:
            value = float(value)
        except ValueError:
            return None
    # Zero is used before synchronization; do not treat it as a 1970 reception.
    return number(value, 1, 253402300799)


def iso(value):
    return datetime.fromtimestamp(value, timezone.utc).isoformat(timespec='seconds') if value else ''


@dataclass(frozen=True)
class Report:
    mac: str
    gateway: str
    reported: float | None
    received: float | None
    values: dict
    rssi: int | None


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse(body):
    """Validate the whole envelope before any device changes. No /history/MQTT input."""
    if not isinstance(body, str) or not body:
        raise ValueError('JSON body required')
    if len(body.encode('utf-8')) > MAX_BODY:
        raise ValueError('Report too large')
    try:
        doc = json.loads(body, object_pairs_hook=_unique_object)
    except (ValueError, RecursionError) as exc:
        raise ValueError('Invalid JSON') from exc
    if not isinstance(doc, dict) or not isinstance(doc.get('data'), dict):
        raise ValueError('Expected HTTP push data object')
    data = doc['data']
    tags = data.get('tags')
    if not isinstance(tags, dict) or len(tags) > MAX_TAGS:
        raise ValueError('Expected at most 256 tags keyed by MAC')
    gateway = mac(data.get('gw_mac'))
    reported = timestamp(data.get('timestamp'))
    result, skipped, seen = [], 0, set()
    for key, tag in tags.items():
        address = mac(key)
        if address in seen:
            raise ValueError('Repeated normalized sensor MAC')
        seen.add(address)
        if not isinstance(tag, dict):
            raise ValueError('Expected tag object')
        if tag.get('id') is not None and mac(tag['id']) != address:
            raise ValueError('Tag ID does not match its MAC key')
        if tag.get('dataFormat') != 5 or isinstance(tag.get('dataFormat'), bool):
            # A raw-only RAWv2 report is a configuration error, not an empty success.
            if 'data' in tag and 'dataFormat' not in tag:
                raise ValueError('Select decoded JSON in the Gateway HTTP settings')
            skipped += 1
            continue
        received = timestamp(tag.get('timestamp'))
        if received and reported and received > reported + 5:
            raise ValueError('Sensor reception is later than Gateway report time')
        values = {key: number(tag.get(key), *limits) for key, limits in FIELDS.items()}
        result.append(Report(address, gateway, reported, received, values,
                             number(tag.get('rssi'), -127, 20, True)))
    return result, skipped, gateway


def restore(raw):
    """Fail closed on missing/corrupt persistent tracking, rather than claiming fresh."""
    try:
        value = json.loads(raw)
        if not isinstance(value, dict) or value.get('version') != 1:
            return {}
        for key in ('freshAt', 'lastHeard', 'received', 'reported', 'measurementAt'):
            if value.get(key) is not None and timestamp(value[key]) is None:
                return {}
        for key in ('duplicates', 'outOfOrder'):
            if number(value.get(key, 0), 0, 1e15, True) is None:
                return {}
        return value
    except (ValueError, TypeError, RecursionError):
        return {}


def fresh(track, now, stale_seconds):
    age = now - track.get('freshAt', 0)
    return bool(track.get('freshAt')) and 0 <= age < stale_seconds


def advance(previous, report, now):
    """Return new tracking plus classification; caller commits only after state write."""
    state = copy.deepcopy(previous)
    state.update(version=1, lastHeard=now, gateway=report.gateway)
    rx, old_rx = report.received, previous.get('received')
    old_gw = previous.get('reported')
    # A lower source timestamp means delayed/replayed data unless a previously
    # future-skewed Gateway clock has now synchronized to Indigo's clock.
    backwards = rx is not None and old_rx is not None and rx < old_rx
    if backwards:
        synchronized = (previous.get('timeQuality') == 'gatewayRelative' and
                        old_gw is not None and old_gw > now + MAX_CLOCK_SKEW and
                        report.reported is not None and abs(report.reported - now) <= 5)
        if not synchronized:
            state['outOfOrder'] = previous.get('outOfOrder', 0) + 1
            return state, 'outOfOrder'
        old_rx = None
        state['sequence'] = None
    elif old_gw and report.reported and report.reported < old_gw and rx == old_rx:
        state['outOfOrder'] = previous.get('outOfOrder', 0) + 1
        return state, 'outOfOrder'
    state['reported'] = report.reported
    state['received'] = rx
    if rx is None:
        state['freshAt'] = now
        state['timeQuality'] = 'reportReceipt'
    elif old_rx is None or rx > old_rx:
        if report.reported is not None:
            lag = max(0, report.reported - rx)
            if abs(now - report.reported) <= MAX_CLOCK_SKEW:
                lag = max(lag, now - rx)
                state['timeQuality'] = 'sensorTimestamp'
            elif report.reported > now:
                state['timeQuality'] = 'gatewayRelative'
            else:
                # A delayed old report cannot be distinguished from a slow
                # Gateway clock. Fail stale rather than refreshing a replay.
                lag = max(lag, now - rx)
                state['timeQuality'] = 'clockUncertain'
        else:
            lag = max(0, now - rx)
            state['timeQuality'] = 'sensorTimestamp' if rx <= now else 'clockUncertain'
            if rx > now:
                lag = 1e12
        state['freshAt'] = now - lag
    # Equal reception time never refreshes freshAt, even in a new HTTP batch.
    signature = hashlib.sha256(json.dumps(report.values, sort_keys=True, allow_nan=False).encode()).hexdigest()
    sequence = report.values['measurementSequenceNumber']
    duplicate = (sequence is not None and sequence == state.get('sequence') and
                 signature == previous.get('signature'))
    if duplicate:
        state['duplicates'] = previous.get('duplicates', 0) + 1
        return state, 'duplicate'
    state.update(sequence=sequence, signature=signature, measurementAt=now)
    return state, 'measurement'
