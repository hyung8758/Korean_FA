# KoreanFA third-party notices

This document identifies third-party source material redistributed with the KoreanFA Python package. It is an attribution notice, not a replacement for the applicable upstream licence texts.

## Python distribution

- **Kaldi-derived scripts and utilities** — Apache License 2.0. Upstream copyright and licence headers are retained in the redistributed source files.
- **Japanese `vocab2dic.pl` utility** — Apache License 2.0. Copyright notices for Tokyo Institute of Technology and Mitsubishi Electric Research Laboratories are retained in the source file.

## Python runtime dependencies

Korean pronunciation conversion is installed as a normal Python dependency, not copied into the KoreanFA wheel:

- **`ko-speech-tools` 0.1.0** — Apache License 2.0. Korean G2P implementation adapted by its upstream project from Apache-licensed sources; its wheel contains its own third-party notices, including CMUdict reader attribution.
- **`mecab-ko`** — MeCab Korean Python binding. KoreanFA uses its BSD licence option; its installed distribution retains the upstream MeCab notices.
- **`mecab-ko-dic`** — Apache License 2.0 Korean MeCab dictionary package.

These dependencies are distinct from the Japanese MeCab and IPADIC resources contained in the managed native engines below.

## Managed native engines (`koreanfa engine install`)

The separately downloaded engine archive is a different distributable from the Python wheel. Every supported engine includes complete, version-matched notice text for Kaldi, OpenFst, MeCab, and IPADIC in its `licenses/` directory:

- `KALDI.txt` — Kaldi, Apache License 2.0.
- `OPENFST.txt` — OpenFst, Apache License 2.0.
- `MECAB.txt` — MeCab attribution and BSD License.
- `IPADIC.txt` — MeCab IPADIC notice and distribution conditions.

The Linux x86_64 engine additionally redistributes these runtime components and notices:

- `OPENBLAS.txt` — OpenBLAS, BSD 3-Clause License.
- `GCC-RUNTIME.txt` — GCC runtime libraries (`libgcc_s`, `libstdc++`, `libgfortran`, and `libquadmath`), GPLv3 with the GCC Runtime Library Exception 3.1.
- `ZLIB.txt` — zlib license.

The macOS arm64 and x86_64 engines use Apple's system Accelerate framework and do not redistribute OpenBLAS or the GCC runtime libraries.

The engine build script creates these files from the exact pinned source or build-image package used for that archive. Do not remove or alter this directory when redistributing an engine archive.
