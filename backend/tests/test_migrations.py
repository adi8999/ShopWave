"""
test_migrations.py – Verify Alembic migrations run cleanly from scratch.
"""
import os
import subprocess
import sys
import tempfile


def test_alembic_upgrade_head_on_fresh_sqlite():
    """Run `alembic upgrade head` against a temporary SQLite database."""
    with tempfile.NamedTemporaryFile(suffix=".db") as tmp:
        env = os.environ.copy()
        env["DATABASE_URL"] = f"sqlite:///{tmp.name}"
        backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        result = subprocess.run(
            [sys.executable, "-m", "alembic", "upgrade", "head"],
            cwd=backend_dir,
            env=env,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, f"Alembic failed:\n{result.stdout}\n{result.stderr}"
