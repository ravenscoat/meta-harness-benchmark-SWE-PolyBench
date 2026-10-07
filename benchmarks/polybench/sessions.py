"""Opt-in task-local native Codex history; never restore credentials or other tasks."""
import io
import os
import subprocess
import tarfile
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import PurePosixPath

from hx.config import digest
from hx.models import GateError
from hx.process import clean_env

VERSION = 'task-local-codex-history@2'
MAX_HISTORY_BYTES = 16000000


def workspace_tree(workspace):
    """Fingerprint delivered files without changing HEAD or the caller's index."""
    with tempfile.TemporaryDirectory(prefix='hx-session-index-') as temporary:
        env = clean_env({'GIT_INDEX_FILE': os.path.join(temporary, 'index')})
        prefix = ['git', '-c', 'safe.directory=' + str(workspace.resolve()),
                  '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.autocrlf=false',
                  '-C', str(workspace)]
        for args in [('read-tree', 'HEAD'), ('add', '--all'), ('write-tree',)]:
            result = subprocess.run(prefix + list(args), env=env, capture_output=True,
                                    text=True, timeout=30)
            if result.returncode:
                raise GateError('Cannot fingerprint session workspace: ' + result.stderr[-1500:])
        return result.stdout.strip()


def session_id(value):
    try:
        return str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError) as error:
        raise GateError('Invalid native Codex session identifier') from error


def history_files(chunks, identifier):
    """Repack only bounded, regular native rollouts. Never extract worker archives."""
    identifier = session_id(identifier)
    data = bytearray()
    for chunk in chunks:
        data.extend(chunk)
        if len(data) > MAX_HISTORY_BYTES:
            raise GateError('Native session archive exceeds history bound')
    files = {}
    with tarfile.open(fileobj=io.BytesIO(data), mode='r:') as tar:
        for member in tar:
            path = PurePosixPath(member.name)
            if (path.is_absolute() or '..' in path.parts or '\\' in member.name
                    or not path.parts or path.parts[0] != 'sessions'):
                raise GateError('Unsafe native session archive path')
            if member.isdir():
                continue
            if not member.isfile() or member.size > MAX_HISTORY_BYTES:
                raise GateError('Native session archive must contain bounded regular files')
            if not path.name.endswith('-' + identifier + '.jsonl'):
                raise GateError('Archive contains a foreign session or non-rollout file')
            if member.name in files:
                raise GateError('Duplicate native session archive member')
            files[member.name] = tar.extractfile(member).read()
    if not files:
        raise GateError('No native rollout captured for completed session')
    return files


@dataclass
class History:
    identifier: str
    source_tree: str
    files: dict[str, bytes]


class TaskSessions:
    """Owned by one engine. No disk discovery or cross-run --last fallback."""
    def __init__(self):
        self.histories = {}

    def key(self, scope, task, model, schema, workdir):
        if not scope:
            raise GateError('Persistent implementer needs explicit run scope')
        return digest({'scope': scope, 'task': task.model_dump(), 'model': model,
                       'schema': schema, 'workdir': workdir, 'version': VERSION})

    def get(self, key, source_tree):
        history = self.histories.get(key)
        if history is not None and history.source_tree != source_tree:
            raise GateError('Session source differs from last accepted worker delivery')
        return history

    def save(self, key, identifier, source_tree, files):
        self.histories[key] = History(session_id(identifier), source_tree, files)

    def invalidate(self, key):
        self.histories.pop(key, None)


def codex_arguments(model, sandbox, effort, workdir, identifier=None, persistent=False):
    argv = ['/opt/hx-cli/bin/codex', '--no-daemon', 'exec']
    if identifier:
        argv += ['resume']
    argv += ['--ignore-user-config', '--json', '--model', model]
    if not persistent:
        argv += ['--ephemeral']
    if identifier:
        # exec resume has no --sandbox or -C; cwd comes from docker exec -w.
        argv += ['-c', f'sandbox_mode="{sandbox}"']
    else:
        argv += ['--sandbox', sandbox, '-C', workdir]
    argv += ['-c', 'approval_policy="never"', '-c', f'model_reasoning_effort="{effort}"',
             '-c', 'sandbox_workspace_write.network_access=false', '-c', 'web_search="disabled"',
             '--output-schema', '/hx/schema.json', '-o', '/hx/result.json']
    if identifier:
        argv += [session_id(identifier)]
    return argv + ['-']
