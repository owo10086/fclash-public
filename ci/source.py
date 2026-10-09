"""Assemble the exact public snapshot with a fixed private source commit."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess


def checked_path(value):
    path = PurePosixPath(value)
    if not value or path.is_absolute() or ".." in path.parts or "\\" in value or str(path) != value:
        raise ValueError("Invalid source path")
    return path


def approved_files(public_root):
    document = json.loads((public_root / "ci/public-files.json").read_text(encoding="utf-8"))
    files = document["files"]
    if len({entry["path"] for entry in files}) != len(files):
        raise ValueError("Duplicate public source path")
    for entry in files:
        checked_path(entry["path"])
        if not re.fullmatch(r"[0-9a-f]{64}", entry["sha256"]):
            raise ValueError("Invalid reviewed digest")
    return files


def overlay_public(public_root, private_root):
    """Validate everything before modifying any private source file."""
    files = approved_files(public_root)
    for entry in files:
        paths = [root / entry["path"] for root in (public_root, private_root)]
        for root, path in zip((public_root, private_root), paths):
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("Missing or unsafe source file")
            if hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
                raise ValueError("Public and private snapshots differ; export the reviewed source first")
    for entry in files:
        shutil.copyfile(public_root / entry["path"], private_root / entry["path"])
    return {entry["path"]: entry["sha256"] for entry in files}


def git_environment(repository, source_token, core_repository, core_token):
    import base64
    environment = os.environ.copy()
    configurations = {"core.autocrlf": "false", "credential.helper": ""}
    for name, token in ((repository, source_token), (core_repository, core_token)):
        encoded = base64.b64encode(("x-access-token:" + token).encode()).decode()
        configurations[f"http.https://github.com/{name}.git.extraheader"] = "AUTHORIZATION: basic " + encoded
    environment["GIT_CONFIG_COUNT"] = str(len(configurations))
    for index, (key, value) in enumerate(configurations.items()):
        environment[f"GIT_CONFIG_KEY_{index}"] = key
        environment[f"GIT_CONFIG_VALUE_{index}"] = value
    environment["GIT_TERMINAL_PROMPT"] = "0"
    return environment


def checkout(public_root, private_root, commit, repository, core_repository, log):
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("The private source must be an immutable commit")
    if private_root.exists():
        raise ValueError("Build directory already exists")
    private_root.mkdir(parents=True)
    environment = git_environment(repository, os.environ["PRIVATE_REPO_TOKEN"],
                                  core_repository, os.environ["CORE_REPO_TOKEN"])

    def git(*arguments, capture=False):
        result = subprocess.run(["git", *arguments], cwd=private_root, env=environment,
                                stdout=subprocess.PIPE if capture else log,
                                stderr=log, check=True)
        return result.stdout.decode().strip() if capture else None

    git("init", "--quiet")
    git("remote", "add", "origin", "https://github.com/" + repository + ".git")
    git("fetch", "--depth=1", "origin", commit)
    git("checkout", "--detach", "FETCH_HEAD")
    if git("rev-parse", "HEAD", capture=True) != commit:
        raise ValueError("Private commit verification failed")
    core_url = git("config", "--file", ".gitmodules", "--get", "submodule.core/Clash.Meta.url", capture=True)
    if core_url != "https://github.com/" + core_repository + ".git":
        raise ValueError("The configured private core does not match the source submodule")
    # Submodules remain pinned by the selected private commit. Never use --remote.
    git("submodule", "update", "--init", "--recursive")
    status = git("submodule", "status", "--recursive", capture=True)
    submodules = {}
    for line in status.splitlines():
        if line[0] in "-+U":
            raise ValueError("An initialized submodule does not match its pinned commit")
        fields = line.strip().split()
        submodules[fields[1]] = fields[0]
    if "core/Clash.Meta" not in submodules:
        raise ValueError("The private core submodule is missing")
    sources = overlay_public(public_root, private_root)
    provenance = {
        "schema_version": 1,
        "public_repository": os.environ["GITHUB_REPOSITORY"],
        "public_sha": os.environ["GITHUB_SHA"],
        "private_repository": repository,
        "private_sha": commit,
        "submodules": submodules,
        "public_sources": sources,
    }
    (private_root / ".build-provenance.json").write_text(json.dumps(provenance, indent=2) + "\n", encoding="utf-8")
    return provenance
