# KoreanFA

[![Python](https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white)](pyproject.toml)
[![Platform](https://img.shields.io/badge/Platform-Linux%20x86__64-FCC624?logo=linux&logoColor=black)](#%EC%A7%80%EC%9B%90-%ED%99%98%EA%B2%BD)
[![License](https://img.shields.io/badge/License-Apache--2.0%20%2B%20proprietary-3DA639)](license)

[English](README.md)

KoreanFA는 한국어와 일본어 WAV 음성 및 UTF-8 전사를 입력받아 Praat TextGrid를
만드는 강제 정렬 라이브러리입니다. Python API와 CLI를 제공하며, 기본적으로 전사
텍스트를 분석해 한국어·일본어 모델을 자동 선택합니다.

## 주요 기능

- WAV/TXT 한 쌍 또는 디렉터리 전체를 정렬
- 한국어·일본어 모델 자동 선택 또는 직접 지정
- Praat TextGrid의 단어·음소 tier 생성
- Docker나 웹 서버 없이 관리형 Kaldi 기반 엔진 사용

## 지원 환경

- Linux x86_64
- Python 3.12 이상
- WAV 음성 파일과 UTF-8 TXT 전사 파일

macOS와 Windows는 아직 지원하지 않습니다.

## 소스 설치

KoreanFA는 아직 PyPI에 등록되지 않았습니다. 일반적인 `pip install koreanfa`
방식은 추후 PyPI 배포 후 제공될 예정입니다. 그전까지는 Linux x86_64 환경에서
GitHub의 최신 소스를 내려받아 설치한 뒤, 호환 엔진을 최초 한 번 설치하세요.

```bash
git clone --depth 1 https://github.com/hyung8758/Korean_FA.git
cd Korean_FA
pip install .
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
koreanfa align corpus --recursive --output-dir aligned
```

같은 상대 경로와 파일 이름을 가진 파일을 한 쌍으로 처리합니다. 예를 들어
`session_01.wav`에는 `session_01.txt`가 필요합니다. 기본적으로 짝이 없는 파일이
있으면 정렬을 멈추며, 완전한 쌍만 처리하려면 `--allow-unmatched`를 사용합니다.

### 언어 모델 선택

기본값은 `--lang auto`입니다. 한글 텍스트는 한국어 모델을, 히라가나·가타카나·한자
텍스트는 일본어 모델을 선택합니다. 문자가 섞인 전사는 모델을 명시적으로 지정하세요.

```bash
koreanfa align recording.wav recording.txt --lang kor
koreanfa align recording.wav recording.txt --lang jap
```

전체 옵션은 `koreanfa align --help`에서 확인할 수 있습니다.

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

aligner = Aligner(lang="auto", num_jobs=2)
batch = aligner.align("corpus", recursive=True)
for result in batch.results:
    print(result.textgrid)
```

## 입력 자료 안내

- WAV마다 짝이 되는 UTF-8 `.txt` 전사가 필요합니다.
- TXT 한 파일에는 한 문장을 넣는 방식을 권장합니다.
- 음성은 임시 작업 공간에서 mono, 16 kHz PCM WAV로 정규화됩니다.
- 한국어 발음 변환에는 `ko-speech-tools`와 한국어 MeCab 사전이 패키지 의존성으로
  함께 설치되므로, 별도의 한국어 G2P 설치는 필요하지 않습니다.
- 일본어 정렬에 필요한 MeCab과 IPADIC은 관리형 엔진에 포함됩니다.

## 엔진 관리

```bash
koreanfa engine install
koreanfa engine status
koreanfa engine install --force
koreanfa engine remove --yes
```

`KOREANFA_ENGINE_HOME`으로 엔진 cache 위치를 변경할 수 있습니다. 고급 사용자는
`KOREANFA_KALDI_DIR` 또는 `kaldi_dir=`로 외부 Kaldi runtime을 지정할 수 있습니다.

## 라이선스

KoreanFA 코드와 일본어 음향 모델은 [Apache-2.0](license)으로 배포됩니다.
한국어 음향 모델은 Mediazen의 proprietary 자산으로 KoreanFA에서만 사용할 수
있으며, 이용 조건은 [모델 고지](model/kor_model/NOTICE.md)를 확인하세요. 포함
소스와 별도 다운로드되는 엔진의 고지는 [제3자 고지](THIRD_PARTY_NOTICES.md)를
확인하세요.
