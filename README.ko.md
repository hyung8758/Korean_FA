# KoreanFA

[English documentation](README.md)

KoreanFA는 한국어와 일본어 음성을 위한 강제 정렬(forced alignment) 라이브러리입니다.
WAV 음성과 짝이 되는 전사 TXT를 입력하면 Praat TextGrid를 생성합니다. 현재 버전은
Docker나 웹 UI 없이 Python 라이브러리와 CLI로 사용합니다.

기본값은 `lang="auto"`이며, 전사 텍스트를 보고 한국어 또는 일본어 모델을 자동으로
선택합니다. Python 패키지와 Kaldi 기반 엔진은 별도로 버전 관리하므로 각각 독립적으로
업데이트할 수 있습니다.

## 지원 환경

첫 엔진 릴리스는 **Linux x86_64**, Python **3.12**를 지원합니다. macOS와 Windows용
엔진 archive는 아직 제공하지 않습니다.

## 설치

먼저 Python 패키지를 설치한 뒤, Kaldi·MeCab·IPADIC이 포함된 엔진을 최초 한 번
설치합니다.

```bash
python -m pip install koreanfa
koreanfa engine install
```

엔진은 KoreanFA GitHub Release에서 버전이 고정된 archive를 받아 SHA-256 검증 후
`~/.cache/koreanfa/engines/`에 설치합니다.

```bash
koreanfa engine status
```

엔진을 설치하지 않고 정렬을 실행하면, 정렬을 억지로 시작하지 않고 다음과 같이 설치
방법을 안내하는 오류가 발생합니다.

```text
KoreanFA engine is not installed. Run 'koreanfa engine install' ...
```

Python 코드에서도 엔진 설치를 명시적으로 수행할 수 있습니다.

```python
from koreanfa.engine import ensure_installed, install

install()                 # 최초 설치
ensure_installed()        # 엔진이 없으면 명확한 오류 발생
```

## CLI 사용법

### WAV/TXT 한 쌍 정렬

```bash
koreanfa align recording.wav recording.txt
```

기본적으로 `recording.TextGrid`가 WAV 파일과 같은 디렉터리에 저장됩니다.

### 디렉터리 단위 정렬

동일한 상대 경로와 이름을 가진 WAV/TXT를 자동으로 짝지어 정렬합니다. 예를 들어
`session_01.wav`와 `session_01.txt`는 하나의 입력 쌍입니다.

```bash
koreanfa align example/kor_files
koreanfa align example/jap_files
```

하위 디렉터리까지 탐색하려면 `--recursive`를 사용하고, 결과를 별도 위치에 저장하려면
`--output-dir`을 사용합니다.

```bash
koreanfa align corpus --recursive --output-dir aligned
```

### 언어 모델 지정

기본값 `--lang auto`에서는 한글 텍스트는 한국어 모델을, 히라가나·가타카나·한자 텍스트는
일본어 모델을 선택합니다. 한글과 일본어 문자가 섞여 있으면 명시적으로 모델을 지정해야
합니다.

```bash
koreanfa align recording.wav recording.txt --lang kor
koreanfa align recording.wav recording.txt --lang jap
```

그 밖에 `--no-word`, `--no-phone`, `--keep-workdir`, `--allow-unmatched` 옵션이
있습니다. 전체 옵션은 `koreanfa align --help`에서 확인할 수 있습니다.

## Python 라이브러리 사용법

### WAV/TXT 한 쌍

```python
from koreanfa import align

result = align("recording.wav", "recording.txt", lang="auto")
print(result.textgrid)
print(result.language)  # "kor" 또는 "jap"
```

### 디렉터리 단위

```python
from koreanfa import Aligner

aligner = Aligner(lang="auto", num_jobs=2)
batch = aligner.align("example/kor_files")
for result in batch.results:
    print(result.textgrid)
```

디렉터리 입력에서는 WAV/TXT가 모두 짝지어져 있어야 합니다. 기본적으로 짝이 없는 파일이
있으면 `PairingError`가 발생합니다. Python에서는 `strict=False`, CLI에서는
`--allow-unmatched`를 지정하면 완전한 쌍만 처리합니다.

## 입력 자료

- 읽을 수 있는 WAV 파일을 사용해야 합니다. KoreanFA가 임시 작업 공간에서 mono, 16 kHz,
  PCM WAV로 자동 정규화합니다.
- 전사는 UTF-8 `.txt` 파일이어야 하며 WAV와 짝이 맞아야 합니다.
- TXT 한 파일에는 한 문장을 넣는 방식을 권장합니다. 공백·탭·줄바꿈과 기존 파이프라인이
  지원하지 않는 문장부호는 정규화됩니다.
- 일본어 정렬에 필요한 MeCab과 IPADIC은 엔진에 포함되므로 별도의 시스템 설치가 필요하지
  않습니다.

## 엔진 관리

```bash
koreanfa engine install          # 호환되는 엔진 다운로드
koreanfa engine status           # 버전과 설치 경로 확인
koreanfa engine install --force  # 불완전한 같은 버전 엔진 교체
koreanfa engine remove --yes     # 호환 엔진 삭제
```

`KOREANFA_ENGINE_HOME`으로 엔진 cache 위치를 바꿀 수 있습니다. 고급 사용자는
`KOREANFA_KALDI_DIR` 또는 `kaldi_dir=`로 외부 Kaldi runtime을 지정할 수 있으며, 이
설정은 설치된 KoreanFA 엔진보다 우선합니다.

## 개발 및 배포 구조

- `koreanfa/`: 공개 Python API, CLI, 엔진 설치기, manifest
- `runtime/`: 기존 정렬 파이프라인과 설정
- `model/`: 한국어·일본어 음향 모델
- `engine/`: Linux 엔진 재현 빌더와 archive 검증기

Linux 엔진 workflow는 `master` 대상 PR에서 엔진 관련 파일이 바뀌면 자동으로 후보 빌드를
실행하며, 수동 실행도 지원합니다. `0.3.0` archive를 만들고 한국어·일본어 정렬까지
검증한 뒤, archive와 SHA-256 파일을 GitHub Actions artifact로 14일 동안 보관합니다.
이 workflow는 tag, GitHub Release, PyPI 배포를 만들지 않습니다.

기존 Docker/Web API 버전은 `docker_api` 브랜치와 `docker-api-v1.7.0` 태그에 보존돼
있습니다.

## 라이선스

KoreanFA는 Apache-2.0 라이선스로 배포합니다. 엔진 archive에는 Kaldi, MeCab, IPADIC의
해당 라이선스 고지도 함께 포함됩니다.

## 이력

KoreanFA는 2016년에 한국어 강제 정렬기로 시작해, 2023년 Docker/Web API 버전 `v1.7.0`까지
발전했습니다. `0.3.0`은 Python 패키지 인터페이스, 한국어·일본어 자동 모델 선택, 분리된
native 엔진 배포 방식을 도입하는 릴리스입니다.
