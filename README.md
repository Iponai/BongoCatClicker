<img src="assets/cat_icon.png" width="72" alt="BongoCatClicker">

# BongoCatClicker

A Windows utility that generates keyboard and mouse input events via the standard `SendInput`
API — the same mechanism a physical keyboard or mouse uses. It doesn't touch any game's files,
process, or memory, and it has no network access.

*[Русская версия / Russian version](README.ru.md)*

## Features

- Sends key-down/key-up events for Numpad digits and/or F13–F24 — keys that exist in Windows'
  input model but not on any physical keyboard, so nothing else on the system reacts to them.
- Optionally clicks the mouse at randomized points inside a screen region you drag out, marked
  by a thin red, click-through border for as long as it's set. The region isn't saved between
  runs.
- Global hotkeys from any window: **F6** start, **F7** or **Esc** stop.
- Auto-pauses on real mouse movement or typing, on by default, so it stays out of your way.
- Keys-only is the fastest mode; mouse and hybrid modes add cursor-positioning overhead.
- Won't click on its own window; a second launch just refocuses the first one.

## Install

Requires Windows 10/11.

### 1. Install Python (skip if you already have it)

Press **Win + S**, type `cmd`, press Enter to open **Command Prompt** — no need to run it as
administrator, Windows shows its own elevation prompt if the install needs it. Check first:

```
python --version
```

A version number means you're already set — skip to step 2. Otherwise:

```
winget install -e --id Python.Python.3.12
```

If that prints `"winget" is not recognized...`, your Windows build doesn't have it (common on
older Windows 10 installs) — download the installer from [python.org](https://python.org)
instead and tick **"Add python.exe to PATH"** during setup. Either way, close and reopen
Command Prompt afterward and re-run `python --version` to confirm.

### 2. Download this project

Go to the repository's main page — https://github.com/Iponai/BongoCatClicker — not this README
file view, which doesn't have it. Click the green **Code** button there → **Download ZIP**, then
extract the archive into a folder of your choice.

### 3. If you're targeting Bongo Cat, enable its admin mode first

Bongo Cat needs to run as administrator, or input won't register while this tool (or any other
elevated window) is active. In Steam: Library → Bongo Cat → **Manage** → **Browse local
files** → right-click `BongoCat.exe` → **Properties** → **Compatibility** tab → check **"Run
this program as an administrator"**.

### 4. Run it

Open the extracted folder and double-click **`start_as_admin.bat`** — needed because Bongo Cat
now runs elevated too (step 3). Use plain `start.bat` instead only if the application you're
sending input to is *not* running as administrator.

Optional: double-click **`make_shortcuts.bat`** in that folder to add shortcuts with the cat
icon, purely for a nicer look — they launch the same `start.bat`/`start_as_admin.bat` underneath.

## Usage

Start with keys-only mode, F13–F24 checked, hold and pause both at 20 ms. Raise both to 30 ms
if presses get missed. Numpad digits type into whatever window is focused, so use F13–F24 for
anything meant to run in the background; mouse mode clicks whatever's under the cursor, so aim
the region at empty desktop or the target window.

## Troubleshooting

Input not registering usually comes down to one of two things:

- **Privilege mismatch.** Windows blocks a non-elevated process from receiving input while an
  elevated window is focused. Run the target application as administrator too.
- **Single-event clicks.** Some counters only register a press when down and up arrive as two
  separate, timed events, not one instantaneous pair — which is how many synthetic-input tools
  fire a "click." This tool always sends them separately.

## Antivirus

Unpacked, unobfuscated Python script with no networking and no compiled `.exe`. Scanned clean
with Microsoft Defender (`MpCmdRun.exe -Scan -ScanType 3`). A generic "PUA:AutoClicker" flag
elsewhere is a catch-all category for input-simulation tools, not a sign of malware.

## Repository layout

```
bongo_clicker.py           main program (EN/RU UI built in)
run.ps1                     launcher (finds Python, quotes the path correctly)
start.bat / start_as_admin.bat
make_shortcuts.bat          optional: adds desktop shortcuts with the cat icon
assets/                     cat icon (already built - shows in the taskbar automatically)
tools/                       regenerates the icon/shortcuts; nothing here needs to be run
```

## License

MIT — see [LICENSE](LICENSE).

---

Honestly vibe-coded with Claude — that's why it's open source.
