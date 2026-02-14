AI generated:

# HarmonicDrive

A near-field acoustic scanner controller with a real-time web-based UI, designed for automated loudspeaker measurement on cylindrical and spherical grids.

## Overview

HarmonicDrive drives a **3-axis CNC-style turntable/arm** (controlled via [grblHAL](https://github.com/grblHAL)) to move a microphone to predefined positions around a speaker under test. 
At each position it triggers a sweep measurement through the connected audio interface, stores the impulse responses, and visualizes progress live in the browser.

The system supports:

- **Cylindrical and spherical measurement grids** — including arc-optimized and randomized point distributions
- **GRBL / grblHAL motion control** — with configurable axis parameters (steps/mm, feed rate, acceleration)
- **Sweep-based acoustic measurements** — exponential sweeps with configurable frequency range, duration, and averaging
- **Live web UI** — jog buttons, homing, alarm handling, position readout, and a measurement-point plot — all served by [NiceGUI](https://nicegui.io/)

## Quick Start

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.13 | Exact version pinned in `pyproject.toml` |
| [uv](https://docs.astral.sh/uv/) | Package manager / virtual-env tool |
| **NFS** library | Local editable dependency (expected at `../NFS`) |
| grblHAL controller | Connected via serial (or use `Mock` mode for development) |
| Audio interface | For acoustic measurements (can be mocked) |

### Installation

Clone the repo (and the NFS library next to it)
```bash
git clone <repo-url> HarmonicDrive git clone <nfs-repo-url> NFS
cd HarmonicDrive uv sync
```

### Running

```bash
uv run main.py                  # uses config.ini by default
uv run main.py --config other.ini   # use a different config
```

The UI opens in your browser (default: [http://localhost:8080](http://localhost:8080)).

## Configuration
All settings live in **`config.ini`** (INI format). Key sections:

| Section | Purpose |
| --- | --- |
| `[scanner]` | Motion controller type and feed-rate limit |
| `[grbl_streamer]` | Serial port, baud rate, mock/real mode |
| `[grbl_x/y/z_axis]` | Steps/mm, max rate, acceleration per axis |
| `[audio]` | Audio device selection, sweep count, raw-file saving |
| `[sweep]` | Sweep type, sample rate, frequency range, duration |
| `[motion_manager]` | Coordinate system (cylindrical / spherical), safe radius |
| `[measurement_points]` | Grid type, point count, spacing, or CSV file |
Set `type = Mock` under `[grbl_streamer]` and `mock = True` under `[audio]` for offline development without hardware.
## Project Structure

HarmonicDrive/
├── main.py                 # Entry point — NiceGUI web UI and scanner orchestration
├── config.ini              # Active configuration
├── pyproject.toml          # Project metadata and dependencies
├── scan_path.csv           # Generated scan path
├── Recordings/             # Processed measurement WAV files
├── RawRecordings/          # Raw (unprocessed) measurement WAV files
└── TODO.md                 # Development notes

## UI Features
- **Jog controls** — PHI (rotation), R (radial), Z (vertical) with 1 / 10 / 60 / 120 step sizes
- **Home / Rehome / Clear Alarm / Soft Reset / Hold** — full GRBL state management
- **Zero & height offset** — set the speaker center relative to the turntable stool
- **Start / single measurement** — run a full grid scan or capture one position
- **Live plot** — azimuth vs. elevation scatter plot, auto-refreshing as data arrives
- **Log tail** — real-time scrolling view of `scanner.log`


