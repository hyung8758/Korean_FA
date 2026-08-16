# Engine installation troubleshooting

KoreanFA downloads a platform-specific native engine when you run:

```bash
koreanfa engine install
```

The installer verifies the downloaded archive against the SHA-256 checksum in the packaged engine manifest. It never extracts or installs an archive whose checksum does not match.

## Supported Linux environments

The published Linux engine requires:

- Linux x86_64
- glibc 2.17 or later

KoreanFA officially tests Ubuntu 22.04 LTS and Ubuntu 24.04 LTS. Older Ubuntu releases and other mainstream glibc-based distributions may satisfy the binary requirement, but they are not currently part of the official test matrix. Alpine Linux and other musl-based distributions are not supported.

Check the current architecture and libc version with:

```bash
uname -m
ldd --version | head -n 1
```

## Checksum mismatch

A checksum mismatch means that the bytes received by the installer differ from the immutable engine archive published by KoreanFA. Common causes include an interrupted transfer, a proxy or VPN, a network cache, a security gateway, or a temporary network problem.

Run the installer again first. A failed temporary download is removed, so the next command downloads a fresh copy:

```bash
koreanfa engine install
```

KoreanFA retries failed transfers and checksum mismatches up to three times. If all attempts fail, wait and try again later or test from another network. Do not bypass checksum verification.

Read the URL and expected checksum from the manifest installed with your KoreanFA version, then compare a direct download:

```bash
url=$(python -c 'import json; from importlib.resources import files; print(json.loads(files("koreanfa").joinpath("engine_manifest.json").read_text())["engines"]["linux-x86_64"]["url"])')
expected=$(python -c 'import json; from importlib.resources import files; print(json.loads(files("koreanfa").joinpath("engine_manifest.json").read_text())["engines"]["linux-x86_64"]["sha256"])')
archive="/tmp/koreanfa-linux-engine.tar.gz"

curl \
  --fail \
  --location \
  --retry 3 \
  --retry-all-errors \
  --output "$archive" \
  "$url"

wc -c "$archive"
sha256sum "$archive"
printf '%s  %s\n' "$expected" "$archive" | sha256sum --check --strict
```

The final command should report `OK`. If it reports `FAILED`, check whether a proxy, VPN, antivirus product, corporate security gateway, or network cache is changing the response. If the direct download is correct but `koreanfa engine install` still fails, open a GitHub issue with the diagnostics below.

## Information to include in an issue

```bash
python --version
python -m pip show koreanfa
uname -a
uname -m
ldd --version | head -n 1
koreanfa engine status
```

Also include the complete `koreanfa engine install` error and the file size and SHA-256 reported by the direct-download check. Do not include proxy credentials, access tokens, or other secrets.
