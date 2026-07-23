# KoreanFA

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

## 설치

Python 패키지를 설치한 다음, 호환되는 정렬 엔진을 최초 한 번 설치합니다.

```bash
python -m pip install koreanfa
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

KoreanFA는 [Apache-2.0](license)으로 배포됩니다.
