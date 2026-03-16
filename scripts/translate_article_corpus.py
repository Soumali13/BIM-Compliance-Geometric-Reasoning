from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

import torch
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer


DEFAULT_MODEL = "Helsinki-NLP/opus-mt-fr-en"


def _split_sentences(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []
    parts = re.split(r"(?<=[\.\!\?\:\;])\s+", text)
    return [part.strip() for part in parts if part.strip()]


def _chunk_text(text: str, *, max_chars: int = 700) -> list[str]:
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    for paragraph in [part.strip() for part in text.split("\n") if part.strip()]:
        paragraph_sentences = _split_sentences(paragraph) or [paragraph]
        for sentence in paragraph_sentences:
            sentence_len = len(sentence)
            if sentence_len > max_chars:
                if current:
                    chunks.append(" ".join(current).strip())
                    current = []
                    current_len = 0
                chunks.append(sentence)
                continue

            projected = current_len + sentence_len + (1 if current else 0)
            if projected > max_chars and current:
                chunks.append(" ".join(current).strip())
                current = [sentence]
                current_len = sentence_len
            else:
                current.append(sentence)
                current_len = projected

    if current:
        chunks.append(" ".join(current).strip())

    return chunks or [text]


class CorpusTranslator:
    def __init__(self, model_name: str) -> None:
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForSeq2SeqLM.from_pretrained(model_name)
        self.model.eval()
        self.cache: dict[str, str] = {}

    def translate(self, text: str) -> str:
        normalized = text.strip()
        if not normalized:
            return text
        if normalized in self.cache:
            return self.cache[normalized]

        pieces = _chunk_text(normalized)
        translated_pieces: list[str] = []
        for start in range(0, len(pieces), 8):
            batch = pieces[start : start + 8]
            tokenized = self.tokenizer(batch, return_tensors="pt", padding=True, truncation=True)
            with torch.inference_mode():
                generated = self.model.generate(**tokenized, max_new_tokens=256, num_beams=1)
            translated_pieces.extend(self.tokenizer.batch_decode(generated, skip_special_tokens=True))

        translated = "\n".join(piece.strip() for piece in translated_pieces if piece.strip()).strip()
        self.cache[normalized] = translated
        return translated


def _translate_article(article: dict, translator: CorpusTranslator) -> dict:
    translated = dict(article)
    for field in ("title", "section", "section_title", "text"):
        value = translated.get(field)
        if isinstance(value, str) and value.strip():
            translated[field] = translator.translate(value)
    return translated


def translate_corpus(input_path: Path, output_path: Path, *, model_name: str, backup_path: Path | None) -> None:
    payload = json.loads(input_path.read_text(encoding="utf-8"))
    translator = CorpusTranslator(model_name)

    if backup_path is not None and not backup_path.exists():
        shutil.copy2(input_path, backup_path)

    translated_articles = [_translate_article(article, translator) for article in payload.get("articles", [])]
    payload["articles"] = translated_articles
    payload["source_language"] = "fr"
    payload["target_language"] = "en"
    payload["translation_model"] = model_name
    payload["translated_from"] = str(input_path if backup_path is None else backup_path)
    payload["generated_by"] = "scripts/translate_article_corpus.py"

    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Translate an extracted article corpus to English.")
    parser.add_argument("input_path", type=Path)
    parser.add_argument("output_path", type=Path)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--backup-path", type=Path, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    translate_corpus(args.input_path, args.output_path, model_name=args.model, backup_path=args.backup_path)
    print(f"Translated corpus written to {args.output_path}")


if __name__ == "__main__":
    main()
