# KoreanFA Example Data Notices

The files under this directory are small fixtures used to demonstrate and
validate KoreanFA. They are not covered by the KoreanFA Apache License 2.0.
Each dataset remains subject to the terms stated below.

## Korean examples (`kor_files/fv01_*`)

- Dataset: Seoul Korean Read-Speech Corpus
  (`서울말 낭독체 발화 말뭉치`)
- Provider: National Institute of Korean Language, Republic of Korea
- Official distribution notice:
  <https://www.korean.go.kr/front/board/boardStandardView.do?b_seq=464&board_id=4&mn_id=17&pageIndex=1>
- Current corpus catalogue: <https://kli.korean.go.kr/m/main/requestMain.do>
- Terms: Korea Open Government License Type 1 (Attribution)
- License information: <https://www.kogl.or.kr/info/licenseType1.do>

KoreanFA redistributes only the listed audio/transcript pairs as example and
validation fixtures. Attribution should be preserved when these files are
copied or redistributed. Access to the source corpus requires accepting the
provider's corpus agreement; use and redistribution must also comply with that
agreement. The provider does not endorse KoreanFA.

Suggested attribution:

> Source: National Institute of Korean Language, “Seoul Korean Read-Speech
> Corpus” (`서울말 낭독체 발화 말뭉치`), Korea Open Government License Type 1
> (Attribution).

## Japanese examples (`jap_files/covost2-native-ja-*`)

- Project: CoVoST 2 Native Japanese Dataset
- Provider: Kyoto University NLP group
- Source: <https://github.com/ku-nlp/covost2NativeJa>
- License: Creative Commons Attribution 4.0 International
- License text: <https://creativecommons.org/licenses/by/4.0/>

The following source recordings and transcripts from `validated.tsv` are
included:

- `train0008.mp3` (`spk1`)
- `train0252.mp3` (`spk2`)
- `train0602.mp3` (`spk3`)
- `train1056.mp3` (`spk4`)
- `dev0004.mp3` (`spk6`)

KoreanFA converted each 48 kHz mono MP3 recording to a 16 kHz mono PCM WAV,
renamed it with the `covost2-native-ja-` prefix, and copied its Japanese
sentence from `validated.tsv` to a same-stem UTF-8 text file. The spoken and
written content was not otherwise changed.

Attribution must be preserved when these files are copied or redistributed,
and the conversion described above must be identified as a modification. The
provider does not endorse KoreanFA.

Suggested attribution:

> Source: Kyoto University NLP Group, “CoVoST 2 Native Japanese Dataset,”
> <https://github.com/ku-nlp/covost2NativeJa>, licensed under CC BY 4.0.
> KoreanFA converted the selected 48 kHz mono MP3 recordings to 16 kHz mono
> PCM WAV and renamed the files.
