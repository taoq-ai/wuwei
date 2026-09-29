"""Allowlisted local service manager calls for the watch installer."""

import subprocess


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
