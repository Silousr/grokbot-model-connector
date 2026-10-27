import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import service


class ServiceTests(unittest.TestCase):
    def test_restart_and_singleton(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            shutil.copy(service.__file__, root / 'service.py')
            (root / 'connector.py').write_text('import time\nwhile True: time.sleep(.1)\n')
            command = [sys.executable, str(root / 'service.py')]
            supervisor = subprocess.Popen(command + ['run'], stdout=subprocess.DEVNULL,
                                          stderr=subprocess.DEVNULL)
            try:
                record = root / '.state/service-status.json'

                def wait_for_pid(previous=None):
                    deadline = time.monotonic() + 8
                    while time.monotonic() < deadline:
                        try:
                            data = json.loads(record.read_text())
                            if data['deliverer_pid'] != previous:
                                return data['deliverer_pid']
                        except (FileNotFoundError, json.JSONDecodeError):
                            pass
                        time.sleep(.05)
                    self.fail('supervisor failed to start/restart child')

                first = wait_for_pid()
                duplicate = subprocess.run(command + ['run'], timeout=3, check=True)
                self.assertEqual(duplicate.returncode, 0)
                self.assertEqual(json.loads(record.read_text())['deliverer_pid'], first)
                os.kill(first, signal.SIGKILL)
                second = wait_for_pid(first)
                self.assertNotEqual(first, second)
                self.assertIsNone(supervisor.poll())
            finally:
                supervisor.terminate()
                supervisor.wait(timeout=5)
            with self.assertRaises(ProcessLookupError):
                os.kill(second, 0)

    def test_boot_install_is_idempotent_and_preserves_other_content(self):
        with tempfile.TemporaryDirectory() as directory:
            boot = Path(directory) / 'boot'
            boot.write_text('#!/bin/bash\nsetup\ncli_auth_boot\nexec existing-watchdog\n')
            with patch.object(service, 'BOOT', boot), patch.object(service.os, 'geteuid', return_value=0), \
                    patch.object(service, 'service_user', return_value='alice'):
                service.install_hook()
                once = boot.read_text()
                service.install_hook()
                self.assertEqual(once, boot.read_text())
            self.assertEqual(once.count(service.MARKER), 1)
            other = once.replace(str(service.ROOT / 'service.py'), '/elsewhere/service.py')
            boot.write_text(other)
            with patch.object(service, 'BOOT', boot), patch.object(service.os, 'geteuid', return_value=0), \
                    patch.object(service, 'service_user', return_value='alice'):
                with self.assertRaises(SystemExit):
                    service.install_hook()
            self.assertEqual(boot.read_text(), other)
            self.assertIn('exec existing-watchdog', once)
            self.assertIn('/usr/sbin/runuser -u alice -- ', once)
            self.assertIn('service.py start', once)
