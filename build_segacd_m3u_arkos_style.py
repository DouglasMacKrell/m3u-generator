#!/usr/bin/env python3
import argparse
import re
from pathlib import Path
from collections import defaultdict, Counter
from typing import Optional, List, Dict, Tuple

VALID_EXTS = {".chd", ".cue", ".iso", ".bin", ".img", ".mdf", ".ccd", ".cdi"}

DISC_RE = re.compile(
    r"(?:\(|\s|^)(?:disc|disk|cd)\s*[-_ ]?(?P<num>\d+)(?:\)|\s|$)",
    re.IGNORECASE,
)

# Match trailing (... ) or [... ] groups (CD-i uses [The Game], [The Documentation], etc.)
TRAILING_GROUP_RE = re.compile(r"\s*[(\[][^)\]]*[)\]]\s*$")

# Identify disc markers inside paren/bracket groups so we can remove ONLY those groups
DISC_GROUP_RE = re.compile(
    r"\s*[(\[][^)\]]*(?:disc|disk|cd)\s*[-_ ]?\d+[^)\]]*[)\]]\s*$",
    re.IGNORECASE,
)

# Tokens worth preserving in the visible m3u filename
# Examples: [T-En], (Translated En), (Rev 1), (Proto), (Beta), (Hack), (Uncensored)
PRESERVE_TOKEN_RE = re.compile(
    r"(?i)\b("
    r"t[-_ ]?en|translated|translation|fan\s*trans|"
    r"rev(?:ision)?\s*\d+|v\s*\d+(?:\.\d+)*|"
    r"proto(?:type)?|beta|demo|sample|preview|"
    r"hack|mod|undub|uncensored|restoration|"
    r"patch(?:ed)?"
    r")\b"
)

# Region / language markers people commonly encode
REGION_TOKEN_RE = re.compile(
    r"(?i)\b("
    r"usa|u\.?s\.?a\.?|us|"
    r"eur(?:ope)?|pal|ntsc[-_ ]?u|ntsc[-_ ]?j|"
    r"jpn|japan|jp|"
    r"eng(?:lish)?|en|"
    r"spa(?:nish)?|es|fra(?:nce)?|fr|deu|ger|de|ita|it|por|pt|rus|ru|"
    r"asia|world"
    r")\b"
)


def disc_number(stem: str) -> Optional[int]:
    m = DISC_RE.search(stem)
    if not m:
        return None
    try:
        return int(m.group("num"))
    except ValueError:
        return None


def strip_all_trailing_paren_groups(stem: str) -> str:
    """Aggressive: repeatedly remove trailing '(...)' or '[...]' groups."""
    s = stem.strip()
    while True:
        new = TRAILING_GROUP_RE.sub("", s).strip()
        if new == s:
            break
        s = new
    return s or stem


def strip_only_disc_groups(stem: str) -> str:
    """
    Safer for Knulli: remove ONLY trailing groups that look like disc markers.

    Examples:
      'BrainDead 13 (USA) (Disc 1)' -> 'BrainDead 13 (USA)'
      'Snatcher (Japan) (Translated En) (CD 2)' -> 'Snatcher (Japan) (Translated En)'
      'Game [The Game] [Disc 1]' -> 'Game [The Game]'
    """
    s = stem.strip()
    while True:
        new = DISC_GROUP_RE.sub("", s).strip()
        if new == s:
            break
        s = new
    return s or stem


def trailing_groups(stem: str) -> List[str]:
    """Return trailing groups (rightmost first) without altering the stem."""
    s = stem
    groups: List[str] = []
    while True:
        m = TRAILING_GROUP_RE.search(s)
        if not m:
            break
        grp = m.group(0).strip()
        if grp:
            groups.append(grp)
        s = s[: m.start()].rstrip()
    return groups


def choose_m3u_stem(
    sample_disc_stem: str,
    *,
    mode: str,
    keep_region: bool,
    keep_variants: bool,
) -> str:
    """
    Decide what the .m3u *visible* filename should be.

    mode:
      - 'aggressive' : old ArkOS-style (strip all trailing groups)
      - 'disc-only'  : strip only disc markers; keep everything else
      - 'smart'      : strip disc markers; optionally re-add region/variant markers only when present
    """
    if mode == "aggressive":
        return strip_all_trailing_paren_groups(sample_disc_stem)

    if mode == "disc-only":
        return strip_only_disc_groups(sample_disc_stem)

    # mode == 'smart'
    # Use a clean base (strip everything) so disc markers are always removed,
    # then re-add only region/variant markers. Fixes "Killer 7 (Disc 1)(USA)" -> "Killer 7 (USA)".
    base = strip_all_trailing_paren_groups(sample_disc_stem)
    if keep_region or keep_variants:
        original_groups = trailing_groups(sample_disc_stem)
        keepers: List[str] = []

        for g in reversed(original_groups):  # restore original order
            # Always ignore disc groups
            if DISC_GROUP_RE.fullmatch(g) or DISC_GROUP_RE.search(g):
                continue
            text = g.strip("()[] ")
            if keep_variants and PRESERVE_TOKEN_RE.search(text):
                keepers.append(g)
                continue
            if keep_region and REGION_TOKEN_RE.search(text):
                keepers.append(g)
                continue

        # Only append keepers that are not already present in base
        out = base
        for k in keepers:
            if k.lower() not in out.lower():
                out = f"{out} {k}".strip()
        return out

    return base


def is_game_image(p: Path) -> bool:
    return p.is_file() and p.suffix.lower() in VALID_EXTS


def sort_discs(files: List[Path]) -> List[Path]:
    def key(p: Path) -> Tuple[int, str]:
        dn = disc_number(p.stem)
        return (dn if dn is not None else 999, p.name.lower())

    return sorted(files, key=key)


def main():
    ap = argparse.ArgumentParser(
        description="Build .m3u files for multi-disc games (Knulli-safe naming)."
    )
    ap.add_argument(
        "rom_dir",
        nargs="?",
        default=".",
        help="Directory containing ROM files (default: current dir)",
    )
    ap.add_argument("--force", action="store_true", help="Overwrite existing .m3u files")
    ap.add_argument(
        "--dry-run", action="store_true", help="Print what would be created without writing"
    )

    # NEW: naming controls
    ap.add_argument(
        "--m3u-name-mode",
        choices=["disc-only", "smart", "aggressive"],
        default="smart",
        help=(
            "How to name the .m3u file: "
            "disc-only (remove only disc markers), "
            "smart (remove disc markers + preserve region/translation/variants when present), "
            "aggressive (strip all trailing groups; NOT recommended for variant libraries)."
        ),
    )
    ap.add_argument(
        "--keep-region",
        action="store_true",
        default=True,
        help="(smart mode) Preserve region/language markers when present (default: on)",
    )
    ap.add_argument(
        "--no-keep-region",
        action="store_false",
        dest="keep_region",
        help="(smart mode) Do not preserve region/language markers",
    )
    ap.add_argument(
        "--keep-variants",
        action="store_true",
        default=True,
        help="(smart mode) Preserve translation/rev/proto/hack markers when present (default: on)",
    )
    ap.add_argument(
        "--no-keep-variants",
        action="store_false",
        dest="keep_variants",
        help="(smart mode) Do not preserve translation/rev/proto/hack markers",
    )

    args = ap.parse_args()

    target_dir = Path(args.rom_dir).expanduser().resolve()
    if not target_dir.exists():
        raise SystemExit(f"ERROR: directory not found: {target_dir}")

    images = [p for p in target_dir.iterdir() if is_game_image(p)]
    if not images:
        print(f"No disc images found in {target_dir}. Nothing to do.")
        return

    # Split into disc-tagged vs not (by filename)
    disc_tagged = [p for p in images if disc_number(p.stem) is not None]
    non_disc = [p for p in images if p not in disc_tagged]

    # Group disc-tagged files by a stable key that ignores disc markers.
    # Must strip ALL trailing groups (not just disc groups) because formats vary:
    # - GameCube: "Killer 7 (Disc 1)(USA)" — (USA) blocks disc group from end
    # - CD-i: "Marco Polo (...)(Disc 1 of 2)[!][The Game]" — [...] blocks disc group
    disc_group_key = {p: strip_all_trailing_paren_groups(p.stem) for p in disc_tagged}

    disc_groups: Dict[str, List[Path]] = defaultdict(list)
    for p in disc_tagged:
        disc_groups[disc_group_key[p]].append(p)

    # For collision detection on single-disc images, compute a conservative base
    # (do NOT strip region/variant markers here; keep stable uniqueness).
    single_base = {p: strip_only_disc_groups(p.stem) for p in non_disc}
    single_counts = Counter(single_base[p] for p in non_disc)

    plan: Dict[str, List[Path]] = {}

    # Multi-disc sets (one m3u per set)
    for key, files in disc_groups.items():
        files_sorted = sort_discs(files)
        # Choose name based on first disc filename (keeps consistent markers)
        sample = files_sorted[0].stem
        m3u_stem = choose_m3u_stem(
            sample,
            mode=args.m3u_name_mode,
            keep_region=args.keep_region,
            keep_variants=args.keep_variants,
        )
        # If that name collides with an existing plan key, fall back to the grouping key
        # (which already retains region/variant markers).
        if m3u_stem in plan:
            m3u_stem = key
        plan[m3u_stem] = files_sorted

    # Singles (one m3u per file), collision-safe naming
    for p in non_disc:
        base = single_base[p]

        if single_counts[base] == 1 and base not in plan:
            # Keep single-disc m3u name aligned with your chosen naming mode
            m3u_stem = choose_m3u_stem(
                p.stem,
                mode=args.m3u_name_mode,
                keep_region=args.keep_region,
                keep_variants=args.keep_variants,
            )
        else:
            # Collision-safe fallback
            m3u_stem = p.stem

        if m3u_stem in plan:
            # Final safety net
            m3u_stem = p.stem

        plan[m3u_stem] = [p]

    wrote = 0
    skipped = 0

    for m3u_stem in sorted(plan.keys(), key=str.lower):
        m3u_path = target_dir / f"{m3u_stem}.m3u"

        if m3u_path.exists() and not args.force:
            skipped += 1
            continue

        lines = [p.name for p in plan[m3u_stem]]
        content = "\n".join(lines) + "\n"  # LF newline, filename-only

        if args.dry_run:
            print(f"[DRY-RUN] {m3u_path.name}")
            for ln in lines:
                print(f"  {ln}")
            print()
        else:
            m3u_path.write_text(content, encoding="utf-8")
            wrote += 1
            print(f"Wrote: {m3u_path.name} ({len(lines)} entries)")

    print()
    print(
        f"Done. Wrote {wrote} m3u files. Skipped {skipped} existing (use --force to overwrite)."
    )


if __name__ == "__main__":
    main()
