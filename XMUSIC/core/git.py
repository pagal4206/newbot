import asyncio
import shlex
from typing import Tuple

import config
from ..logging import LOGGER

# GitPython optional (Heroku-safe)
try:
    from git import Repo
    from git.exc import GitCommandError, InvalidGitRepositoryError
    GIT_AVAILABLE = True
except Exception:
    Repo = None
    GitCommandError = InvalidGitRepositoryError = Exception
    GIT_AVAILABLE = False


def install_req(cmd: str) -> Tuple[str, str, int, int]:
    async def install_requirements():
        args = shlex.split(cmd)
        process = await asyncio.create_subprocess_exec(
            *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        return (
            stdout.decode("utf-8", "replace").strip(),
            stderr.decode("utf-8", "replace").strip(),
            process.returncode,
            process.pid,
        )

    return asyncio.get_event_loop().run_until_complete(install_requirements())


def git():
    # 🚫 Git not available (Heroku)
    if not GIT_AVAILABLE:
        LOGGER(__name__).warning("Git not available. Skipping git operations.")
        return

    REPO_LINK = config.UPSTREAM_REPO

    if config.GIT_TOKEN:
        GIT_USERNAME = REPO_LINK.split("com/")[1].split("/")[0]
        TEMP_REPO = REPO_LINK.split("https://")[1]
        UPSTREAM_REPO = f"https://{GIT_USERNAME}:{config.GIT_TOKEN}@{TEMP_REPO}"
    else:
        UPSTREAM_REPO = REPO_LINK

    try:
        repo = Repo()
        LOGGER(__name__).info("Git client detected.")
        return

    except InvalidGitRepositoryError:
        LOGGER(__name__).info("Initializing new git repository...")
        repo = Repo.init()

    except GitCommandError as e:
        LOGGER(__name__).error(f"Git error: {e}")
        return

    try:
        if "origin" in repo.remotes:
            origin = repo.remote("origin")
        else:
            origin = repo.create_remote("origin", UPSTREAM_REPO)

        origin.fetch()

        if config.UPSTREAM_BRANCH not in repo.heads:
            repo.create_head(
                config.UPSTREAM_BRANCH,
                origin.refs[config.UPSTREAM_BRANCH],
            )

        repo.heads[config.UPSTREAM_BRANCH].set_tracking_branch(
            origin.refs[config.UPSTREAM_BRANCH]
        )
        repo.heads[config.UPSTREAM_BRANCH].checkout(True)

        origin.pull(config.UPSTREAM_BRANCH)

        install_req("pip install --no-cache-dir -r requirements.txt")
        LOGGER(__name__).info("Updates fetched successfully.")

    except Exception as e:
        LOGGER(__name__).error(f"Git update failed: {e}")
