import os
import subprocess
import sys
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase


class SettingsTests(SimpleTestCase):
    def test_exec_command_reads_persisted_secret_with_empty_environment(self):
        # docker compose exec starts a new process without entrypoint's exports.
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, ".secret-key").write_text(
                "test-persisted-secret", encoding="utf-8"
            )
            environment = {**os.environ, "SECRET_KEY": "", "DATA_DIR": directory}
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    "from config.settings import SECRET_KEY; assert SECRET_KEY == 'test-persisted-secret'",
                ],
                env=environment,
                cwd=settings.BASE_DIR,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
