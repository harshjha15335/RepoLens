"""Git reindex refreshes the selected branch rather than cloning into a full directory."""

import shutil
import subprocess

import pytest

from app.core.config import Settings
from app.core.errors import RepositoryValidationError
from app.services.ingestion.service import IngestionService


@pytest.mark.skipif(shutil.which("git") is None, reason="Git is required")
async def test_git_refresh_keeps_selected_branch_and_fetches_new_changes(tmp_path):
    upstream = tmp_path / "upstream"
    upstream.mkdir()

    def git(*args):
        return subprocess.run(
            ["git", "-C", str(upstream), *args], check=True, capture_output=True, text=True
        ).stdout.strip()

    git("init", "-b", "main")
    git("config", "user.name", "RepoLens test")
    git("config", "user.email", "test@example.invalid")
    (upstream / "main.py").write_text("value = 'main'\n", encoding="utf-8")
    git("add", ".")
    git("commit", "-m", "Main fixture")
    git("switch", "-c", "feature")
    (upstream / "main.py").write_text("value = 'feature'\n", encoding="utf-8")
    git("commit", "-am", "Feature fixture")
    settings = Settings(data_dir=str(tmp_path / "data"))
    checkout = settings.repos_path / "test-repository" / "source"
    await IngestionService._clone_git(str(upstream), checkout, "feature", settings)
    assert "feature" in (checkout / "main.py").read_text()

    (upstream / "main.py").write_text("value = 'updated feature'\n", encoding="utf-8")
    git("commit", "-am", "Update fixture")
    git("switch", "main")
    await IngestionService._clone_git(str(upstream), checkout, None, settings)
    assert "updated feature" in (checkout / "main.py").read_text()
    branch = subprocess.run(
        ["git", "-C", str(checkout), "branch", "--show-current"],
        check=True, capture_output=True, text=True,
    ).stdout.strip()
    assert branch == "feature"


async def test_git_checkout_must_stay_in_application_storage(tmp_path):
    settings = Settings(data_dir=str(tmp_path / "data"))
    with pytest.raises(RepositoryValidationError, match="inside repository storage"):
        await IngestionService._clone_git("unused", tmp_path / "outside", None, settings)
