#!/usr/bin/env python3
"""Build a curated Lithuanian lemma word list from CLARIN-LT corpus resources."""

from __future__ import annotations

import argparse
import re
import shutil
import zipfile
from pathlib import Path

from clarin_repo import (
    CCLL_FREQ_HANDLE,
    CCLL_FREQ_ZIP,
    CCLL_LEMMA_MEMBER,
    DEFAULT_CLARIN_DIR,
    JCL_HANDLE,
    JCL_LEMMA_MEMBER,
    JCL_ZIP,
    UTKA_1M_HANDLE,
    UTKA_1M_ZIP,
    UTKA_DAZNINIS_MEMBER,
    download_clarin_zip,
)
from fasttext_utils import (
    ensure_embedding_model,
    list_embedding_models,
    load_model,
    top_vocabulary,
)
from hunspell_lemmatizer import HunspellLemmatizer
from lemmatizer import LemmatizerMode, get_lemmatizer

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "assets" / "words" / "lt_nouns_100k.txt"

# Utka 1M corpus (VDU): dkt = daiktavardis (noun)
UTKA_NOUN_POS = ("dkt", "tikr. dkt", "tikr. dkt2")
# JCL joint corpus: N = noun, Nf/Ng/Np/Ns = proper-noun subclasses
JCL_NOUN_POS = ("N", "Nf", "Ng", "Np", "Ns")
JCL_COMMON_NOUN_POS = ("N",)
LT_WORD_RE = re.compile(r"^[a-ząčęėįšųūž\-]+$", re.IGNORECASE)
DEFAULT_MAX_LEN = 30
_MAX_LEN = DEFAULT_MAX_LEN

# Deverbal noun suffixes (veiksmažodinis daiktavardis), e.g. sportavimas, mokėjimas.
VERBAL_NOUN_SUFFIXES = ("avimas", "ėjimas", "inimas", "stymas", "tavimas", "ymas")
VERBAL_NOUN_SUFFIX_RE = re.compile(
    r"(?:avimas|ėjimas|inimas|stymas|tavimas|ymas)$",
    re.IGNORECASE,
)


def is_valid_lemma(word: str, min_len: int = 2, max_len: int | None = None) -> bool:
    max_len = max_len if max_len is not None else _MAX_LEN
    w = word.strip().lower()
    if len(w) < min_len or len(w) > max_len:
        return False
    if not LT_WORD_RE.match(w):
        return False
    if w.isdigit():
        return False
    return True


def load_lemmas_from_freq_file(path: Path) -> list[tuple[str, int]]:
    """Tab-separated lemma + frequency (CCLL 4-LT_lemma_alpha_freq_list.txt)."""
    entries: list[tuple[str, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 2:
                parts = line.split()
            if len(parts) < 2:
                continue
            lemma = parts[0].strip().lower()
            try:
                freq = int(parts[1].replace(",", ""))
            except ValueError:
                continue
            if is_valid_lemma(lemma):
                entries.append((lemma, freq))
    entries.sort(key=lambda x: -x[1])
    return entries


def load_jcl_lemma_tags(path: Path) -> dict[str, set[str]]:
    """JCL_lemmas.txt: lemma, POS tag, corpus frequency."""
    tags: dict[str, set[str]] = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("lemma"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            lemma, pos = parts[0].strip().lower(), parts[1].strip()
            if not is_valid_lemma(lemma):
                continue
            tags.setdefault(lemma, set()).add(pos)
    return tags


def load_lemmas_from_jcl_file(
    path: Path,
    allowed_pos: frozenset[str] | None = None,
) -> list[tuple[str, int]]:
    entries: list[tuple[str, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("lemma"):
                continue
            parts = line.split("\t")
            if len(parts) < 3:
                continue
            lemma, pos = parts[0].strip().lower(), parts[1].strip()
            try:
                freq = int(parts[2].replace(",", ""))
            except ValueError:
                continue
            if allowed_pos and pos not in allowed_pos:
                continue
            if not is_valid_lemma(lemma):
                continue
            entries.append((lemma, freq))
    entries.sort(key=lambda x: -x[1])
    return entries


def is_verbal_noun(
    lemma: str,
    verb_lemmas: frozenset[str] | None = None,
) -> bool:
    """Detect deverbal nouns (sportavimas, mokėjimas) by suffix and optional verb stem."""
    w = lemma.strip().lower()
    if not VERBAL_NOUN_SUFFIX_RE.search(w):
        return False

    matched_suffix = next(s for s in VERBAL_NOUN_SUFFIXES if w.endswith(s))
    if len(w) <= len(matched_suffix) + 1:
        return False

    if verb_lemmas is None:
        return True

    root = w[:-len(matched_suffix)]
    if len(root) < 3:
        return True

    prefix = root[:5]
    for verb in verb_lemmas:
        if verb.startswith(prefix) or prefix in verb:
            return True
    return True


def filter_verbal_nouns(
    lemmas: list[str],
    verb_lemmas: frozenset[str] | None = None,
) -> list[str]:
    kept: list[str] = []
    dropped = 0
    for lemma in lemmas:
        if is_verbal_noun(lemma, verb_lemmas):
            dropped += 1
            continue
        kept.append(lemma)
    print(f"Verbal noun filter: kept {len(kept)}, dropped {dropped}")
    return kept


def load_lemmas_from_utka_file(
    path: Path,
    allowed_pos: frozenset[str] | None = None,
) -> list[tuple[str, int]]:
    """Utka dazninis.txt: headword, POS, wordform, frequency."""
    entries: list[tuple[str, int]] = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) < 4:
                continue
            headword, pos = parts[0].strip().lower(), parts[1].strip().lower()
            try:
                freq = int(parts[3].replace(",", ""))
            except ValueError:
                continue
            if not is_valid_lemma(headword):
                continue
            if allowed_pos and pos not in allowed_pos:
                continue
            entries.append((headword, freq))
    merged: dict[str, int] = {}
    for lemma, freq in entries:
        merged[lemma] = max(merged.get(lemma, 0), freq)
    return sorted(merged.items(), key=lambda x: -x[1])


def extract_zip_member(zip_path: Path, member: str | None, member_suffix: str | None) -> Path:
    tmp = zip_path.parent / f"_extract_{zip_path.stem}"
    tmp.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path) as zf:
        if member:
            name = member if member in zf.namelist() else None
        else:
            name = next(
                (n for n in zf.namelist() if member_suffix and n.endswith(member_suffix)),
                None,
            )
        if not name:
            raise ValueError(f"Member not found in {zip_path}: {member or member_suffix}")
        out = tmp / Path(name).name
        with zf.open(name) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst)
        return out


def merge_freq_lists(lists: list[list[tuple[str, int]]]) -> list[str]:
    merged: dict[str, int] = {}
    for entries in lists:
        for lemma, freq in entries:
            merged[lemma] = max(merged.get(lemma, 0), freq)
    return [lemma for lemma, _ in sorted(merged.items(), key=lambda x: (-x[1], x[0]))]


def load_from_clarin(
    clarin_dir: Path,
    ccll_zip: Path | None,
    utka_zip: Path | None,
    jcl_zip: Path | None,
    lemma_file: Path | None,
    download: bool,
    use_ccll: bool,
    use_utka: bool,
    use_jcl: bool,
    jcl_pos: frozenset[str] | None,
    utka_pos: frozenset[str] | None,
) -> list[tuple[str, int]]:
    freq_lists: list[list[tuple[str, int]]] = []

    if lemma_file and lemma_file.exists():
        freq_lists.append(load_lemmas_from_freq_file(lemma_file))
        print(f"Lemma file: {len(freq_lists[-1])} entries from {lemma_file}")

    if use_jcl:
        jcl_path = jcl_zip or (clarin_dir / JCL_ZIP)
        if download or not jcl_path.exists():
            jcl_path = download_clarin_zip(JCL_HANDLE, JCL_ZIP, clarin_dir)
        if jcl_path.exists():
            extracted = extract_zip_member(jcl_path, JCL_LEMMA_MEMBER, None)
            freq_lists.append(load_lemmas_from_jcl_file(extracted, jcl_pos))
            pos_label = ",".join(sorted(jcl_pos)) if jcl_pos else "all"
            print(
                f"JCL: {len(freq_lists[-1])} lemmas (POS {pos_label}) "
                f"from {JCL_LEMMA_MEMBER}"
            )
            shutil.rmtree(extracted.parent, ignore_errors=True)

    if use_ccll:
        if jcl_pos:
            print("Skipping CCLL (no POS tags; use JCL or Utka for noun filtering).")
        else:
            ccll_path = ccll_zip or (clarin_dir / CCLL_FREQ_ZIP)
            if download or not ccll_path.exists():
                ccll_path = download_clarin_zip(CCLL_FREQ_HANDLE, CCLL_FREQ_ZIP, clarin_dir)
            if ccll_path.exists():
                extracted = extract_zip_member(ccll_path, CCLL_LEMMA_MEMBER, None)
                freq_lists.append(load_lemmas_from_freq_file(extracted))
                print(f"CCLL: {len(freq_lists[-1])} lemmas from {CCLL_LEMMA_MEMBER}")
                shutil.rmtree(extracted.parent, ignore_errors=True)

    if use_utka:
        utka_path = utka_zip or (clarin_dir / UTKA_1M_ZIP)
        if download or not utka_path.exists():
            utka_path = download_clarin_zip(UTKA_1M_HANDLE, UTKA_1M_ZIP, clarin_dir)
        if utka_path.exists():
            extracted = extract_zip_member(utka_path, UTKA_DAZNINIS_MEMBER, None)
            freq_lists.append(load_lemmas_from_utka_file(extracted, utka_pos))
            pos_label = ",".join(sorted(utka_pos)) if utka_pos else "all"
            print(
                f"Utka 1M (VDU): {len(freq_lists[-1])} headwords (POS {pos_label}) "
                f"from {UTKA_DAZNINIS_MEMBER}"
            )
            shutil.rmtree(extracted.parent, ignore_errors=True)

    if not freq_lists:
        raise FileNotFoundError(
            "No CLARIN wordlist data found. Run with --download-clarin or place zips in assets/clarin/."
        )

    merged = merge_freq_lists(freq_lists)
    return [(lemma, 0) for lemma in merged]


def filter_hunspell(lemmas: list[str]) -> list[str]:
    lemmatizer = HunspellLemmatizer()
    kept: list[str] = []
    dropped = 0
    for lemma in lemmas:
        if lemmatizer._dict.lookup(lemma):
            kept.append(lemma)
        else:
            dropped += 1
    print(f"Hunspell filter: kept {len(kept)}, dropped {dropped}")
    return kept


def fill_from_fasttext(
    model,
    seen: set[str],
    top_k: int,
    lemmatizer_mode: LemmatizerMode = "hunspell",
) -> list[str]:
    lemmatizer = get_lemmatizer(lemmatizer_mode)
    hunspell = HunspellLemmatizer()
    added: list[str] = []
    for token in top_vocabulary(model, top_k * 4):
        if len(added) + len(seen) >= top_k:
            break
        w = token.lower()
        if not is_valid_lemma(w):
            continue
        lemma = lemmatizer.lemmatize(w) if lemmatizer else w
        if not lemma or lemma in seen or not is_valid_lemma(lemma):
            continue
        if not hunspell._dict.lookup(lemma):
            continue
        seen.add(lemma)
        added.append(lemma)
    if lemmatizer:
        lemmatizer.close()
    return added


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare Lithuanian lemma list from CLARIN-LT corpora",
        epilog=(
            "Primary sources: CCLL Lemmatised Frequency Lists and Utka 1M corpus "
            "(https://clarin-repo.lt/search?query=wordlist)."
        ),
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top-k", type=int, default=100000)
    parser.add_argument("--clarin-dir", type=Path, default=DEFAULT_CLARIN_DIR)
    parser.add_argument("--ccll-zip", type=Path, help="Local LT_freq_lists.zip")
    parser.add_argument("--utka-zip", type=Path, help="Local Lithuanian-wordlist.zip")
    parser.add_argument("--jcl-zip", type=Path, help="Local JCL_Wordlist.zip")
    parser.add_argument("--lemma-file", type=Path, help="Pre-extracted lemma freq .txt")
    parser.add_argument(
        "--download-clarin",
        action="store_true",
        help="Download missing CLARIN-LT archives",
    )
    parser.add_argument(
        "--source",
        choices=["clarin", "jcl", "all", "fasttext", "both"],
        default="clarin",
        help=(
            "clarin = CCLL+Utka; jcl = Joint Corpus (POS-tagged); all = merge JCL+CCLL+Utka; "
            "fasttext / both = fastText vocabulary fill"
        ),
    )
    parser.add_argument(
        "--pos",
        help="POS filter: JCL tags (N,Ng,...) or Utka tags (dkt). Comma-separated.",
    )
    parser.add_argument(
        "--nouns-only",
        action="store_true",
        help="Common nouns only (JCL: N; skips proper names Ng/Nf/Np/Ns)",
    )
    parser.add_argument(
        "--nouns-all",
        action="store_true",
        help="All noun types including proper names (JCL: N,Nf,Ng,Np,Ns; Utka: dkt)",
    )
    parser.add_argument(
        "--fill-fasttext",
        action="store_true",
        help="After CLARIN merge, pad with Hunspell-validated fastText lemmas",
    )
    parser.add_argument(
        "--embedding-model",
        choices=list_embedding_models(),
        default="cc",
    )
    parser.add_argument("--model", type=Path, help="Explicit .bin path")
    parser.add_argument("--download-model", action="store_true")
    parser.add_argument(
        "--hunspell-filter",
        action="store_true",
        help="Drop lemmas not found in Semantika Hunspell dictionary",
    )
    parser.add_argument(
        "--exclude-verbal-nouns",
        action="store_true",
        help="Drop deverbal nouns (sportavimas, mokėjimas, …) by suffix heuristics",
    )
    parser.add_argument(
        "--include-verbal-nouns",
        action="store_true",
        help="Keep deverbal nouns even when --nouns-only is set",
    )
    parser.add_argument("--max-len", type=int, default=DEFAULT_MAX_LEN)
    args = parser.parse_args()

    global _MAX_LEN
    _MAX_LEN = args.max_len

    jcl_pos: frozenset[str] | None = None
    utka_pos: frozenset[str] | None = None
    if args.nouns_only and args.nouns_all:
        parser.error("Use only one of --nouns-only or --nouns-all")
    if args.include_verbal_nouns and args.exclude_verbal_nouns:
        parser.error("Use only one of --include-verbal-nouns or --exclude-verbal-nouns")
    exclude_verbal_nouns = args.exclude_verbal_nouns or (
        args.nouns_only and not args.include_verbal_nouns
    )
    if args.nouns_only:
        jcl_pos = frozenset(JCL_COMMON_NOUN_POS)
        utka_pos = frozenset(("dkt",))
    elif args.nouns_all:
        jcl_pos = frozenset(JCL_NOUN_POS)
        utka_pos = frozenset(UTKA_NOUN_POS)
    elif args.pos:
        tags = frozenset(p.strip() for p in args.pos.split(",") if p.strip())
        jcl_pos = tags
        utka_pos = tags

    use_jcl = args.source in ("jcl", "all")
    use_ccll = args.source in ("clarin", "all", "both")
    use_utka = args.source in ("clarin", "all", "both")
    if args.source == "jcl":
        use_ccll = False
        use_utka = False

    lemmas: list[str] = []
    verb_lemmas: frozenset[str] | None = None

    if exclude_verbal_nouns and use_jcl:
        jcl_path = args.jcl_zip or (args.clarin_dir / JCL_ZIP)
        if jcl_path.exists():
            extracted = extract_zip_member(jcl_path, JCL_LEMMA_MEMBER, None)
            jcl_tags = load_jcl_lemma_tags(extracted)
            verb_lemmas = frozenset(
                lemma for lemma, tags in jcl_tags.items() if "V" in tags
            )
            print(f"JCL verbs for deverbal filter: {len(verb_lemmas)} lemmas")
            shutil.rmtree(extracted.parent, ignore_errors=True)

    if args.source in ("clarin", "jcl", "all", "both"):
        entries = load_from_clarin(
            args.clarin_dir,
            args.ccll_zip,
            args.utka_zip,
            args.jcl_zip,
            args.lemma_file,
            args.download_clarin,
            use_ccll,
            use_utka,
            use_jcl,
            jcl_pos,
            utka_pos,
        )
        lemmas = [lemma for lemma, _ in entries]
        print(f"CLARIN merged: {len(lemmas)} unique lemmas")

    need_fasttext = (
        args.source == "fasttext"
        or args.fill_fasttext
        or (args.source == "both" and len(lemmas) < args.top_k)
    )

    if need_fasttext:
        model_path, _, embedding_label = ensure_embedding_model(
            embedding_model=args.embedding_model,
            model_path=args.model,
            download=args.download_model,
        )
        print(f"Loading {embedding_label} from {model_path}...")
        model = load_model(model_path)
        seen = set(lemmas)
        fill = fill_from_fasttext(model, seen, args.top_k)
        lemmas.extend(fill)
        print(f"fastText fill: {len(fill)} lemmas")

    if args.hunspell_filter:
        lemmas = filter_hunspell(lemmas)

    if exclude_verbal_nouns:
        lemmas = filter_verbal_nouns(lemmas, verb_lemmas)

    final = lemmas[:args.top_k]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        for w in final:
            f.write(w + "\n")

    print(f"Wrote {len(final)} lemmas to {args.output}")
    if final:
        print(f"Sample: {final[:5]} ... {final[-3:]}")


if __name__ == "__main__":
    main()
