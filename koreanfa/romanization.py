"""Readable Korean Revised Romanization labels for alignment output."""

_HANGUL_START = 0xAC00
_HANGUL_END = 0xD7A3
_CODA_COUNT = 28
_SYLLABLES_PER_ONSET = 21 * _CODA_COUNT

# These tables follow the National Institute of Korean Language's Revised
# Romanization convention.  Input is the pronunciation-form Hangul produced
# during KoreanFA lexicon preparation, so sound changes have already been
# resolved before this display-only conversion.
_ONSETS = (
    "g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s",
    "ss", "", "j", "jj", "ch", "k", "t", "p", "h",
)
_VOWELS = (
    "a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa",
    "wae", "oe", "yo", "u", "wo", "we", "wi", "yu", "eu", "ui",
    "i",
)
_CODAS = (
    "", "k", "k", "ks", "n", "nj", "nh", "t", "l", "lg",
    "lm", "lb", "ls", "lt", "lp", "lh", "m", "p", "ps", "t",
    "t", "ng", "t", "t", "k", "t", "p", "h",
)

_JAPANESE_ROMANIZATION = {
    "キャ": "kya", "キュ": "kyu", "キョ": "kyo", "ギャ": "gya", "ギュ": "gyu", "ギョ": "gyo",
    "シャ": "sha", "シュ": "shu", "ショ": "sho", "シェ": "she",
    "ジャ": "ja", "ジュ": "ju", "ジョ": "jo", "ジェ": "je",
    "チャ": "cha", "チュ": "chu", "チョ": "cho", "チェ": "che",
    "ニャ": "nya", "ニュ": "nyu", "ニョ": "nyo", "ヒャ": "hya", "ヒュ": "hyu", "ヒョ": "hyo",
    "ミャ": "mya", "ミュ": "myu", "ミョ": "myo", "リャ": "rya", "リュ": "ryu", "リョ": "ryo",
    "ビャ": "bya", "ビュ": "byu", "ビョ": "byo", "ピャ": "pya", "ピュ": "pyu", "ピョ": "pyo",
    "クヮ": "kwa", "グヮ": "gwa", "ジァ": "ja", "ヂュ": "ju",
    "ディ": "di", "デュ": "dyu", "ティ": "ti", "テュ": "tyu", "トゥ": "tu", "ドゥ": "du",
    "ツァ": "tsa", "ツィ": "tsi", "ツェ": "tse", "ツォ": "tso",
    "ファ": "fa", "フィ": "fi", "フェ": "fe", "フォ": "fo", "フャ": "fya", "フュ": "fyu", "フョ": "fyo",
    "ウァ": "wa", "ウィ": "wi", "ウェ": "we", "ウォ": "wo",
    "ヴァ": "va", "ヴィ": "vi", "ヴェ": "ve", "ヴォ": "vo", "ヴュ": "vyu",
    "イェ": "ye", "キェ": "kye", "ギェ": "gye", "ニェ": "nye", "ヒェ": "hye", "ミェ": "mye",
    "リェ": "rye", "ビェ": "bye", "ピェ": "pye", "スィ": "si", "ズィ": "zi", "ブィ": "bi",
    "カ": "ka", "キ": "ki", "ク": "ku", "ケ": "ke", "コ": "ko",
    "ガ": "ga", "ギ": "gi", "グ": "gu", "ゲ": "ge", "ゴ": "go",
    "サ": "sa", "シ": "shi", "ス": "su", "セ": "se", "ソ": "so",
    "ザ": "za", "ジ": "ji", "ズ": "zu", "ゼ": "ze", "ゾ": "zo",
    "タ": "ta", "チ": "chi", "ツ": "tsu", "テ": "te", "ト": "to",
    "ダ": "da", "ヂ": "ji", "ヅ": "zu", "デ": "de", "ド": "do",
    "ナ": "na", "ニ": "ni", "ヌ": "nu", "ネ": "ne", "ノ": "no",
    "ハ": "ha", "ヒ": "hi", "フ": "fu", "ヘ": "he", "ホ": "ho",
    "バ": "ba", "ビ": "bi", "ブ": "bu", "ベ": "be", "ボ": "bo",
    "パ": "pa", "ピ": "pi", "プ": "pu", "ペ": "pe", "ポ": "po",
    "マ": "ma", "ミ": "mi", "ム": "mu", "メ": "me", "モ": "mo",
    "ヤ": "ya", "ユ": "yu", "ヨ": "yo", "ラ": "ra", "リ": "ri", "ル": "ru", "レ": "re", "ロ": "ro",
    "ワ": "wa", "ヰ": "i", "ヱ": "e", "ヲ": "o", "ヴ": "vu", "ア": "a", "イ": "i", "ウ": "u", "エ": "e", "オ": "o",
    "ァ": "a", "ィ": "i", "ゥ": "u", "ェ": "e", "ォ": "o", "ヮ": "wa", "ヵ": "ka", "ヶ": "ke",
}
_JAPANESE_KEYS = tuple(sorted(_JAPANESE_ROMANIZATION, key=len, reverse=True))


def romanize_korean_pronunciation(text: str) -> str:
    """Return a readable Revised Romanization rendering of pronunciation Hangul.

    The function deliberately preserves whitespace and non-Hangul text.  It
    is a display aid for the TextGrid ``romanization`` tier, not a replacement
    for KoreanFA's model-phone labels or an IPA transcription.
    """
    output: list[str] = []
    previous_coda = ""
    for character in text:
        codepoint = ord(character)
        if not _HANGUL_START <= codepoint <= _HANGUL_END:
            output.append(character)
            previous_coda = ""
            continue
        offset = codepoint - _HANGUL_START
        onset_index, remainder = divmod(offset, _SYLLABLES_PER_ONSET)
        vowel_index, coda_index = divmod(remainder, _CODA_COUNT)
        onset = _ONSETS[onset_index]
        # RR writes ㄹ as "l" after a coda (e.g. 실라 -> silla); it is "r"
        # at the start of a pronunciation word or after a vowel.
        if onset_index == 5 and previous_coda:
            onset = "l"
        coda = _CODAS[coda_index]
        output.extend((onset, _VOWELS[vowel_index], coda))
        previous_coda = coda
    return "".join(output)


def romanize_japanese_reading(text: str, following_reading: str = "") -> str:
    """Render a MeCab Katakana reading in readable ASCII Hepburn-style Latin text.

    Long vowels remain explicit (``トウキョウ`` becomes ``toukyou``), which
    avoids losing information in ASCII-only TextGrid labels.  This is a
    reading aid, not a phonetic alphabet or a replacement for model phones.
    """
    output: list[str] = []
    index = 0
    pending_sokuon = False
    while index < len(text):
        character = text[index]
        if character == "ッ":
            pending_sokuon = True
            index += 1
            continue
        if character == "ー":
            vowel = next((letter for part in reversed(output) for letter in reversed(part) if letter in "aeiou"), "")
            output.append(vowel)
            index += 1
            continue
        if character == "ン":
            following = _next_japanese_romanization(text, index + 1)
            output.append("n'" if following[:1] in "aeiouy" else "n")
            index += 1
            continue
        matched = next((key for key in _JAPANESE_KEYS if text.startswith(key, index)), None)
        if matched is None:
            output.append(character)
            pending_sokuon = False
            index += 1
            continue
        romanized = _JAPANESE_ROMANIZATION[matched]
        if pending_sokuon:
            romanized = _sokuon_prefix(romanized) + romanized
            pending_sokuon = False
        output.append(romanized)
        index += len(matched)
    if pending_sokuon:
        output.append(_sokuon_prefix(_next_japanese_romanization(following_reading, 0)))
    return "".join(output)


def _next_japanese_romanization(text: str, index: int) -> str:
    """Return the next mapped mora for context-sensitive ン rendering."""
    while index < len(text):
        if text[index] in {"ッ", "ー"}:
            index += 1
            continue
        matched = next((key for key in _JAPANESE_KEYS if text.startswith(key, index)), None)
        return _JAPANESE_ROMANIZATION[matched] if matched else text[index]
    return ""


def _sokuon_prefix(romanized: str) -> str:
    """Apply Hepburn-style consonant doubling to a following mora."""
    if romanized.startswith("ch"):
        return "t"
    if romanized.startswith("sh"):
        return "s"
    if romanized.startswith("ts"):
        return "t"
    return romanized[0] if romanized and romanized[0] not in "aeiou" else ""
