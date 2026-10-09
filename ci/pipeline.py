"""Manual public CI entry point. Private output never reaches Actions stdout."""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import traceback
import urllib.error
import urllib.parse

from github_api import GitHub
from source import checkout


TARGETS = {
    "windows-amd64": [{"platform": "windows", "arch": "amd64", "os": "windows-2022"}],
    "macos-amd64": [{"platform": "macos", "arch": "amd64", "os": "macos-15-intel"}],
    "macos-arm64": [{"platform": "macos", "arch": "arm64", "os": "macos-15"}],
}
TARGETS["default-platforms"] = TARGETS["windows-amd64"] + TARGETS["macos-amd64"]
PUBLIC_ROOT = Path(__file__).resolve().parents[1]


def validate_context():
    if os.environ.get("GITHUB_REF") != "refs/heads/main" or os.environ.get("GITHUB_EVENT_NAME") != "workflow_dispatch":
        raise ValueError("Private builds may only run manually from main")
    if os.environ.get("ACTIONS_STEP_DEBUG", "").lower() == "true" or os.environ.get("ACTIONS_RUNNER_DEBUG", "").lower() == "true":
        raise ValueError("Debug logging must be disabled for private builds")
    for name in ("PRIVATE_SOURCE_REPOSITORY", "PRIVATE_CORE_REPOSITORY", "GITHUB_REPOSITORY"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", os.environ.get(name, "")):
            raise ValueError("Invalid repository setting")
    if os.environ["GITHUB_REPOSITORY"] in (os.environ["PRIVATE_SOURCE_REPOSITORY"], os.environ["PRIVATE_CORE_REPOSITORY"]):
        raise ValueError("The workflow must run in the separate public repository")
    if not re.fullmatch(r"[0-9a-f]{40}", os.environ.get("GITHUB_SHA", "")):
        raise ValueError("Invalid public source commit")


def api():
    client = GitHub(os.environ["PRIVATE_SOURCE_REPOSITORY"], os.environ["PRIVATE_REPO_TOKEN"])
    client.require_private()
    return client


def output(key, value):
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as stream:
        stream.write(key + "=" + (json.dumps(value, separators=(",", ":")) if isinstance(value, (list, dict)) else str(value)) + "\n")


def same_sources(existing, current):
    keys = ("public_repository", "public_sha", "private_repository", "private_sha", "submodules", "public_sources")
    if any(existing.get(key) != current.get(key) for key in keys):
        raise ValueError("This release already contains a different source snapshot")


def records_release(client, release, create=False):
    """Keep verification JSON in an internal draft, outside delivery assets."""
    tag = "ci-records-" + str(release["id"])
    records = client.release(tag)
    if records is None and create:
        records = client.request("/releases", method="POST", data={
            "tag_name": tag, "target_commitish": release["target_commitish"],
            "name": "内部构建校验记录", "draft": True, "prerelease": False,
            "body": "内部校验记录，保留为私有草稿。",
        })
    if records is None or records.get("draft") is not True:
        raise ValueError("Private verification records must remain in an internal draft")
    if records.get("target_commitish") != release["target_commitish"]:
        raise ValueError("The internal records target a different source commit")
    return records


def upload_verified_json(client, release, name, value, replace=False):
    uploaded = client.upload_json(release, name, value, replace=replace)
    expected = (json.dumps(value, indent=2) + "\n").encode()
    if uploaded.get("size") != len(expected) or uploaded.get("digest") != "sha256:" + hashlib.sha256(expected).hexdigest():
        raise ValueError("Private record upload checksum verification failed")
    if client.asset_json(uploaded) != value:
        raise ValueError("Private record readback verification failed")
    return uploaded


def release_sources(client, release):
    records = records_release(client, release)
    matches = [asset for asset in client.assets(records) if asset["name"] == "source-provenance.json"]
    if len(matches) != 1:
        raise ValueError("Existing release does not have an unambiguous source record")
    return client.asset_json(matches[0])


def release_presentation(client, records):
    matches = [asset for asset in client.assets(records) if asset["name"] == "release-presentation.json"]
    if len(matches) != 1:
        raise ValueError("The private release notes are missing or ambiguous")
    presentation = client.asset_json(matches[0])
    if set(presentation) != {"name", "body"} or not all(isinstance(value, str) and value.strip() for value in presentation.values()):
        raise ValueError("Invalid private release notes")
    return presentation


def source_release(client, tag, provenance, presentation):
    release = client.release(tag)
    if release is None:
        release = client.request("/releases", method="POST", data={
            "tag_name": tag, "target_commitish": provenance["private_sha"],
            "name": presentation["name"], "draft": True, "prerelease": False,
            "body": presentation["body"],
        })
        records = records_release(client, release, create=True)
        upload_verified_json(client, records, "source-provenance.json", provenance)
        upload_verified_json(client, records, "release-presentation.json", presentation)
    else:
        same_sources(release_sources(client, release), provenance)
        if release_presentation(client, records_release(client, release)) != presentation:
            raise ValueError("The release notes do not match the selected private source")
    # Verify the actual tag, since target_commitish is not authoritative for an existing tag.
    try:
        client.request("/git/ref/tags/" + urllib.parse.quote(tag, safe=""))
    except urllib.error.HTTPError as error:
        # GitHub does not create a new tag until a draft is published. Creating
        # it here would also activate any legacy private tag-triggered workflow.
        # An untagged draft must still target the exact selected private commit.
        if error.code == 404 and release.get("draft") and release.get("target_commitish") == provenance["private_sha"]:
            return release
        raise
    tag_commit = client.request("/commits/" + urllib.parse.quote(tag, safe=""))["sha"]
    if tag_commit != provenance["private_sha"]:
        raise ValueError("The release tag refers to a different private commit")
    return release


def selected_brands(root, selector):
    available = sorted(path.name[len("app_config_"):-len(".json")]
                       for path in (root / "brand_config").glob("app_config_*.json"))
    if not available or any(not re.fullmatch(r"[A-Za-z0-9_-]+", name) for name in available):
        raise ValueError("Invalid private brand configuration")
    brands = available if selector == "all" else [selector]
    if any(brand not in available for brand in brands):
        raise ValueError("The requested brand does not exist in the private snapshot")
    return brands


def work_root(phase):
    suffix = os.environ.get("BUILD_PLATFORM", "prepare") + "-" + os.environ.get("BUILD_ARCH", "sources")
    return Path(os.environ["RUNNER_TEMP"]) / ("client-" + phase + "-" + suffix)


def assemble(root, commit, log):
    GitHub(os.environ["PRIVATE_CORE_REPOSITORY"], os.environ["CORE_REPO_TOKEN"]).require_private()
    return checkout(PUBLIC_ROOT, root, commit, os.environ["PRIVATE_SOURCE_REPOSITORY"],
                    os.environ["PRIVATE_CORE_REPOSITORY"], log)


def prepare(log):
    if os.environ.get("PREFLIGHT_ONLY", "false").lower() == "true" and os.environ.get("PUBLISH_RELEASE", "false").lower() == "true":
        raise ValueError("Preflight-only runs may not publish a release")
    print("Source verification started.", flush=True)
    client = api()
    reference = os.environ["PRIVATE_SOURCE_REF"].strip()
    if not reference or len(reference) > 200 or any(ord(char) < 32 for char in reference):
        raise ValueError("Invalid private source reference")
    commit = client.request("/commits/" + urllib.parse.quote(reference, safe=""))["sha"]
    root = work_root("prepare")
    provenance = assemble(root, commit, log)
    brands = selected_brands(root, os.environ["BUILD_BRAND"])
    target = os.environ["BUILD_TARGET"]
    if target not in TARGETS:
        raise ValueError("Unsupported target")
    match = re.search(r"^version:\s*([^\r\n]+)", (root / "pubspec.yaml").read_text(encoding="utf-8"), re.MULTILINE)
    if not match:
        raise ValueError("The private project version is missing")
    version = match.group(1).strip()
    history = json.loads((root / "brand_config/update_history.json").read_text(encoding="utf-8"))
    entries = [entry for entry in history["releases"] if entry.get("version") == version]
    if len(entries) != 1 or not entries[0].get("items") or any(not isinstance(item, str) or not item.strip() for item in entries[0]["items"]):
        raise ValueError("The selected version must have unambiguous release notes")
    presentation = {"name": "v" + version, "body": "\n".join("- " + item for item in entries[0]["items"])}
    tag = os.environ.get("RELEASE_TAG", "").strip() or "v" + version
    if not re.fullmatch(r"v[A-Za-z0-9_.+\-]+", tag):
        raise ValueError("Invalid release tag")
    source_release(client, tag, provenance, presentation)
    matrix = {"include": [dict(platform, brand=brand) for brand in brands for platform in TARGETS[target]]}
    output("matrix", matrix)
    output("private_sha", commit)
    output("release_tag", tag)
    print("Source snapshots verified. Private draft prepared.")


def run_private(root, log, preflight=False):
    environment = os.environ.copy()
    environment["FCLASH_BUILD_PROVENANCE"] = str(root / ".build-provenance.json")
    status = root / ".build-stage"
    environment["FCLASH_BUILD_STATUS_FILE"] = str(status)
    for key in ("PRIVATE_REPO_TOKEN", "CORE_REPO_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        environment.pop(key, None)
    command = [sys.executable, "scripts/public_build/build_private.py",
               "--brand", os.environ["BUILD_BRAND"], "--platform", os.environ["BUILD_PLATFORM"],
               "--arch", os.environ["BUILD_ARCH"]]
    if preflight:
        command.append("--preflight-only")
    messages = {"tools": "Tool compatibility check started.",
                "dependencies": "Tool compatibility check passed. Installing private build dependencies.",
                "compile": "Client compilation and packaging started.",
                "verify": "Compilation and packaging passed. Package content checks started."}
    previous = None
    with subprocess.Popen(command, cwd=root, env=environment, stdout=log, stderr=log) as process:
        while True:
            if status.is_file():
                # Never forward text supplied by private code. Only these
                # fixed stage values can cause an exact public message.
                with status.open(encoding="utf-8", errors="replace") as stream:
                    current = stream.read(32)
                if current in messages and current != previous:
                    print(messages[current], flush=True)
                    previous = current
            try:
                code = process.wait(timeout=2)
                break
            except subprocess.TimeoutExpired:
                continue
    if code:
        raise subprocess.CalledProcessError(code, command)


def preflight_record_name(brand, platform, arch):
    return record_name(brand, platform, arch).replace("build-record-", "preflight-record-", 1)


def successful_run_record(client, assets, kind, brand, platform, arch, provenance):
    prefix = kind + "-record-" + os.environ["GITHUB_RUN_ID"] + "-"
    suffix = "-" + "-".join((brand, platform, arch)) + ".json"
    attempts = []
    for asset in assets:
        name = asset["name"]
        if name.startswith(prefix) and name.endswith(suffix):
            value = name[len(prefix):-len(suffix)]
            if value.isascii() and value.isdigit() and 1 <= int(value) <= int(os.environ["GITHUB_RUN_ATTEMPT"]):
                attempts.append((int(value), asset))
    if not attempts:
        raise ValueError("This run has no successful record for the selected target")
    newest = max(attempt for attempt, _ in attempts)
    matches = [asset for attempt, asset in attempts if attempt == newest]
    if len(matches) != 1:
        raise ValueError("The selected run record is ambiguous")
    record = client.asset_json(matches[0])
    same_sources(record["provenance"], provenance)
    expected = {"brand": brand, "platform": platform, "arch": arch,
                "run_id": os.environ["GITHUB_RUN_ID"], "run_attempt": str(newest), "checks": "passed"}
    if any(record.get(key) != value for key, value in expected.items()):
        raise ValueError("The selected run record does not match its target and attempt")
    if kind == "preflight" and record.get("kind") != "preflight":
        raise ValueError("The selected record is not a platform preflight")
    return record


def preflight(log):
    client = api()
    root = work_root("preflight")
    provenance = assemble(root, os.environ["PRIVATE_SOURCE_SHA"], log)
    release = client.release(os.environ["RELEASE_TAG"])
    if release is None:
        raise ValueError("The prepared release is missing")
    same_sources(release_sources(client, release), provenance)
    records = records_release(client, release)
    print("Source verification passed. Checking platform tools.", flush=True)
    run_private(root, log, preflight=True)
    result = json.loads((root / ".preflight-result.json").read_text(encoding="utf-8"))
    same_sources(result["provenance"], provenance)
    if result.get("checks") != "passed" or result.get("kind") != "preflight":
        raise ValueError("Platform tool compatibility check did not pass")
    print("Tool compatibility check passed. Checking private upload and readback.", flush=True)
    record = dict(result, run_id=os.environ["GITHUB_RUN_ID"], run_attempt=os.environ["GITHUB_RUN_ATTEMPT"])
    name = preflight_record_name(os.environ["BUILD_BRAND"], os.environ["BUILD_PLATFORM"], os.environ["BUILD_ARCH"])
    client.require_private()
    upload_verified_json(client, records, name, record, replace=True)
    print("Private upload and readback passed. Preflight complete.", flush=True)


def build(log):
    client = api()
    root = work_root("build")
    provenance = assemble(root, os.environ["PRIVATE_SOURCE_SHA"], log)
    release = client.release(os.environ["RELEASE_TAG"])
    if release is None:
        raise ValueError("The prepared release is missing")
    same_sources(release_sources(client, release), provenance)
    records = records_release(client, release)
    # GitHub keeps successful prerequisite jobs when only failed jobs rerun.
    # Their records can belong to an earlier attempt of this exact run.
    successful_run_record(client, client.assets(records), "preflight", os.environ["BUILD_BRAND"],
                          os.environ["BUILD_PLATFORM"], os.environ["BUILD_ARCH"], provenance)
    print("Source verification and preflight record passed.", flush=True)
    run_private(root, log)
    result = json.loads((root / ".verified-build.json").read_text(encoding="utf-8"))
    same_sources(result["provenance"], provenance)
    print("Package content checks passed. Private upload started.", flush=True)
    assets = []
    client.require_private()
    package_name, manifest_name = target_asset_names(os.environ["BUILD_BRAND"], os.environ["BUILD_PLATFORM"], os.environ["BUILD_ARCH"])
    if len(result["assets"]) != 2 or {Path(relative).name for relative in result["assets"]} != {package_name, manifest_name}:
        raise ValueError("The build must contain exactly its installer and brand manifest")
    for relative in result["assets"]:
        path = root / relative
        if path.is_symlink() or not path.resolve().is_relative_to((root / "dist").resolve()):
            raise ValueError("Unsafe package path")
        data = path.read_bytes()
        destination = records if path.name == manifest_name else release
        uploaded = client.upload(destination, path.name, data, replace=True)
        digest = hashlib.sha256(data).hexdigest()
        if uploaded.get("size") != len(data) or uploaded.get("digest") != "sha256:" + digest:
            raise ValueError("Private upload checksum verification failed")
        assets.append({"name": path.name, "sha256": digest, "size": len(data), "id": uploaded["id"], "release_id": destination["id"]})
    record = dict(result, run_id=os.environ["GITHUB_RUN_ID"], run_attempt=os.environ["GITHUB_RUN_ATTEMPT"], assets=assets)
    name = record_name(os.environ["BUILD_BRAND"], os.environ["BUILD_PLATFORM"], os.environ["BUILD_ARCH"])
    upload_verified_json(client, records, name, record, replace=True)
    print("Package and contents verified. Uploaded to the private release.")


def record_name(brand, platform, arch):
    return "build-record-" + "-".join([os.environ["GITHUB_RUN_ID"], os.environ["GITHUB_RUN_ATTEMPT"], brand, platform, arch]) + ".json"


def target_asset_names(brand, platform, arch):
    stem = "-".join((brand, platform, arch))
    if platform == "windows" and arch == "amd64":
        package = stem + "-setup.exe"
    elif platform == "macos" and arch in ("amd64", "arm64"):
        package = stem + ".dmg"
    else:
        raise ValueError("Unsupported package target")
    return package, stem + "-brand-manifest.json"


def finalize(log):
    client = api()
    release = client.release(os.environ["RELEASE_TAG"])
    if release is None:
        raise ValueError("The prepared release is missing")
    provenance = release_sources(client, release)
    if provenance["private_sha"] != os.environ["PRIVATE_SOURCE_SHA"] or provenance["public_sha"] != os.environ["GITHUB_SHA"]:
        raise ValueError("Release source verification failed")
    records = records_release(client, release)
    delivery_assets = {asset["name"]: asset for asset in client.assets(release)}
    record_assets = {asset["name"]: asset for asset in client.assets(records)}
    for entry in json.loads(os.environ["BUILD_MATRIX"])["include"]:
        record = successful_run_record(client, record_assets.values(), "build", entry["brand"],
                                       entry["platform"], entry["arch"], provenance)
        package_name, manifest_name = target_asset_names(entry["brand"], entry["platform"], entry["arch"])
        if len(record["assets"]) != 2 or {item["name"] for item in record["assets"]} != {package_name, manifest_name}:
            raise ValueError("The successful build record has an incomplete asset set")
        for expected in record["assets"]:
            is_manifest = expected["name"] == manifest_name
            destination = records if is_manifest else release
            if expected.get("release_id") != destination["id"]:
                raise ValueError("A verified asset has the wrong release destination")
            actual = (record_assets if is_manifest else delivery_assets).get(expected["name"], {})
            if actual.get("id") != expected["id"] or actual.get("size") != expected["size"] or actual.get("digest") != "sha256:" + expected["sha256"]:
                raise ValueError("A release package changed after verification")
    # Remove the old separate checksum attachment convention only after success.
    for asset in delivery_assets.values():
        if asset["name"].endswith(".sha256"):
            client.request(f"/releases/assets/{asset['id']}", method="DELETE")
        elif not re.fullmatch(r"[A-Za-z0-9_-]+-(?:windows-amd64-setup\.exe|macos-(?:amd64|arm64)\.dmg)", asset["name"]):
            raise ValueError("Delivery releases may only contain installers")
    publish = os.environ.get("PUBLISH_RELEASE", "false").lower() == "true"
    if publish:
        presentation = release_presentation(client, records)
        client.request(f"/releases/{release['id']}", method="PATCH", data=dict(presentation, draft=False))
    print("All selected packages verified. " + ("Private release published." if publish else "Private draft retained."))


def sanitize(text):
    import base64
    for name in ("PRIVATE_REPO_TOKEN", "CORE_REPO_TOKEN", "GH_TOKEN", "GITHUB_TOKEN"):
        token = os.environ.get(name, "")
        if token:
            text = text.replace(token, "[redacted]")
            text = text.replace(base64.b64encode(("x-access-token:" + token).encode()).decode(), "[redacted]")
    text = re.sub(r"(?:gh[pousr]_[A-Za-z0-9_]{20,}|github_pat_[A-Za-z0-9_]{20,})", "[redacted]", text)
    return re.sub(r"https://[^\s/@]+:[^\s/@]+@", "https://[redacted]@", text)


def diagnostics(phase, path):
    client = api()
    tag = "ci-diagnostics-" + os.environ["GITHUB_RUN_ID"]
    release = client.release(tag)
    if release is None:
        release = client.request("/releases", method="POST", data={
            "tag_name": tag, "target_commitish": os.environ.get("PRIVATE_SOURCE_SHA") or os.environ.get("PRIVATE_SOURCE_REF"),
            "name": "Private CI diagnostics " + os.environ["GITHUB_RUN_ID"], "draft": True,
            "body": "Sanitized build logs. This draft is for diagnostics and contains no public Actions attachments.",
        })
    suffix = "-".join(filter(None, [phase, os.environ.get("BUILD_BRAND"), os.environ.get("BUILD_PLATFORM"),
                                  os.environ.get("BUILD_ARCH"), os.environ["GITHUB_RUN_ATTEMPT"]]))
    cleaned = path.with_suffix(".sanitized.log.gz")
    with path.open("r", encoding="utf-8", errors="replace") as source, gzip.open(cleaned, "wt", encoding="utf-8") as target:
        for line in source:
            target.write(sanitize(line))
    client.upload(release, suffix + ".log.gz", cleaned.read_bytes(), replace=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=["prepare", "preflight", "build", "finalize"])
    arguments = parser.parse_args()
    log_path = Path(os.environ.get("RUNNER_TEMP", ".")) / ("private-" + arguments.phase + ".log")
    failed = False
    with log_path.open("w", encoding="utf-8") as log:
        try:
            validate_context()
            globals()[arguments.phase](log)
        except Exception:
            traceback.print_exc(file=log)
            failed = True
    try:
        diagnostics(arguments.phase, log_path)
    except Exception:
        # Never print an upload error: it may contain a private endpoint, source
        # excerpt, or credential. A failed diagnostics upload is still reported.
        print("Private diagnostics could not be uploaded. No log contents were exposed.")
    if failed:
        print("::error::This stage failed. Inspect the diagnostics draft in the private source repository.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
