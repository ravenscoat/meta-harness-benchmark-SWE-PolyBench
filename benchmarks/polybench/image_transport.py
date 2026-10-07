"""Bounded retries of a pinned cache transfer, never of a coding identity."""
import time

from benchmarks.polybench.image_cache import ensure_image
from benchmarks.polybench.prepare import write

VERSION = 'pinned-image-transport@1'


def transient_transport(error):
    text = str(error).lower()
    return any(term in text for term in ['connection reset by peer', 'unexpected eof',
                                        'tls handshake timeout', 'read timed out',
                                        'i/o timeout', 'connection aborted'])


def ensure_pinned(client, root, case, control, *, operation=ensure_image, sleep=time.sleep):
    """At most three sequential attempts, same pin; preserve every SDK receipt."""
    folder = root / 'transport-retries' / (case['id'] + '-' + str(time.time_ns()))
    folder.mkdir(parents=True, exist_ok=False)
    for attempt in range(1, 4):
        control()
        record = {'version': VERSION, 'attempt': attempt, 'case': case['id'],
                  'image_id': case['image_id'], 'digests': case['image_digests'], 'passed': False}
        try:
            image = operation(client, root, case)
            control()
            record['passed'] = True
            return image
        except Exception as error:
            record['error'] = str(error)
            record['retryable_transport'] = transient_transport(error)
            if attempt == 3 or not record['retryable_transport']:
                raise
        finally:
            write(folder / f'attempt-{attempt}.json', record)
        control()
        sleep(10 * attempt)
        control()
