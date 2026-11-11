# chief-of-staff

A personal AI chief of staff packaged for Codex on macOS. This folder holds the source, the build script and the released ZIP. It is independent of the rest of this repository.

| Path | What it is |
|---|---|
| `release/chief-of-staff-codex-1.0.1.zip` | The installable package. Start with `START_HERE.md` inside it |
| `release/chief-of-staff-codex-1.0.1.zip.sha256` | Its checksum |
| `release/TEST_REPORT-1.0.1.md` | What passed, failed and was not tested for that exact archive |
| `pkg/` | Package source. Its layout is the layout of the ZIP |
| `build.py` | Builds the ZIP and its manifest from `pkg/` |
| `release_check.py` | Extracts a built ZIP into a clean directory and tests it |

## Install

Download the ZIP, extract it, and follow `START_HERE.md`. In short:

```bash
cd chief-of-staff-codex-1.0.1
bash install.sh
bash verify.sh
```

## Build and test

```bash
python3 build.py
python3 release_check.py release/chief-of-staff-codex-1.0.1.zip --python "$(command -v python3)" --codex "$(command -v codex)"
```

Python 3.9 or newer, standard library only. The tests inside the package can also be run on their own from an extracted ZIP with `bash tests/run_all.sh`.

Changing anything under `pkg/` changes the archive checksum, so rebuild, re-run the release check and update the test report together.
