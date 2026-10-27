#!/usr/bin/env python3
"""Dependency-free crash supervisor for the alert deliverer, plus an optional
boot hook for Grok Bot boxes (containers without systemd or cron)."""
import argparse
import fcntl
import json
import os
import pwd
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parent
STATE = Path(os.environ.get('MODEL_CONNECTOR_STATE', ROOT / '.state')).resolve()
# Boot entrypoint used by Grok Bot box containers. Override for other images.
BOOT = Path(os.environ.get('MODEL_CONNECTOR_BOOT_SCRIPT', '/usr/local/bin/start-sand-box'))
MARKER = '# Model Connector supervised alerts'


def run():
    STATE.mkdir(mode=0o700, exist_ok=True)
    with (STATE / 'supervisor.lock').open('a') as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return
        stopping = False
        child = None

        def stop(*_):
            nonlocal stopping
            stopping = True
            if child is not None and child.poll() is None:
                child.terminate()

        signal.signal(signal.SIGTERM, stop)
        signal.signal(signal.SIGINT, stop)
        while not stopping:
            child = subprocess.Popen([sys.executable, str(ROOT / 'connector.py'), 'deliver-alerts'],
                                     cwd=ROOT, stdin=subprocess.DEVNULL,
                                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            status = dict(supervisor_pid=os.getpid(), deliverer_pid=child.pid,
                          started=time.time())
            temp = STATE / 'service-status.tmp'
            temp.write_text(json.dumps(status) + '\n')
            temp.replace(STATE / 'service-status.json')
            code = child.wait()
            if not stopping:
                print(f'{time.time():.0f} deliverer exited ({code}); restarting in 2s', flush=True)
                time.sleep(2)


def start():
    STATE.mkdir(mode=0o700, exist_ok=True)
    with (STATE / 'supervisor.log').open('ab') as log:
        subprocess.Popen([sys.executable, str(Path(__file__).resolve()), 'run'], cwd=ROOT,
                         stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                         start_new_session=True, close_fds=True)


def status():
    try:
        data = json.loads((STATE / 'service-status.json').read_text())
        for key, token in [('supervisor_pid', 'service.py'), ('deliverer_pid', 'deliver-alerts')]:
            args = Path(f'/proc/{data[key]}/cmdline').read_bytes().decode().split('\0')
            if token not in ' '.join(args):
                raise ValueError('process identity mismatch')
        # Check locks too: PID records alone can be stale or reused.
        for name in ('supervisor.lock', 'deliverer.lock'):
            with (STATE / name).open('a') as lock:
                try:
                    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                except BlockingIOError:
                    continue
                raise ValueError('process lock is not held')
    except (OSError, ValueError, KeyError):
        print('Model Connector service is not running (or is restarting).')
        return 1
    print(f"Model Connector running: supervisor PID {data['supervisor_pid']}, "
          f"deliverer PID {data['deliverer_pid']}")
    return 0


def service_user():
    # Run as whoever owns the install directory, never as root.
    return os.environ.get('SUDO_USER') or pwd.getpwuid(ROOT.stat().st_uid).pw_name


def install_hook():
    # Grok Bot boxes run no systemd/cron. Their boot entrypoint calls
    # cli_auth_boot before handing over to its watchdog; start just before it.
    if os.geteuid() != 0:
        raise SystemExit('Install the boot hook with sudo; the service itself runs as the install owner.')
    if not BOOT.exists():
        raise SystemExit(f'No boot entrypoint at {BOOT}; use systemd/cron or start manually.')
    entry = '\ncli_auth_boot\n'
    text = BOOT.read_text()
    user = service_user()
    if user == 'root':
        raise SystemExit('Refusing to run the service as root; install as a normal user.')
    block = (f'{MARKER}\n'
             f'/usr/sbin/runuser -u {shlex.quote(user)} -- {shlex.quote(sys.executable)} {shlex.quote(str(ROOT / "service.py"))} start\n'
             '# End Model Connector supervised alerts\n')
    if MARKER in text:
        first = text.index(MARKER)
        existing = text[first:text.index('# End Model Connector supervised alerts\n', first)]
        if str(ROOT / 'service.py') not in existing and os.environ.get('MODEL_CONNECTOR_FORCE_HOOK') != '1':
            raise SystemExit('A boot hook for another connector install exists; set MODEL_CONNECTOR_FORCE_HOOK=1 to replace it.')
        last = text.index('# End Model Connector supervised alerts\n', first) + len('# End Model Connector supervised alerts\n')
        text = text[:first] + text[last:]
    if text.count(entry) != 1:
        raise SystemExit('Boot entrypoint changed; refusing to guess the insertion point.')
    updated = text.replace(entry, '\n' + block + 'cli_auth_boot\n')
    if updated != BOOT.read_text():
        BOOT.write_text(updated)
    print(f'Installed idempotent boot hook; service runs as {user}.')


if __name__ == '__main__':
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['run', 'start', 'status', 'install-hook'])
    args = parser.parse_args()
    if args.action == 'run':
        run()
    elif args.action == 'start':
        start()
    elif args.action == 'status':
        sys.exit(status())
    else:
        install_hook()
