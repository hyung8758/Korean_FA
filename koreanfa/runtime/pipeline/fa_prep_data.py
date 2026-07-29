"""Create Kaldi data files for a directory containing matched WAV/TXT pairs."""

import argparse
import math
import sys
import wave
from pathlib import Path


def _pairs(directory: Path) -> tuple[tuple[Path, Path], ...]:
    audio = {path.stem: path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".wav"}
    text = {path.stem: path for path in directory.iterdir() if path.is_file() and path.suffix.lower() == ".txt"}
    if set(audio) != set(text):
        missing_text = sorted(set(audio) - set(text))
        missing_audio = sorted(set(text) - set(audio))
        details = []
        if missing_text:
            details.append("WAV without TXT: " + ", ".join(missing_text))
        if missing_audio:
            details.append("TXT without WAV: " + ", ".join(missing_audio))
        raise ValueError(" | ".join(details))
    if not audio:
        raise ValueError("No WAV/TXT pairs found")
    return tuple((audio[stem], text[stem]) for stem in sorted(audio))


def prepare_data(directory: Path, destination: Path) -> None:
    pairs = _pairs(directory)
    destination.mkdir(parents=True, exist_ok=True)
    records: list[tuple[str, Path, str, float]] = []
    for wav_path, text_path in pairs:
        transcript = text_path.read_text(encoding="utf-8").strip()
        if not transcript:
            raise ValueError(f"Transcript is empty: {text_path}")
        with wave.open(str(wav_path), "rb") as signal:
            frame_rate = signal.getframerate()
            if frame_rate <= 0:
                raise ValueError(f"Invalid sample rate in {wav_path}")
            duration = signal.getnframes() / frame_rate
        # Kaldi segment end points must not round beyond the WAV duration.
        end = math.nextafter(duration, 0.0) if duration else 0.0
        records.append((wav_path.stem, wav_path, transcript, end))

    speaker = directory.name or "koreanfa"
    (destination / "text").write_text("".join(f"{stem} {text}\n" for stem, _, text, _ in records), encoding="utf-8")
    (destination / "textraw").write_text("".join(f"{text}\n" for _, _, text, _ in records), encoding="utf-8")
    (destination / "segments").write_text(
        "".join(f"{stem} {stem} 0 {end:.6f}\n" for stem, _, _, end in records), encoding="utf-8"
    )
    (destination / "wav.scp").write_text("".join(f"{stem} {wav}\n" for stem, wav, _, _ in records), encoding="utf-8")
    (destination / "utt2spk").write_text("".join(f"{stem} {speaker}\n" for stem, _, _, _ in records), encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("data_directory", type=Path)
    parser.add_argument("save_directory", type=Path)
    args = parser.parse_args(argv)
    try:
        prepare_data(args.data_directory, args.save_directory)
    except (OSError, ValueError, wave.Error) as error:
        print(f"koreanfa: error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
