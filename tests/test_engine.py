import hashlib
import json
import tarfile
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Lock, Thread
from time import sleep
from typing import Iterator
from urllib.error import URLError

import pytest

from koreanfa import api, engine
from koreanfa.engine import install, remove, status
from koreanfa.errors import EngineNotFoundError, EngineUnavailableError


class _QuietArchiveHandler(SimpleHTTPRequestHandler):
    """Serve a test archive without writing request logs during pytest."""

    def log_message(self, format: str, *args: object) -> None:
        return None


@contextmanager
def _serve_directory(directory: Path) -> Iterator[str]:
    handler = partial(_QuietArchiveHandler, directory=str(directory))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address
        yield f"http://{host}:{port}"
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def _write_engine_archive(tmp_path: Path) -> tuple[Path, str]:
    source = tmp_path / "source" / "koreanfa-engine"
    kaldi_binary = source / "kaldi" / "src" / "bin" / "ali-to-phones"
    mecab_binary = source / "mecab" / "bin" / "mecab"
    kaldi_binary.parent.mkdir(parents=True)
    mecab_binary.parent.mkdir(parents=True)
    kaldi_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    mecab_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    kaldi_binary.chmod(0o755)
    mecab_binary.chmod(0o755)
    (source / "engine.json").write_text(
        json.dumps(
            {
                "kaldi_dir": "kaldi",
                "mecab_command": "mecab/bin/mecab",
                "mecab_dict": "mecab/lib/mecab/dic/ipadic",
                "mecabrc": "mecab/etc/mecabrc",
                "library_paths": ["kaldi/src/lib"],
            }
        ),
        encoding="utf-8",
    )
    (source / "mecab" / "lib" / "mecab" / "dic" / "ipadic").mkdir(parents=True)
    (source / "mecab" / "etc").mkdir(parents=True)
    (source / "mecab" / "etc" / "mecabrc").write_text("dicdir = ignored\n", encoding="utf-8")
    (source / "kaldi" / "src" / "lib").mkdir(parents=True)
    archive = tmp_path / "engine.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(source, arcname=source.name)
    checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
    return archive, checksum


def test_engine_install_verifies_and_locates_runtime(
    tmp_path: Path, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)

    installed = install(engine_home=tmp_path / "cache", manifest_path=manifest)

    assert installed.installed is True
    assert installed.kaldi_dir == installed.root / "kaldi"
    assert installed.environment["KOREANFA_MECAB_COMMAND"] == str(installed.root / "mecab" / "bin" / "mecab")
    assert installed.environment["KOREANFA_MECAB_DICT"] == str(installed.root / "mecab" / "lib" / "mecab" / "dic" / "ipadic")
    assert installed.environment["MECABRC"] == str(installed.root / "mecab" / "etc" / "mecabrc")
    assert installed.environment["LD_LIBRARY_PATH"] == str(installed.root / "kaldi" / "src" / "lib")
    assert status(engine_home=tmp_path / "cache", manifest_path=manifest) == installed
    assert remove(engine_home=tmp_path / "cache", manifest_path=manifest) is True


def test_engine_install_downloads_and_verifies_http_archive(
    tmp_path: Path, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    with _serve_directory(archive.parent) as base_url:
        manifest = write_test_manifest(
            tmp_path, url=f"{base_url}/{archive.name}", sha256=checksum
        )
        installed = install(engine_home=tmp_path / "cache", manifest_path=manifest)

    assert installed.installed is True
    assert installed.root == tmp_path / "cache" / "test-1" / engine._platform_tag()


def test_engine_download_retries_transient_network_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    source = tmp_path / "source.tar.gz"
    destination = tmp_path / "downloaded.tar.gz"
    source.write_bytes(b"verified engine archive")
    real_urlopen = engine.urlopen
    attempts: list[float] = []

    def flaky_urlopen(request, *, timeout: float):
        attempts.append(timeout)
        if len(attempts) < 3:
            raise URLError("temporary test outage")
        return real_urlopen(request, timeout=timeout)

    monkeypatch.setattr(engine, "urlopen", flaky_urlopen)
    monkeypatch.setattr(engine.time, "sleep", lambda _seconds: None)

    engine._download(source.as_uri(), destination, attempts=3, timeout=7.5)

    assert destination.read_bytes() == source.read_bytes()
    assert attempts == [7.5, 7.5, 7.5]


def test_engine_download_rejects_oversized_archives(tmp_path: Path) -> None:
    source = tmp_path / "oversized.tar.gz"
    destination = tmp_path / "downloaded.tar.gz"
    source.write_bytes(b"12345")

    with pytest.raises(EngineUnavailableError, match="too large|exceeded"):
        engine._download(source.as_uri(), destination, attempts=1, max_bytes=4)

    assert not destination.exists()


def test_concurrent_engine_installs_share_one_download(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    cache = tmp_path / "cache"
    download_started = Event()
    release_download = Event()
    counter_lock = Lock()
    download_count = 0
    real_download = engine._download

    def controlled_download(*args, **kwargs) -> None:
        nonlocal download_count
        with counter_lock:
            download_count += 1
        download_started.set()
        if not release_download.wait(timeout=5):
            raise RuntimeError("test did not release the controlled engine download")
        real_download(*args, **kwargs)

    monkeypatch.setattr(engine, "_download", controlled_download)
    with ThreadPoolExecutor(max_workers=2) as executor:
        first = executor.submit(install, engine_home=cache, manifest_path=manifest)
        assert download_started.wait(timeout=5)
        second = executor.submit(install, engine_home=cache, manifest_path=manifest)
        sleep(0.1)
        assert not second.done()
        release_download.set()
        first_status = first.result(timeout=10)
        second_status = second.result(timeout=10)

    assert first_status == second_status
    assert first_status.installed is True
    assert download_count == 1


def test_engine_manifest_can_be_overridden_for_candidate_testing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    write_test_manifest: Callable[..., Path],
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    monkeypatch.setenv("KOREANFA_ENGINE_MANIFEST", str(manifest))

    installed = install(engine_home=tmp_path / "cache")

    assert installed.installed is True
    assert status(engine_home=tmp_path / "cache") == installed


@pytest.mark.parametrize(
    ("manifest_data", "message"),
    [
        ([], "JSON object with string keys"),
        ({"engines": []}, "does not contain an engines mapping"),
        ({"engines": {"linux-x86_64": {"version": "2.0.0", "url": 7, "sha256": None}}}, "invalid URL"),
    ],
)
def test_engine_manifest_rejects_invalid_shapes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, manifest_data: object, message: str
) -> None:
    manifest_path = tmp_path / "invalid-manifest.json"
    manifest_path.write_text(json.dumps(manifest_data), encoding="utf-8")
    monkeypatch.setattr(engine.platform, "system", lambda: "Linux")
    monkeypatch.setattr(engine.platform, "machine", lambda: "x86_64")

    with pytest.raises(EngineUnavailableError, match=message):
        status(manifest_path=manifest_path)


def test_engine_install_rejects_checksum_mismatch(
    tmp_path: Path, write_test_manifest: Callable[..., Path]
) -> None:
    archive, _ = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256="0" * 64)

    with pytest.raises(EngineUnavailableError, match="checksum mismatch"):
        install(engine_home=tmp_path / "cache", manifest_path=manifest)


def test_force_install_preserves_a_working_engine_when_replacement_fails(
    tmp_path: Path, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    cache = tmp_path / "cache"
    install(engine_home=cache, manifest_path=manifest)
    broken_manifest = write_test_manifest(
        tmp_path,
        url=archive.as_uri(),
        sha256="0" * 64,
        filename="broken-manifest.json",
    )

    with pytest.raises(EngineUnavailableError, match="checksum mismatch"):
        install(force=True, engine_home=cache, manifest_path=broken_manifest)

    assert status(engine_home=cache, manifest_path=manifest).installed is True


def test_force_install_restores_the_previous_engine_when_promotion_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    cache = tmp_path / "cache"
    installed = install(engine_home=cache, manifest_path=manifest)
    real_rename = Path.rename

    def fail_replacement_promotion(source: Path, target: Path) -> Path:
        if source.name.startswith(f".{installed.platform}.new-"):
            raise OSError("simulated promotion failure")
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_replacement_promotion)

    with pytest.raises(OSError, match="simulated promotion failure"):
        install(force=True, engine_home=cache, manifest_path=manifest)

    assert status(engine_home=cache, manifest_path=manifest).installed is True
    assert not list(installed.root.parent.glob(f".{installed.platform}.backup-*"))


def test_force_install_keeps_backup_when_rollback_itself_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    cache = tmp_path / "cache"
    installed = install(engine_home=cache, manifest_path=manifest)
    real_rename = Path.rename

    def fail_promotion_and_rollback(source: Path, target: Path) -> Path:
        if source.name.startswith((f".{installed.platform}.new-", f".{installed.platform}.backup-")):
            raise OSError("simulated rename failure")
        return real_rename(source, target)

    monkeypatch.setattr(Path, "rename", fail_promotion_and_rollback)

    with pytest.raises(EngineUnavailableError, match="preserved backup remains"):
        install(force=True, engine_home=cache, manifest_path=manifest)

    backups = list(installed.root.parent.glob(f".{installed.platform}.backup-*"))
    assert len(backups) == 1
    assert (backups[0] / "engine.json").is_file()
    assert not installed.root.exists()


def test_first_install_removes_promoted_engine_if_final_validation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    cache = tmp_path / "cache"
    spec = engine._engine_spec(manifest)
    real_status_for = engine._status_for
    status_calls = 0

    def fail_final_status(candidate_spec: engine.EngineSpec, home: Path) -> engine.EngineStatus:
        nonlocal status_calls
        status_calls += 1
        if status_calls == 2:
            return engine._missing_status(candidate_spec, home / candidate_spec.version / candidate_spec.platform)
        return real_status_for(candidate_spec, home)

    monkeypatch.setattr(engine, "_status_for", fail_final_status)

    with pytest.raises(EngineNotFoundError, match="invalid after installation"):
        install(engine_home=cache, manifest_path=manifest)

    assert not (cache / spec.version / spec.platform).exists()


def test_engine_status_rejects_missing_japanese_runtime(
    tmp_path: Path, write_test_manifest: Callable[..., Path]
) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = write_test_manifest(tmp_path, url=archive.as_uri(), sha256=checksum)
    cache = tmp_path / "cache"
    installed = install(engine_home=cache, manifest_path=manifest)
    (installed.root / "mecab" / "lib" / "mecab" / "dic" / "ipadic").rmdir()

    assert status(engine_home=cache, manifest_path=manifest).installed is False


def test_alignment_runtime_uses_installed_engine(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    write_test_manifest: Callable[..., Path],
) -> None:
    manifest = write_test_manifest(tmp_path, url=None, sha256=None)
    monkeypatch.setenv("KOREANFA_ENGINE_MANIFEST", str(manifest))
    expected = status()
    engine_root = tmp_path / "cache" / expected.version / expected.platform
    binary = engine_root / "kaldi" / "src" / "bin" / "ali-to-phones"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    mecab = engine_root / "mecab" / "bin" / "mecab"
    mecab.parent.mkdir(parents=True)
    mecab.write_text("", encoding="utf-8")
    (engine_root / "mecab" / "lib" / "mecab" / "dic" / "ipadic").mkdir(parents=True)
    (engine_root / "mecab" / "etc").mkdir(parents=True)
    (engine_root / "mecab" / "etc" / "mecabrc").write_text("", encoding="utf-8")
    (engine_root / "lib").mkdir(parents=True)
    (engine_root / "engine.json").write_text(
        json.dumps(
            {
                "kaldi_dir": "kaldi",
                "mecab_command": "mecab/bin/mecab",
                "mecab_dict": "mecab/lib/mecab/dic/ipadic",
                "mecabrc": "mecab/etc/mecabrc",
                "library_paths": ["lib"],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "cache"))

    runtime, environment = api._resolve_kaldi_dir(None)

    assert runtime == engine_root / "kaldi"
    assert environment["KOREANFA_MECAB_COMMAND"] == str(mecab)


@pytest.mark.parametrize(
    ("system", "machine", "expected"),
    [
        ("Darwin", "arm64", "darwin-arm64"),
        ("Darwin", "aarch64", "darwin-arm64"),
        ("Darwin", "x86_64", "darwin-x86_64"),
        ("Darwin", "amd64", "darwin-x86_64"),
    ],
)
def test_platform_tag_normalizes_macos_architectures(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str, expected: str
) -> None:
    monkeypatch.setattr(engine.platform, "system", lambda: system)
    monkeypatch.setattr(engine.platform, "machine", lambda: machine)

    assert engine._platform_tag() == expected


def test_macos_engine_uses_platform_cache_location(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("KOREANFA_ENGINE_HOME", raising=False)
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setattr(engine.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(engine.Path, "home", classmethod(lambda cls: tmp_path / "home"))

    assert engine._engine_home() == (tmp_path / "home" / "Library" / "Caches" / "koreanfa" / "engines").resolve()


def test_macos_engine_uses_fallback_dynamic_library_path(tmp_path: Path) -> None:
    source = tmp_path / "engine"
    kaldi_binary = source / "kaldi" / "src" / "bin" / "ali-to-phones"
    mecab_binary = source / "mecab" / "bin" / "mecab"
    kaldi_binary.parent.mkdir(parents=True)
    mecab_binary.parent.mkdir(parents=True)
    kaldi_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    mecab_binary.write_text("#!/bin/sh\n", encoding="utf-8")
    kaldi_binary.chmod(0o755)
    mecab_binary.chmod(0o755)
    (source / "mecab" / "lib" / "mecab" / "dic" / "ipadic").mkdir(parents=True)
    (source / "mecab" / "etc").mkdir(parents=True)
    (source / "mecab" / "etc" / "mecabrc").write_text("", encoding="utf-8")
    (source / "lib").mkdir()
    (source / "engine.json").write_text(
        json.dumps(
            {
                "kaldi_dir": "kaldi",
                "mecab_command": "mecab/bin/mecab",
                "mecab_dict": "mecab/lib/mecab/dic/ipadic",
                "mecabrc": "mecab/etc/mecabrc",
                "library_paths": ["lib"],
                "library_path_variable": "DYLD_FALLBACK_LIBRARY_PATH",
            }
        ),
        encoding="utf-8",
    )
    spec = engine.EngineSpec("darwin-arm64", "test-1", None, None)

    installed = engine._status_from_root(spec, source)

    assert installed.installed is True
    assert installed.environment["DYLD_FALLBACK_LIBRARY_PATH"] == str(source / "lib")
    assert "LD_LIBRARY_PATH" not in installed.environment


def test_library_paths_are_prepended_without_overwriting_existing_values() -> None:
    environment = {"DYLD_FALLBACK_LIBRARY_PATH": "/existing/dylibs", "MECABRC": "/caller/mecabrc"}

    api._merge_engine_environment(
        environment,
        {
            "DYLD_FALLBACK_LIBRARY_PATH": "/engine/lib",
            "MECABRC": "/engine/mecabrc",
        },
    )

    assert environment["DYLD_FALLBACK_LIBRARY_PATH"] == "/engine/lib:/existing/dylibs"
    assert environment["MECABRC"] == "/caller/mecabrc"


def test_alignment_runtime_explains_how_to_install_when_missing(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    write_test_manifest: Callable[..., Path],
) -> None:
    manifest = write_test_manifest(tmp_path, url=None, sha256=None)
    monkeypatch.setenv("KOREANFA_ENGINE_MANIFEST", str(manifest))
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "empty-cache"))

    with pytest.raises(EngineNotFoundError, match="native engine is required"):
        api._resolve_kaldi_dir(None)
