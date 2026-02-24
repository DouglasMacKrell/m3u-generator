# m3u-generator

Build `.m3u` playlist files for multi-disc games. Works with ArkOS, Knulli OS, Batocera, and other emulation frontends that support m3u for disc swapping.

Supports PSX, GameCube, Sega CD, CD-i, and other disc-based systems. Handles varied naming conventions (e.g. `(Disc 1)(USA)`, `(Disc 1 of 2)[!][The Game]`).

## Usage

```bash
python3 build_segacd_m3u_arkos_style.py /path/to/roms
```

**Examples:**
```bash
# GameCube
python3 build_segacd_m3u_arkos_style.py "/Volumes/ARKSD/roms/gc"

# PSX
python3 build_segacd_m3u_arkos_style.py "/Volumes/ARKSD/roms/psx"

# Dry run (preview without writing)
python3 build_segacd_m3u_arkos_style.py /path/to/roms --dry-run

# Overwrite existing m3u files
python3 build_segacd_m3u_arkos_style.py /path/to/roms --force
```

## Options

| Flag | Description |
|------|-------------|
| `--dry-run` | Show what would be created without writing files |
| `--force` | Overwrite existing `.m3u` files |
| `--m3u-name-mode` | `smart` (default), `disc-only`, or `aggressive` |
| `--no-keep-region` | Don't preserve region markers (e.g. USA, EU) in m3u names |
| `--no-keep-variants` | Don't preserve translation/rev/proto/hack markers |

## Supported formats

`.chd`, `.cue`, `.iso`, `.bin`, `.img`, `.mdf`, `.ccd`, `.cdi`

## Requirements

Python 3.6+
