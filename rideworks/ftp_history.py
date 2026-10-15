"""One date-effective SQLite FTP timeline; explicit, validated legacy bootstrap."""
import csv
from datetime import date
from hashlib import sha256
import io
import json
from pathlib import Path

from .errors import IntegrityError

APPROVED_SHA256 = 'cb990c18e969d0d12f1d524bea22cf8b596746171f179f6241748394b87ad073'


def snapshot(store):
    """Read rows and revision together, sharing the caller's calculation snapshot."""
    with store._transaction():
        state = store.connection.execute('SELECT * FROM ftp_history_state WHERE singleton=1').fetchone()
        if state is None or state['initialization'] not in ('ready', 'migration_needed'):
            raise IntegrityError('Unknown FTP initialization state; review required.')
        if state['initialization'] == 'migration_needed':
            raise IntegrityError('FTP history migration needed: explicitly bootstrap this Store before analysis.')
        pairs = [tuple(r) for r in store.connection.execute('SELECT effective_date,watts FROM ftp_history ORDER BY effective_date')]
        rows = [dict(effective_from_date=d, ftp_watts=w,
                     effective_until_date_exclusive=pairs[i+1][0] if i+1<len(pairs) else None)
                for i,(d,w) in enumerate(pairs)]
        signature = sha256(json.dumps([state['revision'], pairs], separators=(',', ':')).encode()).hexdigest()
        return dict(rows=rows,revision=state['revision'],signature=signature,initialization=state['initialization'])


def validate_entry(effective_date, watts):
    try:
        if date.fromisoformat(effective_date).isoformat() != effective_date:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError('FTP date must be YYYY-MM-DD.') from None
    if type(watts) is not int or watts <= 0 or watts > 9223372036854775807:
        raise ValueError('FTP watts must be a positive integer supported by SQLite.')


def add_entry(store, effective_date, watts, *, expected_revision):
    """Insert an intermediate setting; never overwrite or alter existing rows."""
    validate_entry(effective_date, watts)
    with store._transaction(write=True):
        current = snapshot(store)
        if type(expected_revision) is not int or expected_revision != current['revision']:
            raise ValueError('FTP history changed. Reload and preview again.')
        existing = next((r for r in current['rows'] if r['effective_from_date']==effective_date),None)
        if existing:
            raise ValueError(f"An FTP entry already exists on {effective_date}: {existing['ftp_watts']} W.")
        rows = current['rows']
        if not rows or not rows[0]['effective_from_date'] < effective_date < rows[-1]['effective_from_date']:
            raise ValueError('Choose a date between existing FTP entries. Extending history requires an Owner decision.')
        store.connection.execute('INSERT INTO ftp_history VALUES (?,?)',(effective_date,watts))
        store.connection.execute('UPDATE ftp_history_state SET revision=revision+1 WHERE singleton=1')
        return snapshot(store)


def validated_sources(source_path, mirror_path):
    """No target construction or writes until both explicit inputs pass."""
    payload = Path(source_path).read_bytes()
    mirror = Path(mirror_path).read_bytes()
    if payload != mirror or sha256(payload).hexdigest() != APPROVED_SHA256:
        raise IntegrityError('FTP bootstrap sources must be the two byte-identical approved inputs.')
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8')))
    if reader.fieldnames != ['effective_from_date','effective_until_date_exclusive','ftp_watts']:
        raise IntegrityError('Invalid FTP bootstrap columns.')
    rows = list(reader)
    pairs = []
    try:
        for i,r in enumerate(rows):
            if None in r or set(r) != set(reader.fieldnames):
                raise ValueError()
            d,w = r['effective_from_date'],int(r['ftp_watts'])
            validate_entry(d,w)
            if str(w)!=r['ftp_watts'] or (pairs and d<=pairs[-1][0]):
                raise ValueError()
            if r['effective_until_date_exclusive'] != (rows[i+1]['effective_from_date'] if i+1<len(rows) else ''):
                raise ValueError()
            pairs.append((d,w))
        if len(pairs)!=66:
            raise ValueError()
    except (ValueError,TypeError,KeyError) as exc:
        raise IntegrityError('Invalid FTP bootstrap dates, watts or intervals.') from exc
    return pairs


def bootstrap(target_dir, source_path, mirror_path):
    if target_dir is None:
        raise ValueError('An explicit FTP bootstrap target Store is required.')
    pairs = validated_sources(source_path,mirror_path)
    from .store import Store
    with Store(target_dir) as store, store._transaction(write=True):
        state=store.connection.execute('SELECT * FROM ftp_history_state WHERE singleton=1').fetchone()
        if state is None or state['initialization'] not in ('ready','migration_needed'):
            raise IntegrityError('Unknown FTP bootstrap state.')
        if state['bootstrap_checksum'] is not None:
            if state['bootstrap_checksum'] != APPROVED_SHA256 or state['initialization']!='ready' or state['revision']<1:
                raise IntegrityError('Conflicting FTP bootstrap completion marker.')
            return dict(imported=False,**snapshot(store))
        if state['revision'] != 0 or store.connection.execute('SELECT 1 FROM ftp_history LIMIT 1').fetchone():
            raise IntegrityError('Nonempty or partial FTP target; refusing to merge bootstrap.')
        store.connection.executemany('INSERT INTO ftp_history VALUES (?,?)',pairs)
        store.connection.execute("UPDATE ftp_history_state SET initialization='ready',revision=1,bootstrap_checksum=? WHERE singleton=1",(APPROVED_SHA256,))
        actual=[tuple(r) for r in store.connection.execute('SELECT effective_date,watts FROM ftp_history ORDER BY effective_date')]
        if actual != pairs:
            raise IntegrityError('FTP bootstrap parity verification failed.')
        return dict(imported=True,**snapshot(store))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--target-dir',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--mirror',type=Path,required=True)
    args=parser.parse_args()
    result=bootstrap(args.target_dir,args.source,args.mirror)
    print(json.dumps(dict(imported=result['imported'],entries=len(result['rows']),revision=result['revision'],signature=result['signature'])))


if __name__=='__main__':
    main()
