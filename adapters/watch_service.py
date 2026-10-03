"""Allowlisted local process and network calls for the watch: service manager, heartbeat probes, the dead-man ping and telemetry posts."""

from pathlib import Path
import subprocess
import threading
import time

LAUNCHER = Path(__file__).resolve().parents[1] / 'bin/wuwei'
PROBE_ARGS = (('hook', 'PreToolUse'), ('status', '--line'))


def call(argv):
    allowed = (['systemctl', '--user', 'daemon-reload'],
               ['systemctl', '--user', 'enable', '--now'],
               ['systemctl', '--user', 'disable', '--now'],
               ['launchctl', 'bootstrap'], ['launchctl', 'bootout'])
    if not any(argv[:len(prefix)] == prefix for prefix in allowed):
        raise ValueError('unsupported watch service command')
    try:
        result = subprocess.run(argv, text=True, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise OSError(f'watch service could not run: {exc}') from exc
    if result.returncode:
        raise OSError(f'watch service failed: {result.stderr.strip() or result.stdout.strip() or result.returncode}')


def probe(calls, cwd, during=lambda: None, timeout=10):
    """Start allowlisted launcher calls together, run `during`, then collect each one.

    calls: [(argv tuple, stdin text)]. Returns ([(exit or None on timeout, first stderr
    line, wall ms)], during()). All calls share one deadline; a late call is killed.
    """
    if not all(tuple(argv) in PROBE_ARGS for argv, _ in calls):
        raise ValueError('unsupported probe command')
    deadline = time.monotonic() + timeout
    results, processes, threads = [None] * len(calls), [], []

    def collect(index, process, started):
        try:
            _, error = process.communicate(timeout=max(0, deadline - time.monotonic()))
            results[index] = (process.returncode, (error.splitlines() or [''])[0],
                              round((time.monotonic() - started) * 1000))
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()
            results[index] = (None, 'timeout', round((time.monotonic() - started) * 1000))

    try:
        for argv, text in calls:
            started = time.monotonic()
            process = subprocess.Popen([str(LAUNCHER), *argv], cwd=cwd, stdin=subprocess.PIPE,
                                       stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, errors='replace')
            processes.append(process)
            try:
                process.stdin.write(text)
                process.stdin.close()
            except BrokenPipeError:
                pass
            process.stdin = None  # closed now, so the call reads its payload without waiting its turn
            threads.append(threading.Thread(target=collect, args=(len(threads), process, started), daemon=True))
            threads[-1].start()
        measured = during()
        for thread in threads:
            thread.join()
        return results, measured
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.wait()


def ping(url, timeout=5):
    """GET an https check URL; raise OSError or ValueError on any failure."""
    import urllib.request
    if not url.startswith('https://'):
        raise ValueError('ping URL must be https')
    with urllib.request.urlopen(url, timeout=timeout) as response:
        response.read(1024)


def post(url, body, headers=None, timeout=5):
    """POST JSON to an https URL and return the HTTP status (#422); an error status is a
    status, any other failure raises OSError or ValueError."""
    import json
    import urllib.error
    import urllib.request
    if not url.startswith('https://'):
        raise ValueError('post URL must be https')
    request = urllib.request.Request(url, data=json.dumps(body).encode(), method='POST',
                                     headers={'Content-Type': 'application/json', **(headers or {})})
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        # A 3xx comes back as its status: following it would resend the headers to the Location host.
        def redirect_request(self, *args):
            return None
    try:
        with urllib.request.build_opener(NoRedirect).open(request, timeout=timeout) as response:
            response.read(1024)
            return response.status
    except urllib.error.HTTPError as exc:
        return exc.code
