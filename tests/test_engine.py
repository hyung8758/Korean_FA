import hashlib
import json
import tarfile
from pathlib import Path

import pytest

from koreanfa import api
from koreanfa.engine import install, remove, status
from koreanfa.errors import EngineNotFoundError, EngineUnavailableError


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


def _write_manifest(tmp_path: Path, archive: Path, checksum: str) -> Path:
    platform = status().platform
    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps({"schema_version": 1, "engines": {platform: {"version": "test-1", "url": archive.as_uri(), "sha256": checksum}}}),
        encoding="utf-8",
    )
    return manifest


def test_engine_install_verifies_and_locates_runtime(tmp_path: Path) -> None:
    archive, checksum = _write_engine_archive(tmp_path)
    manifest = _write_manifest(tmp_path, archive, checksum)

    installed = install(engine_home=tmp_path / "cache", manifest_path=manifest)

    assert installed.installed is True
    assert installed.kaldi_dir == installed.root / "kaldi"
    assert installed.environment["KOREANFA_MECAB_COMMAND"] == str(installed.root / "mecab" / "bin" / "mecab")
    assert installed.environment["KOREANFA_MECAB_DICT"] == str(installed.root / "mecab" / "lib" / "mecab" / "dic" / "ipadic")
    assert installed.environment["MECABRC"] == str(installed.root / "mecab" / "etc" / "mecabrc")
    assert status(engine_home=tmp_path / "cache", manifest_path=manifest) == installed
    assert remove(engine_home=tmp_path / "cache", manifest_path=manifest) is True


def test_engine_install_rejects_checksum_mismatch(tmp_path: Path) -> None:
    archive, _ = _write_engine_archive(tmp_path)
    manifest = _write_manifest(tmp_path, archive, "0" * 64)

    with pytest.raises(EngineUnavailableError, match="checksum mismatch"):
        install(engine_home=tmp_path / "cache", manifest_path=manifest)


def test_alignment_runtime_uses_installed_engine(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    engine_root = tmp_path / "cache" / "0.3.0" / status().platform
    binary = engine_root / "kaldi" / "src" / "bin" / "ali-to-phones"
    binary.parent.mkdir(parents=True)
    binary.write_text("", encoding="utf-8")
    mecab = engine_root / "mecab" / "bin" / "mecab"
    mecab.parent.mkdir(parents=True)
    mecab.write_text("", encoding="utf-8")
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "cache"))

    runtime, environment = api._resolve_kaldi_dir(None)

    assert runtime == engine_root / "kaldi"
    assert environment["KOREANFA_MECAB_COMMAND"] == str(mecab)


def test_alignment_runtime_explains_how_to_install_when_missing(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KOREANFA_ENGINE_HOME", str(tmp_path / "empty-cache"))

    with pytest.raises(EngineNotFoundError, match="native engine is required"):
        api._resolve_kaldi_dir(None)
