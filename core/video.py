"""ffmpeg helpers: locate binaries, probe, pick and extract frames, extract audio."""
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

from core.config import VIDEO_MAX_FRAMES, VIDEO_MIN_FRAMES, VIDEO_SCENE_THRESHOLD, VIDEO_SECONDS_PER_FRAME


class VideoError(RuntimeError):
    pass


def _find(name: str) -> str:
    """Find ffmpeg/ffprobe even if this process started before ffmpeg was added to PATH."""
    found = shutil.which(name)
    if found:
        return found
    dirs = []
    if os.name == "nt":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                dirs += winreg.QueryValueEx(k, "Path")[0].split(";")
        except OSError:
            pass
        dirs += [str(p.parent) for p in
                 (Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft/WinGet/Packages").glob(f"*FFmpeg*/**/{name}.exe")]
    found = shutil.which(name, path=os.pathsep.join(d for d in dirs if d))
    if not found:
        raise VideoError(f"{name} not found. Install with: winget install Gyan.FFmpeg")
    return found


def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")


def probe(path: Path) -> dict:
    """Returns {duration, width, height, has_audio}."""
    r = _run([_find("ffprobe"), "-v", "error", "-show_entries",
              "format=duration:stream=codec_type,width,height", "-of", "json", str(path)])
    if r.returncode != 0:
        raise VideoError(f"Could not read video: {r.stderr.strip()[:300]}")
    info = json.loads(r.stdout)
    streams = info.get("streams", [])
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise VideoError("File has no video stream")
    return {
        "duration": float(info["format"]["duration"]),
        "width": video.get("width"),
        "height": video.get("height"),
        "has_audio": any(s.get("codec_type") == "audio" for s in streams),
    }


def scene_changes(path: Path, threshold: float = VIDEO_SCENE_THRESHOLD) -> list[float]:
    r = _run([_find("ffmpeg"), "-hide_banner", "-i", str(path),
              "-vf", f"select='gt(scene,{threshold})',showinfo", "-an", "-f", "null", "-"])
    return [float(t) for t in re.findall(r"pts_time:([\d.]+)", r.stderr)]


def pick_timestamps(duration: float, scenes: list[float]) -> list[float]:
    """Frame times: the opening shot, a frame just after each scene change, and evenly spaced
    fill-ins, with near-duplicates removed and the total capped."""
    n = max(VIDEO_MIN_FRAMES, min(VIDEO_MAX_FRAMES, round(duration / VIDEO_SECONDS_PER_FRAME)))
    min_gap = duration / (n * 2)
    end = max(0.0, duration - 0.1)

    def add(t, chosen):
        t = min(max(0.0, t), end)
        if all(abs(t - c) >= min_gap for c in chosen):
            chosen.append(t)

    chosen: list[float] = []
    add(min(0.5, duration / 2), chosen)
    for s in scenes:
        add(s + 0.3, chosen)  # just after the cut, past any transition
    if len(chosen) > n:  # too many cuts: keep an even spread of them
        chosen.sort()
        step = len(chosen) / n
        chosen = [chosen[int(i * step)] for i in range(n)]
    # Fill gaps: repeatedly add the grid point farthest from any chosen frame.
    grid = [(i + 0.5) * duration / (4 * n) for i in range(4 * n)]
    while len(chosen) < n:
        best = max(grid, key=lambda g: min(abs(g - c) for c in chosen))
        if min(abs(best - c) for c in chosen) < min_gap:
            break
        chosen.append(best)
    return sorted(chosen)


def extract_frame(path: Path, t: float) -> bytes:
    r = subprocess.run([_find("ffmpeg"), "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(path),
                        "-frames:v", "1", "-f", "image2pipe", "-vcodec", "png", "-"], capture_output=True)
    if r.returncode != 0 or not r.stdout:
        raise VideoError(f"Frame extraction failed at {t:.1f}s: {r.stderr.decode(errors='replace')[:200]}")
    return r.stdout


def extract_audio(path: Path, out_wav: Path) -> None:
    r = _run([_find("ffmpeg"), "-hide_banner", "-loglevel", "error", "-y", "-i", str(path),
              "-vn", "-ac", "1", "-ar", "16000", str(out_wav)])
    if r.returncode != 0:
        raise VideoError(f"Audio extraction failed: {r.stderr.strip()[:300]}")


def fmt_time(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"
