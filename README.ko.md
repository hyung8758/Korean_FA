# KoreanFA

[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Linux](https://img.shields.io/badge/Linux-x86__64-FCC624?logo=linux&logoColor=black)](#%EC%A7%80%EC%9B%90-%ED%99%98%EA%B2%BD)
[![macOS](https://img.shields.io/badge/macOS-12%2B%20%7C%20Apple%20Silicon%20%7C%20Intel-000000?logo=apple&logoColor=white)](#%EC%A7%80%EC%9B%90-%ED%99%98%EA%B2%BD)
[![License](https://img.shields.io/badge/License-Apache--2.0%20%2B%20proprietary-3DA639)](license)

[English](README.md)

KoreanFA는 한국어와 일본어 WAV 음성 및 UTF-8 전사를 입력받아 Praat TextGrid를 만드는 강제 정렬 라이브러리입니다. Python API와 CLI를 제공하며, 기본적으로 전사 텍스트를 분석해 한국어·일본어 모델을 자동 선택합니다.

## 주요 기능

- WAV/TXT 한 쌍 또는 디렉터리 전체를 정렬
- 한국어·일본어 모델 자동 선택 또는 직접 지정
- Praat TextGrid의 단어·음소 tier 생성
- Docker나 웹 서버 없이 관리형 Kaldi 기반 엔진 사용

## 지원 환경

- Linux x86_64
- Apple Silicon(arm64) 또는 Intel(x86_64) 기반 macOS 12 이상
- Python 3.12 또는 3.13
- WAV 음성 파일과 UTF-8 TXT 전사 파일

Windows는 아직 지원하지 않습니다. KoreanFA는 지원되는 Linux 또는 macOS 환경에 맞는 네이티브 엔진을 자동으로 내려받습니다.

## 소스 설치

KoreanFA는 아직 PyPI에 등록되지 않았습니다. 일반적인 `pip install koreanfa` 방식은 추후 PyPI 배포 후 제공될 예정입니다. 그전까지는 지원되는 Linux 또는 macOS 환경에서 GitHub의 최신 소스를 내려받아 설치한 뒤, 호환 엔진을 최초 한 번 설치하세요.

```bash
git clone --depth 1 https://github.com/hyung8758/Korean_FA.git
cd Korean_FA
python -m pip install .
koreanfa engine install
```

엔진 상태는 언제든 확인할 수 있습니다.

```bash
koreanfa engine status
```

엔진이 없는 상태에서 정렬을 실행하면 설치 방법을 안내하는 오류가 표시됩니다.

## CLI 사용법

WAV/TXT 한 쌍을 정렬합니다.

```bash
koreanfa align recording.wav recording.txt
```

기본적으로 입력 WAV와 같은 위치에 `recording.TextGrid`가 생성됩니다.

디렉터리에 있는 모든 WAV/TXT 쌍을 정렬합니다.

```bash
koreanfa align corpus
koreanfa align corpus -r -o aligned
```

같은 상대 경로와 파일 이름을 가진 파일을 한 쌍으로 처리합니다. 예를 들어 `session_01.wav`에는 `session_01.txt`가 필요합니다. 기본적으로 짝이 없는 파일이 있으면 기본적으로 해당 파일을 건너뛰고 경고를 출력합니다.

CLI는 파일별 준비·디코딩 단계, 디렉터리 진행 막대, 마지막 `total / success / failed` 요약을 출력합니다. 일부 파일이 실패해도 성공한 파일의 TextGrid는 보존하며, CLI는 실패 파일과 사유를 출력한 뒤 종료 코드 2로 끝납니다. 진단을 위해 `logs/summary.tsv`와 파일별 Kaldi 로그를 보관하려면 `--keep-workdir`를 사용하세요.

### 언어 모델 선택

기본값은 `-l auto`, `--lang auto`입니다. 한글 텍스트는 한국어 모델을, 히라가나·가타카나·한자 텍스트는 일본어 모델을 선택합니다. 문자가 섞인 전사는 모델을 명시적으로 지정하세요. 디렉터리 정렬에서 두 문자 체계가 없는 전사(예: `<laugh>`, 영어만 있는 문장)는 `batch.failures`에 실패로 기록되고, 나머지 파일은 계속 처리합니다.

```bash
koreanfa align recording.wav recording.txt -l kor
koreanfa align recording.wav recording.txt -l jap
```

전체 옵션은 `koreanfa align --help`에서 확인할 수 있습니다.

### 정렬 옵션

- `-nj N`, `--num-jobs N`: 최대 `N`개 파일을 동시에 정렬합니다. 기본값은 4이며 Python에서는 `num_jobs=N`으로 지정합니다.
- `-o DIR`, `--output-dir DIR`: TextGrid를 `DIR` 아래에 저장합니다 (`output_dir=DIR`).
- `-kd DIR`, `--kaldi-dir DIR`: 외부 Kaldi runtime을 사용합니다 (`kaldi_dir=DIR`).
- `-l {auto,kor,jap}`, `--lang ...`: 언어 어댑터를 선택합니다 (`lang=...`).
- `-r`, `--recursive`: 디렉터리 정렬 시 하위 디렉터리도 포함합니다 (`recursive=True`).
- `-iu`, `--ignore-unmatched [true|false]`: 같은 이름의 짝이 없는 WAV/TXT 파일을 경고와 함께 건너뜁니다. 기본값은 true이며 (`ignore_unmatched=True`), `false`로 지정하면 짝이 없는 파일을 발견한 시점에 정렬 전에 중단합니다.
- `-nw`, `--no-word`; `-np`, `--no-phone`: 해당 TextGrid tier를 만들지 않습니다 (`word_tier=False`, `phone_tier=False`).
- `-kw`, `--keep-workdir`: 성공한 실행의 Kaldi 로그와 진단 작업 파일을 보관합니다 (`keep_workdir=True`).

명령 도움말은 `-h`, `--help`로, 패키지 버전은 `-v`, `--version`으로 확인합니다.

## Python API

엔진을 최초 한 번 설치한 후, WAV/TXT 한 쌍을 정렬합니다.

```python
from koreanfa import align, install_engine

install_engine()
result = align("recording.wav", "recording.txt", lang="auto")
print(result.textgrid)
print(result.language)  # "kor" 또는 "jap"
```

디렉터리 정렬에는 `Aligner`를 사용합니다.

```python
from koreanfa import Aligner

aligner = Aligner(lang="auto", num_jobs=4)
batch = aligner.align("corpus", recursive=True)
for result in batch.results:
    print(result.textgrid)
for failure in batch.failures:
    print(f"제외됨: {failure.audio} ({failure.reason})")
```

라이브러리 함수는 기본적으로 진행 로그를 출력하지 않으며, 짝이 없는 입력 파일은 Python 경고 시스템으로 알립니다. 호스트 프로그램에서 진행 상태가 필요하면 `progress` 콜백을 넘기고, `logs/summary.tsv`를 보관하려면 `keep_workdir=True`를 사용하세요. 디렉터리 정렬 결과에서 성공 파일은 `batch.results`, 정상적으로 제외된 파일은 `batch.failures`로 각각 확인할 수 있습니다.

## 입력 자료 안내

- WAV마다 짝이 되는 UTF-8 `.txt` 전사가 필요합니다.
- TXT 한 파일에는 한 문장을 넣는 방식을 권장합니다.
- 음성은 임시 작업 공간에서 mono, 16 kHz PCM WAV로 정규화됩니다.
- 한국어 발음 변환에는 `ko-speech-tools`와 한국어 MeCab 사전이 패키지 의존성으로 함께 설치되므로, 별도의 한국어 G2P 설치는 필요하지 않습니다.
- 일본어 정렬에 필요한 MeCab과 IPADIC은 관리형 엔진에 포함됩니다.

## 엔진 관리

```bash
koreanfa engine install
koreanfa engine status
koreanfa engine install -f
koreanfa engine remove -y
```

`KOREANFA_ENGINE_HOME`으로 엔진 cache 위치를 변경할 수 있습니다. 고급 사용자는 `KOREANFA_KALDI_DIR` 또는 `kaldi_dir=`로 외부 Kaldi runtime을 지정할 수 있습니다.

## 라이선스

KoreanFA 코드와 일본어 음향 모델은 [Apache-2.0](license)으로 배포됩니다. 한국어 음향 모델은 Mediazen의 proprietary 자산으로 KoreanFA에서만 사용할 수 있으며, 이용 조건은 [모델 고지](koreanfa/runtime/model/kor_model/NOTICE.md)를 확인하세요. 포함 소스와 별도 다운로드되는 엔진의 고지는 [제3자 고지](THIRD_PARTY_NOTICES.md)를 확인하세요.
