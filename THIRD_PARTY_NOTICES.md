# KoreanFA third-party notices

This document identifies third-party source material redistributed with the
KoreanFA Python package. It is an attribution notice, not a replacement for
the applicable upstream licence texts.

## Python distribution

- **Kaldi-derived scripts and utilities** — Apache License 2.0. Upstream
  copyright and licence headers are retained in the redistributed source
  files.
- **Japanese `vocab2dic.pl` utility** — Apache License 2.0. Copyright notices
  for Tokyo Institute of Technology and Mitsubishi Electric Research
  Laboratories are retained in the source file.

## Linux engine (`koreanfa engine install`)

The separately downloaded engine archive is a different distributable from the
Python wheel. It includes complete, version-matched notice text in its
`licenses/` directory:

- `KALDI.txt` — Kaldi, Apache License 2.0.
- `OPENFST.txt` — OpenFst, Apache License 2.0.
- `OPENBLAS.txt` — OpenBLAS, BSD 3-Clause License.
- `MECAB.txt` — MeCab attribution and BSD License.
- `IPADIC.txt` — MeCab IPADIC notice and distribution conditions.
- `GCC-RUNTIME.txt` — GCC runtime libraries (`libgcc_s`, `libstdc++`,
  `libgfortran`, and `libquadmath`), GPLv3 with the GCC Runtime Library
  Exception 3.1.
- `ZLIB.txt` — zlib license.

The engine build script creates these files from the exact pinned source or
build-image package used for that archive. Do not remove or alter this
directory when redistributing an engine archive.
