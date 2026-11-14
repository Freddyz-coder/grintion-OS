from __future__ import annotations

import fcntl
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
GARB = REPO_ROOT / "bin" / "garb"


def run(root: Path, *args: str, check: bool = True, env: dict | None = None,
        backend: str | None = None) -> subprocess.CompletedProcess:
    command = [sys.executable, str(GARB)]
    if backend:
        command += ["--backend", backend]
    command += ["--root", str(root), *args]
    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    if check and result.returncode != 0:
        raise AssertionError(f"garb {' '.join(args)} failed:\n{result.stdout}\n{result.stderr}")
    return result


def mark_synced(root: Path) -> None:
    """Pretend pacman's sync databases are already downloaded."""
    sync = root / "var/lib/pacman/sync"
    sync.mkdir(parents=True, exist_ok=True)
    (sync / "core.db").write_text("")


def write_package(src: Path, name: str, version: str = "1.0.0", deps: list[str] | None = None,
                  files: dict[str, str] | None = None) -> None:
    pkg = src / name
    (pkg / "root" / "usr" / "share" / name).mkdir(parents=True, exist_ok=True)
    (pkg / "root" / "usr" / "share" / name / "data.txt").write_text(f"{name}-{version}\n")
    for rel, content in (files or {}).items():
        path = pkg / "root" / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
    manifest = [
        "[package]",
        f'name = "{name}"',
        f'version = "{version}"',
        "release = 1",
        f'description = "{name} test package"',
        'arch = ["x86_64"]',
    ]
    if deps:
        manifest += ["", "[dependencies]", f"runtime = {json.dumps(deps)}"]
    (pkg / "Garbfile").write_text("\n".join(manifest) + "\n")


@pytest.fixture()
def environment(tmp_path: Path) -> dict:
    src = tmp_path / "src"
    repo = tmp_path / "repo"
    keys = tmp_path / "keys"
    root = tmp_path / "root"
    src.mkdir()
    write_package(src, "libfoo")
    write_package(src, "app", deps=["libfoo"], files={"usr/bin/app": "app-ok\n"})
    (src / "app" / "root" / "usr" / "bin" / "app").chmod(0o755)
    subprocess.run([sys.executable, str(GARB), "keygen", str(keys)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-build", str(src), str(repo)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-index", str(repo), "--key", str(keys / "private.pem")],
                   check=True, capture_output=True)
    (root / "etc/garb/repos.d").mkdir(parents=True)
    (root / "etc/garb/keys").mkdir(parents=True)
    (root / "etc/garb/repos.d/demo.conf").write_text(f"url={repo}\n")
    shutil.copy(keys / "public.pem", root / "etc/garb/keys/demo.pub")
    run(root, "update")
    return {"src": src, "repo": repo, "keys": keys, "root": root}


def test_signed_install_dependencies_and_remove(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    assert (root / "usr/bin/app").read_text() == "app-ok\n"
    assert (root / "usr/share/libfoo/data.txt").read_text() == "libfoo-1.0.0\n"
    run(root, "verify")
    run(root, "remove", "app", "libfoo")
    assert not (root / "usr/bin/app").exists()
    assert not (root / "usr/share/libfoo/data.txt").exists()


def test_tamper_is_detected(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    (root / "usr/bin/app").write_text("evil\n")
    result = run(root, "verify", check=False)
    assert result.returncode != 0
    assert "TAMPERED" in result.stdout


def test_bad_signature_fails_closed(environment: dict) -> None:
    root = environment["root"]
    repo = environment["repo"]
    keys = environment["keys"]
    other = keys / "other"
    subprocess.run([sys.executable, str(GARB), "keygen", str(other)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "sign-index", str(repo / "index.json"),
                    "--key", str(other / "private.pem")], check=True, capture_output=True)
    result = run(root, "update", check=False)
    assert result.returncode != 0
    assert "signature" in result.stderr.lower()


def test_traversal_archive_is_rejected(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    evil = tmp_path / "pkg.garb"
    metadata = {
        "schema": 1,
        "name": "evil",
        "version": "1.0.0",
        "release": 1,
        "files": [{"path": "../escaped", "type": "file", "sha256": "0" * 64}],
    }
    with tarfile.open(evil, "w:gz") as tar:
        payload = json.dumps(metadata).encode()
        info = tarfile.TarInfo("GARB_METADATA.json")
        info.size = len(payload)
        import io
        tar.addfile(info, io.BytesIO(payload))
        data = b"owned\n"
        info = tarfile.TarInfo("../escaped")
        info.size = len(data)
        tar.addfile(info, io.BytesIO(data))
    result = run(root, "install", str(evil), check=False)
    assert result.returncode != 0
    assert not (tmp_path / "escaped").exists()


def test_archive_checksum_mismatch_fails(environment: dict) -> None:
    root = environment["root"]
    repo = environment["repo"]
    archives = list(repo.glob("*.garb"))
    target = next(path for path in archives if path.name.startswith("app-"))
    with open(target, "ab") as handle:
        handle.write(b"tamper")
    result = run(root, "install", "app", check=False)
    assert result.returncode != 0
    assert "checksum" in result.stderr.lower()


def test_pacman_backend_translation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    mark_synced(root)
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0 - libalpm v15.0.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$@" > "$GARB_FAKE_LOG"\n'
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "install", "foo", backend="pacman", env=env)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        "--root", str(root), "-S", "--needed", "--noconfirm", "foo"
    ]


def test_apk_backend_translation(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    log = tmp_path / "apk.args"
    fake = tmp_path / "apk"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "apk-tools 2.14.4"; exit 0; fi\n'
        'printf \'%s\\n\' "$@" > "$GARB_FAKE_LOG"\n'
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "remove", "foo", backend="apk", env=env)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ["--root", str(root), "del", "foo"]


def test_remove_refuses_reverse_dependencies(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    result = run(root, "remove", "libfoo", check=False)
    assert result.returncode != 0
    assert "required by" in result.stderr
    assert (root / "usr/share/libfoo/data.txt").exists()
    run(root, "remove", "libfoo", "--force")
    assert not (root / "usr/share/libfoo/data.txt").exists()


def test_local_archive_resolves_dependencies(environment: dict) -> None:
    root = environment["root"]
    archive = next(environment["repo"].glob("app-*.garb"))
    run(root, "install", str(archive))
    assert (root / "usr/bin/app").read_text() == "app-ok\n"
    assert (root / "usr/share/libfoo/data.txt").exists()


def test_local_archive_missing_dependency_fails(environment: dict, tmp_path: Path) -> None:
    root = tmp_path / "bare-root"
    root.mkdir()
    archive = next(environment["repo"].glob("app-*.garb"))
    result = run(root, "install", str(archive), check=False)
    assert result.returncode != 0
    assert "libfoo" in result.stderr


def test_file_conflict_is_refused(environment: dict) -> None:
    root = environment["root"]
    src = environment["src"]
    repo = environment["repo"]
    keys = environment["keys"]
    run(root, "install", "app")
    write_package(src, "other", files={"usr/bin/app": "other-ok\n"})
    subprocess.run([sys.executable, str(GARB), "repo-build", str(src), str(repo)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-index", str(repo), "--key", str(keys / "private.pem")],
                   check=True, capture_output=True)
    run(root, "update")
    result = run(root, "install", "other", check=False)
    assert result.returncode != 0
    assert "conflicts" in result.stderr.lower()
    assert (root / "usr/bin/app").read_text() == "app-ok\n"
    run(root, "install", "other", "--force")
    assert (root / "usr/bin/app").read_text() == "other-ok\n"


def test_clean_and_list(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    listed = run(root, "list").stdout
    assert "app" in listed and "libfoo" in listed
    assert "app" in run(root, "list", "--available").stdout
    assert run(root, "list", "--upgradable").stdout.strip() == "[-] no packages to list"
    cleaned = run(root, "clean")
    assert "cleaned" in cleaned.stdout
    assert not any((root / "var/cache/garb/repos").iterdir())
    run(root, "update")
    run(root, "list", "--available")


def test_verify_json_output(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    payload = json.loads(run(root, "verify", "--format", "json").stdout)
    assert payload["failed"] == 0
    (root / "usr/bin/app").write_text("evil\n")
    result = run(root, "verify", "--format", "json", check=False)
    assert result.returncode != 0
    payload = json.loads(result.stdout)
    assert payload["failed"] == 1
    assert any(item["status"] == "tampered" for item in payload["packages"][0]["files"])


def test_malformed_garbfile_has_no_traceback(tmp_path: Path) -> None:
    package = tmp_path / "bad"
    package.mkdir()
    (package / "Garbfile").write_text("[package\nname = ")
    result = run(tmp_path / "root", "build", str(package / "Garbfile"),
                 "-o", str(tmp_path / "out"), check=False)
    assert result.returncode != 0
    assert "Traceback" not in result.stderr
    assert result.stderr.startswith("[-]")


def test_symlink_to_directory_is_packaged(tmp_path: Path) -> None:
    package = tmp_path / "src" / "linker"
    (package / "root/usr/share/linker").mkdir(parents=True)
    (package / "root/usr/share/linker/data.txt").write_text("data\n")
    (package / "root/usr/lib").mkdir(parents=True)
    (package / "root/usr/lib/linker").symlink_to("../share/linker")
    (package / "Garbfile").write_text(
        "[package]\n"
        'name = "linker"\n'
        'version = "1.0.0"\n'
        "release = 1\n"
    )
    out = tmp_path / "out"
    subprocess.run([sys.executable, str(GARB), "build", str(package / "Garbfile"), "-o", str(out)],
                   check=True, capture_output=True)
    archive = next(out.glob("*.garb"))
    with tarfile.open(archive) as tar:
        assert "usr/lib/linker" in tar.getnames()
        assert tar.getmember("usr/lib/linker").issym()
        assert tar.getmember("usr/lib/linker").linkname == "../share/linker"


def test_allow_unsigned_repository_without_signature(tmp_path: Path) -> None:
    src = tmp_path / "src"
    repo = tmp_path / "repo"
    root = tmp_path / "root"
    src.mkdir()
    write_package(src, "solo")
    subprocess.run([sys.executable, str(GARB), "repo-build", str(src), str(repo)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-index", str(repo)], check=True, capture_output=True)
    (root / "etc/garb/repos.d").mkdir(parents=True)
    (root / "etc/garb/repos.d/demo.conf").write_text(f"url={repo}\n")
    run(root, "update", "--allow-unsigned")
    assert (root / "var/cache/garb/repos/demo/index.json").exists()


def test_pacman_backend_maps_installed_info(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0 - libalpm v15.0.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$@" > "$GARB_FAKE_LOG"\n'
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "info", "foo", "--installed", backend="pacman", env=env)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == ["--root", str(root), "-Qi", "foo"]


def test_pacman_backend_rejects_json_verify(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(tmp_path / "pacman")
    (tmp_path / "pacman").write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        "exit 0\n"
    )
    (tmp_path / "pacman").chmod(0o755)
    result = run(root, "verify", "--format", "json", backend="pacman", env=env, check=False)
    assert result.returncode != 0
    assert "native-garb" in result.stderr


def test_pacman_backend_rejects_unknown_major_version(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v99.0.0"; exit 0; fi\n'
        "exit 0\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    result = run(root, "install", "foo", backend="pacman", env=env, check=False)
    assert result.returncode != 0
    assert "supported major versions" in result.stderr


def test_pacman_backend_requires_parseable_version(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    fake = tmp_path / "pacman"
    fake.write_text("#!/bin/sh\nexit 0\n")
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    result = run(root, "install", "foo", backend="pacman", env=env, check=False)
    assert result.returncode != 0
    assert "did not report a supported version" in result.stderr


def test_pacman_backend_limits_overwrite_to_reported_conflicts(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    mark_synced(root)
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$*" >> "$GARB_FAKE_LOG"\n'
        'case " $* " in *" --overwrite "*) exit 0 ;; esac\n'
        'echo "usr/lib/libfoo.so exists in filesystem"\n'
        "exit 1\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "install", "foo", backend="pacman", env=env)
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert len(calls) == 2
    assert calls[0] == f"--root {root} -S --needed --noconfirm foo"
    assert "--overwrite /usr/lib/libfoo.so" in calls[1]
    assert "--overwrite usr/lib/libfoo.so" in calls[1]
    assert "--overwrite *" not in calls[0]
    assert "--overwrite *" not in calls[1]


def test_pacman_backend_parses_colon_conflict_format(tmp_path: Path) -> None:
    # pacman 7 prints "path: exists in filesystem" while pacman 6 omits the
    # colon. A parser that only accepts one form silently skips the retry.
    root = tmp_path / "root"
    root.mkdir()
    mark_synced(root)
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v6.1.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$*" >> "$GARB_FAKE_LOG"\n'
        'case " $* " in *" --overwrite "*) exit 0 ;; esac\n'
        'echo "libxdmcp: usr/lib/libfoo.so exists in filesystem"\n'
        "exit 1\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "install", "foo", backend="pacman", env=env)
    assert result.returncode == 0, result.stderr
    calls = log.read_text().splitlines()
    assert len(calls) == 2
    assert "--overwrite /usr/lib/libfoo.so" in calls[1]
    assert "--overwrite usr/lib/libfoo.so" in calls[1]


def test_pacman_backend_refuses_sensitive_conflict(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    mark_synced(root)
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$*" >> "$GARB_FAKE_LOG"\n'
        'echo "/etc/shadow exists in filesystem"\n'
        "exit 1\n"
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "install", "foo", backend="pacman", env=env, check=False)
    assert result.returncode != 0
    assert "security-sensitive" in result.stderr
    assert len(log.read_text().splitlines()) == 1


def test_local_archive_rejects_external_backend(tmp_path: Path) -> None:
    root = tmp_path / "root"
    root.mkdir()
    archive = tmp_path / "pkg.garb"
    archive.write_bytes(b"not a real archive")
    result = run(root, "install", str(archive), backend="pacman", check=False)
    assert result.returncode != 0
    assert "native backend" in result.stderr


def test_upgrade(environment: dict) -> None:
    root = environment["root"]
    src = environment["src"]
    repo = environment["repo"]
    keys = environment["keys"]
    run(root, "install", "app")
    write_package(src, "app", version="2.0.0", deps=["libfoo"], files={"usr/bin/app": "app-v2\n"})
    subprocess.run([sys.executable, str(GARB), "repo-build", str(src), str(repo)], check=True, capture_output=True)
    subprocess.run([sys.executable, str(GARB), "repo-index", str(repo), "--key", str(keys / "private.pem")],
                   check=True, capture_output=True)
    run(root, "update")
    run(root, "upgrade")
    assert (root / "usr/bin/app").read_text() == "app-v2\n"
    entry = json.loads((root / "var/lib/garb/db.json").read_text())["packages"]["app"]
    assert entry["version"] == "2.0.0"


def sign_index(repo: Path, keys: Path) -> None:
    subprocess.run(
        [sys.executable, str(GARB), "sign-index", str(repo / "index.json"),
         "--key", str(keys / "private.pem")],
        check=True,
        capture_output=True,
    )


def test_expired_index_is_rejected(environment: dict) -> None:
    import time

    repo = environment["repo"]
    index = json.loads((repo / "index.json").read_text())
    index["expires"] = int(time.time()) - 60
    (repo / "index.json").write_text(json.dumps(index))
    sign_index(repo, environment["keys"])

    result = run(environment["root"], "update", check=False)
    assert result.returncode != 0
    assert "expired" in result.stderr.lower()


def test_replayed_index_is_rejected(environment: dict) -> None:
    import time

    repo = environment["repo"]
    index = json.loads((repo / "index.json").read_text())
    index["index_version"] = 1
    index["expires"] = int(time.time()) + 86400
    (repo / "index.json").write_text(json.dumps(index))
    sign_index(repo, environment["keys"])

    result = run(environment["root"], "update", check=False)
    assert result.returncode != 0
    assert "replayed" in result.stderr.lower()


def test_setuid_package_cannot_be_built(tmp_path: Path) -> None:
    package = tmp_path / "src" / "suid"
    (package / "root/usr/bin").mkdir(parents=True)
    binary = package / "root/usr/bin/suid-helper"
    binary.write_text("#!/bin/sh\n")
    binary.chmod(0o4755)
    (package / "Garbfile").write_text(
        "[package]\n"
        'name = "suid"\n'
        'version = "1.0.0"\n'
        "release = 1\n"
    )

    result = subprocess.run(
        [sys.executable, str(GARB), "build", str(package / "Garbfile"),
         "-o", str(tmp_path / "out")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode != 0
    assert "setuid" in result.stderr.lower()


def test_setuid_archive_is_rejected_at_install(tmp_path: Path) -> None:
    import hashlib
    import io

    root = tmp_path / "root"
    root.mkdir()
    archive = tmp_path / "suid.garb"
    payload = b"#!/bin/sh\n"
    metadata = {
        "schema": 1,
        "name": "suid",
        "version": "1.0.0",
        "release": 1,
        "files": [{
            "path": "usr/bin/suid-helper",
            "type": "file",
            "sha256": hashlib.sha256(payload).hexdigest(),
            "mode": "4755",
        }],
    }
    with tarfile.open(archive, "w:gz") as tar:
        payload_json = json.dumps(metadata).encode()
        info = tarfile.TarInfo("GARB_METADATA.json")
        info.size = len(payload_json)
        tar.addfile(info, io.BytesIO(payload_json))
        info = tarfile.TarInfo("usr/bin/suid-helper")
        info.size = len(payload)
        info.mode = 0o755
        tar.addfile(info, io.BytesIO(payload))

    result = run(root, "install", str(archive), check=False)
    assert result.returncode != 0
    assert "setuid" in result.stderr.lower()
    assert not (root / "usr/bin/suid-helper").exists()


def test_transaction_journal_records_a_committed_install(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    records = json.loads(run(root, "history", "--format", "json").stdout)
    assert any(
        record.get("status") == "committed" and "app" in record.get("packages", [])
        for record in records
    )
    text = run(root, "history").stdout
    assert "committed" in text
    assert "app" in text


def test_lock_blocks_a_concurrent_transaction(environment: dict) -> None:
    root = environment["root"]
    lock = root / "var/lib/garb/lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with open(lock, "a+", encoding="utf-8") as holder:
        fcntl.flock(holder.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        result = run(root, "install", "app", check=False)
    assert result.returncode != 0
    assert "another garb transaction is running" in result.stderr
    assert not (root / "usr/share/libfoo/data.txt").exists()
    run(root, "install", "app")


def test_fsck_accepts_a_healthy_install(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    result = run(root, "fsck")
    assert "fsck passed" in result.stdout
    assert run(root, "fsck", "--hash").returncode == 0


def test_fsck_detects_missing_files(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    (root / "usr/bin/app").unlink()
    result = run(root, "fsck", check=False)
    assert result.returncode != 0
    assert "missing file" in result.stdout
    payload = json.loads(run(root, "fsck", "--format", "json", check=False).stdout)
    assert payload["ok"] is False
    assert any(issue["kind"] == "missing" for issue in payload["issues"])


def test_fsck_detects_tampering_only_with_hash(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    (root / "usr/bin/app").write_text("tampered\n")
    assert run(root, "fsck").returncode == 0
    result = run(root, "fsck", "--hash", check=False)
    assert result.returncode != 0
    assert "hash mismatch" in result.stdout


def test_corrupt_database_fails_closed(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    database = root / "var/lib/garb/db.json"
    database.write_text("{not json\n")
    result = run(root, "list", check=False)
    assert result.returncode != 0
    assert "corrupt" in result.stderr.lower()
    assert "Traceback" not in result.stderr
    fsck = run(root, "fsck", "--format", "json", check=False)
    assert fsck.returncode != 0
    payload = json.loads(fsck.stdout)
    assert any(issue["kind"] == "database" for issue in payload["issues"])


def test_fsck_reports_incomplete_journal_and_backup(environment: dict) -> None:
    root = environment["root"]
    run(root, "install", "app")
    journal = root / "var/lib/garb/journal.jsonl"
    journal.write_text(
        journal.read_text()
        + json.dumps({
            "schema": 1,
            "txid": "test-incomplete",
            "time": 0,
            "root": str(root),
            "command": "install",
            "packages": ["app"],
            "status": "started",
        })
        + "\n"
    )
    (root / "var/lib/garb/tmp/garb-backup-test").mkdir(parents=True)
    payload = json.loads(run(root, "fsck", "--format", "json").stdout)
    kinds = {issue["kind"] for issue in payload["issues"]}
    assert "journal" in kinds
    assert "backup" in kinds


def test_pacman_backend_syncs_missing_databases_before_install(tmp_path: Path) -> None:
    # A fresh install has the seeded local database but no core.db/extra.db.
    # pacman then reports "database file for 'core' does not exist" followed by
    # "target not found" for every package, which looks like a broken manager.
    root = tmp_path / "root"
    root.mkdir()
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$*" >> "$GARB_FAKE_LOG"\n'
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "install", "firefox", backend="pacman", env=env)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        f"--root {root} -Sy",
        f"--root {root} -S --needed --noconfirm firefox",
    ]
    assert "synchronizing" in result.stderr


def test_pacman_backend_maps_common_package_names(tmp_path: Path) -> None:
    # Users arrive from Debian/Fedora spellings. Arch package names are
    # lowercase, and some familiar names have a different Arch package.
    root = tmp_path / "root"
    root.mkdir()
    mark_synced(root)
    log = tmp_path / "pacman.args"
    fake = tmp_path / "pacman"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ "$1" = "--version" ]; then echo "Pacman v7.0.0"; exit 0; fi\n'
        'printf \'%s\\n\' "$*" >> "$GARB_FAKE_LOG"\n'
    )
    fake.chmod(0o755)
    env = os.environ.copy()
    env["GARB_BACKEND_BIN"] = str(fake)
    env["GARB_FAKE_LOG"] = str(log)
    result = run(root, "install", "kde-plasma", "NetworkManager", backend="pacman", env=env)
    assert result.returncode == 0, result.stderr
    assert log.read_text().splitlines() == [
        f"--root {root} -S --needed --noconfirm plasma-meta networkmanager"
    ]
