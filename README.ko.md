# KoreanFA

[![PyPI](https://img.shields.io/pypi/v/koreanfa?logo=pypi&logoColor=white)](https://pypi.org/project/koreanfa/)
[![Python](https://img.shields.io/badge/Python-3.12%20%7C%203.13-3776AB?logo=python&logoColor=white)](https://github.com/hyung8758/Korean_FA/blob/master/pyproject.toml)
[![Ubuntu](https://img.shields.io/badge/Ubuntu-22.04%20%7C%2024.04%20LTS-E95420?logo=ubuntu&logoColor=white)](#%EC%A7%80%EC%9B%90-%ED%99%98%EA%B2%BD)
[![macOS](https://img.shields.io/badge/macOS-12%2B%20%7C%20Apple%20Silicon%20%7C%20Intel-000000?logo=apple&logoColor=white)](#%EC%A7%80%EC%9B%90-%ED%99%98%EA%B2%BD)
[![License](https://img.shields.io/badge/License-Apache--2.0%20%2B%20proprietary-3DA639)](https://github.com/hyung8758/Korean_FA/blob/master/license)

[English](https://github.com/hyung8758/Korean_FA/blob/master/README.md)

KoreanFA는 한국어와 일본어 WAV 음성 및 UTF-8 전사를 입력받아 Praat TextGrid를 만드는 강제 정렬 라이브러리입니다. Python API와 CLI를 제공하며, 기본적으로 전사 텍스트를 분석해 한국어·일본어 모델을 자동 선택합니다.

## 주요 기능

- WAV/TXT 한 쌍 또는 디렉터리 전체를 정렬
- 한국어·일본어 모델 자동 선택 또는 직접 지정
- Praat TextGrid의 단어·음소 tier 생성
- 정렬 전 코퍼스 검증과 재현 가능한 JSON 실행 리포트 생성
- 구조화 구간을 JSON, CSV, 단어·음소 CTM으로 내보내기
- 토큰별 사용자 발음 사전과 한국어 G2P/OOV 사전 점검
- Kaldi를 다시 실행하지 않고 검토가 필요한 TextGrid를 진단
- Docker나 웹 서버 없이 관리형 Kaldi 기반 엔진 사용

## 지원 환경

- glibc 2.17 이상인 Linux x86_64
  - 공식 지원 및 검증: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS
  - 이전 Ubuntu 버전과 기타 glibc 기반 Linux 배포판에서도 동작할 수 있지만 현재 KoreanFA의 공식 테스트 범위에는 포함되지 않습니다
- Apple Silicon(arm64) 또는 Intel(x86_64) 기반 macOS 12 이상
- Python 3.12 또는 3.13
- WAV 음성 파일과 UTF-8 TXT 전사 파일

Windows는 아직 지원하지 않습니다. KoreanFA는 지원되는 Linux 또는 macOS 환경에 맞는 네이티브 엔진을 자동으로 내려받습니다.

## 설치

PyPI에서 KoreanFA를 설치한 뒤, 현재 시스템에 맞는 네이티브 정렬 엔진을 최초 한 번 설치합니다.

```bash
python -m pip install koreanfa
koreanfa engine install
```

원격 기본 브랜치의 최신 개발 소스를 사용하려면 다음과 같이 설치합니다.

```bash
git clone --depth 1 https://github.com/hyung8758/Korean_FA.git
cd Korean_FA
python -m pip install .
koreanfa engine install
```

엔진 상태는 다음 명령으로 언제든 확인할 수 있습니다.

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

같은 상대 경로와 파일 이름을 가진 파일을 한 쌍으로 처리합니다. 예를 들어 `session_01.wav`에는 `session_01.txt`가 필요합니다. 짝이 없는 파일은 기본적으로 건너뛰고 경고를 출력합니다.

Kaldi 정렬을 시작하지 않고 파일 pairing, UTF-8 전사, 언어 감지, WAV 전체 디코딩, 엔진 준비 상태를 검사할 수 있습니다.

```bash
koreanfa validate corpus -r --report validation.json
```

검증은 첫 오류에서 멈추지 않고 발견한 문제를 모두 수집합니다. 오류가 있으면 종료 코드 2를 반환하며, `--strict`를 사용하면 경고도 실패로 처리합니다. 정렬을 실행하지 않을 컴퓨터에서 데이터만 검사할 때는 `--no-engine-check`를 사용할 수 있습니다.

CLI는 파일별 준비·디코딩 단계, 디렉터리 진행 막대, 마지막 `total / success / failed / skipped` 요약을 출력합니다. 일부 파일이 실패해도 성공한 파일의 TextGrid는 보존하며, CLI는 실패 파일과 사유를 출력한 뒤 종료 코드 2로 끝납니다. 진단을 위해 `logs/summary.tsv`와 파일별 Kaldi 로그를 보관하려면 `--keep-workdir`를 사용하세요.

### 언어 모델 선택

기본값은 `-l auto`, `--lang auto`입니다. 한글 텍스트는 한국어 모델을, 히라가나·가타카나·한자 텍스트는 일본어 모델을 선택합니다. 문자가 섞인 전사는 모델을 명시적으로 지정하세요. 디렉터리 정렬에서 두 문자 체계가 없는 전사(예: `<laugh>`, 영어만 있는 문장)는 `batch.failures`에 실패로 기록되고, 나머지 파일은 계속 처리합니다.

```bash
koreanfa align recording.wav recording.txt -l kor
koreanfa align recording.wav recording.txt -l jap
```

전체 옵션은 `koreanfa align --help`에서 확인할 수 있습니다.

### 정렬 옵션

- `-nj N`, `--num-jobs N`: 최대 `N`개의 파일 작업자를 동시에 실행하며, 각 작업자는 이전 파일이 끝나는 즉시 다음 pair를 처리합니다. 기본값은 4이며 Python에서는 `num_jobs=N`으로 지정합니다.
- `-o DIR`, `--output-dir DIR`: TextGrid를 `DIR` 아래에 저장합니다 (`output_dir=DIR`).
- `-kd DIR`, `--kaldi-dir DIR`: 외부 Kaldi runtime을 사용합니다 (`kaldi_dir=DIR`).
- `-l {auto,kor,jap}`, `--lang ...`: 언어 어댑터를 선택합니다 (`lang=...`).
- `-r`, `--recursive`: 디렉터리 정렬 시 하위 디렉터리도 포함합니다 (`recursive=True`).
- `-iu`, `--ignore-unmatched [true|false]`: 같은 이름의 짝이 없는 WAV/TXT 파일을 경고와 함께 건너뜁니다. 기본값은 true이며 (`ignore_unmatched=True`), `false`로 지정하면 짝이 없는 파일을 발견한 시점에 정렬 전에 중단합니다.
- `-nw`, `--no-word`; `-np`, `--no-phone`: 해당 TextGrid tier를 만들지 않습니다 (`word_tier=False`, `phone_tier=False`).
- `-kw`, `--keep-workdir`: 성공한 실행의 Kaldi 로그와 진단 작업 파일을 보관합니다 (`keep_workdir=True`).
- `--existing {overwrite,skip,error}`: 기존 TextGrid를 덮어쓰거나(호환성을 위한 기본값), 구조가 올바른 TextGrid는 재정렬하지 않거나, 요청 출력이 하나라도 있으면 정렬 전에 중단합니다 (`existing=...`). 올바른 TextGrid를 건너뛸 때도 요청한 JSON/CSV/CTM은 기존 TextGrid에서 생성하며, 손상된 TextGrid는 성공한 파일로 건너뛰지 않습니다.
- `--export {json,csv,ctm}`: 기계 판독용 형식을 추가로 생성합니다. 여러 형식은 옵션을 반복합니다 (`exports=("json", "csv", "ctm")`). CTM은 단어·음소 파일로 나뉘며 빈 gap 구간만 제외하고, 코퍼스 기준 상대 stem을 recording ID로 사용합니다. CTM의 5필드 구조를 유지하도록 recording ID와 label의 공백·제어 문자·`%`는 UTF-8 퍼센트 인코딩하며, JSON과 CSV의 label은 원문 그대로 유지합니다.
- `--pronunciation-dictionary PATH`: UTF-8 TSV의 정확한 토큰별 발음 override를 적용합니다. 자세한 형식은 [발음 사전 안내](docs/pronunciation-dictionary.md)를 참고하세요.
- `--report PATH`: 상대 경로, 옵션, 성공·실패·건너뜀, 시도 횟수, 엔진 메타데이터가 담긴 버전형 JSON 실행 리포트를 원자적으로 저장합니다 (`report_path=PATH`). 전사 원문은 리포트에 복사하지 않습니다.
- `--quality-report PATH`: 정렬 뒤 별도 JSON TextGrid 품질 진단 리포트를 작성합니다 (`quality_report_path=PATH`). `review`는 확인이 필요한 후보를 뜻하며, 정렬 실패나 신뢰도 점수는 아닙니다. 자세한 기준은 [품질 진단 안내](docs/alignment-quality.md)를 참고하세요.

네이티브 라이브러리의 작업자별 스레드를 더 엄격히 제한해야 하는 환경에서는 `KOREANFA_THREADS_PER_JOB`에 양의 정수를 설정할 수 있습니다. 기본값은 파일 작업자별 `1`입니다.

### 발음 사전과 OOV 점검

특정 한국어·일본어 토큰에 원하는 읽기를 적용하려면 UTF-8 TSV 발음 사전을 선택적으로 전달합니다. 헤더와 정확히 세 개의 탭 구분 열이 필요합니다.

```tsv
language	word	pronunciation
kor	KoreanFA	코리안에프에이
jap	大切	タイセツ
```

`word`와 `pronunciation`은 공백 없는 하나의 토큰이어야 합니다. 한국어 발음은 한글로, 일본어 발음은 히라가나 또는 가타카나로 적습니다(내부적으로 가타카나로 정규화). 한국어는 공백으로 나눈 정확한 토큰에, 일본어는 MeCab가 만든 정확한 표층형에 적용됩니다.
전사에 한글·일본어 문자가 전혀 없다면 override만으로 자동 언어 감지가 바뀌지는 않으므로 `--lang kor` 또는 `--lang jap`으로 사용할 모델을 명시하세요.

정렬 전에 아래처럼 실행하면 사전 형식과 기본 한국어 G2P가 발음으로 바꾸지 못하는 토큰을 점검할 수 있습니다.

```bash
koreanfa validate corpus --pronunciation-dictionary pronunciations.tsv
koreanfa align corpus --pronunciation-dictionary pronunciations.tsv
```

명령 도움말은 `-h`, `--help`로, 패키지 버전은 `-v`, `--version`으로 확인합니다.

## Python API

엔진을 최초 한 번 설치한 후, WAV/TXT 한 쌍을 정렬합니다.

```python
from koreanfa import align, install_engine

install_engine()
result = align("recording.wav", "recording.txt", lang="auto")
print(result.textgrid)
print(result.language)  # "kor" 또는 "jap"
for word in result.words:
    print(word.start, word.end, word.label)
```

디렉터리 정렬에는 `Aligner`를 사용합니다.

```python
from koreanfa import Aligner

aligner = Aligner(lang="auto", num_jobs=4)
batch = aligner.align(
    "corpus",
    output_dir="aligned",
    recursive=True,
    existing="skip",
    exports=("json", "csv", "ctm"),
    report_path="aligned/run.json",
    quality_report_path="aligned/quality.json",
    pronunciation_dictionary="pronunciations.tsv",
)
for result in batch.results:
    print(result.textgrid, result.outputs["json"])
for skipped in batch.skipped:
    print(f"변경 없음: {skipped.textgrid}")
for failure in batch.failures:
    print(f"제외됨: {failure.audio} ({failure.reason})")
if batch.quality_report:
    print(batch.quality_report.path, batch.quality_report.summary.review)
```

`result.words`와 `result.phones`에는 이름이 있는 무음 구간을 포함한 초 단위 typed interval이 들어 있습니다. `result.outputs`에서 생성된 모든 파일을 확인할 수 있습니다. 디렉터리 결과는 성공 파일을 `batch.results`, 올바른 기존 출력을 `batch.skipped`, 처리하지 못한 파일을 `batch.failures`에 담으며, 합계와 경과 시간은 `batch.summary`에서 확인합니다.

라이브러리 함수는 기본적으로 진행 로그를 출력하지 않으며, 짝이 없는 입력 파일은 Python 경고 시스템으로 알립니다. 호스트 프로그램에서 진행 상태가 필요하면 `progress` 콜백을 넘기고, `logs/summary.tsv`를 보관하려면 `keep_workdir=True`를 사용하세요.

Python에서도 `validate("corpus", recursive=True)`로 같은 사전 검증을 실행할 수 있습니다. 반환되는 `ValidationReport`에는 올바른 pair와 발견한 구조화 문제가 모두 들어 있으며, 데이터만 검사할 때는 `check_engine=False`를 지정합니다.

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

`KOREANFA_ENGINE_HOME`으로 엔진 캐시 위치를 변경할 수 있습니다. 고급 사용자는 `KOREANFA_KALDI_DIR` 또는 `kaldi_dir=`로 외부 Kaldi 런타임을 지정할 수 있습니다.

엔진 다운로드 또는 체크섬 검증에 실패하면 [엔진 설치 문제 해결 문서(영문)](https://github.com/hyung8758/Korean_FA/blob/master/docs/troubleshooting.md)를 확인하세요. KoreanFA는 SHA-256 체크섬이 배포 manifest와 일치하지 않는 엔진을 설치하지 않습니다.

## 인용

연구에서 KoreanFA를 사용한 경우 실제 연구에 사용한 버전을 명시하여 인용해 주세요. 인용 메타데이터는 [`CITATION.cff`](https://github.com/hyung8758/Korean_FA/blob/master/CITATION.cff)와 GitHub 저장소의 **Cite this repository** 메뉴에서 확인할 수 있습니다.

## 라이선스

KoreanFA 코드와 일본어 음향 모델은 [Apache-2.0](https://github.com/hyung8758/Korean_FA/blob/master/license)으로 배포됩니다. 한국어 음향 모델은 Mediazen의 독점 자산이며 상업적·비상업적 목적 모두에 사용할 수 있지만 KoreanFA의 구성 요소로만 사용해야 합니다. 모델을 수정하거나 별도로 재배포하려면 Mediazen의 사전 서면 허가가 필요합니다. 자세한 내용은 한국어 모델 [고지](https://github.com/hyung8758/Korean_FA/blob/master/koreanfa/runtime/model/kor_model/NOTICE.md)를 확인하세요. 예제 데이터에는 별도 조건이 적용되므로 [예제 데이터 고지](https://github.com/hyung8758/Korean_FA/blob/master/example/NOTICE.md)를 확인하세요. 포함 소스와 별도 다운로드되는 엔진의 고지는 [제3자 고지](https://github.com/hyung8758/Korean_FA/blob/master/THIRD_PARTY_NOTICES.md)를 확인하세요.
