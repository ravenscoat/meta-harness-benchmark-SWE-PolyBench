"""File-backed capture prevents Node's forced exit from dropping pipe writes."""

CAPTURE_SCRIPT = r'''
umask 077
hx_capture=$(mktemp -d /tmp/hx-report.XXXXXXXX) || exit 125
trap 'rm -rf -- "$hx_capture"' EXIT HUP INT TERM
hx_blocks=$1
shift
(
  ulimit -f "$hx_blocks" || exit 125
  "$@" >"$hx_capture/stdout" 2>"$hx_capture/stderr"
)
hx_status=$?
cat "$hx_capture/stdout" || exit 125
cat "$hx_capture/stderr" >&2 || exit 125
exit "$hx_status"
'''


def capture_argv(argv, max_bytes):
    # Only explicit JSON reporters need this adapter. Keep user argv separate
    # from trusted shell code; no interpolation/eval of repository arguments.
    if not any(argv[i:i + 2] == ['--reporter', 'json'] for i in range(len(argv))):
        return argv
    # Shell file-size units vary (512/1024 bytes). This bounds each temporary
    # stream to no more than the configured byte allowance; outer capture also
    # enforces the combined log budget and existing command deadline.
    blocks = max(1, max_bytes // 1024)
    return ['sh', '-c', CAPTURE_SCRIPT, 'hx-report-capture', str(blocks), *argv]
