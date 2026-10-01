"""Run the Phase 1 pipeline on one image from the command line (no UI).

    python scripts/try_image.py path/to/image.jpg [K]
    python scripts/try_image.py --make-sample     # writes tests/assets/sample_sailboat.png
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def make_sample() -> Path:
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1200, 800), (135, 196, 235))
    d = ImageDraw.Draw(img)
    d.rectangle([0, 480, 1200, 800], fill=(20, 90, 150))
    d.ellipse([950, 80, 1070, 200], fill=(255, 220, 90))
    d.polygon([(560, 470), (840, 470), (800, 520), (600, 520)], fill=(245, 245, 240))
    d.line([(700, 470), (700, 170)], fill=(60, 60, 60), width=6)
    d.polygon([(706, 180), (706, 460), (840, 460)], fill=(230, 60, 50))
    d.polygon([(694, 200), (694, 460), (590, 460)], fill=(250, 250, 250))
    path = ROOT / "tests" / "assets" / "sample_sailboat.png"
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path)
    return path


if __name__ == "__main__":
    if sys.argv[1:] == ["--make-sample"]:
        print(make_sample())
        sys.exit()

    from core.analyze import analyze_image
    from core.scoring import filter_tags

    path = Path(sys.argv[1])
    k = int(sys.argv[2]) if len(sys.argv) > 2 else 3
    r = analyze_image(path.read_bytes(), path.name, k, on_progress=print)
    print("\nCaption:", r["caption"])
    print(f"\n{'tag':<24}{'certainty':>10}{'agree':>8}{'conf':>7}")
    for s in filter_tags(r["scores"], "top_n", 25):
        print(f"{s.tag:<24}{s.certainty:>10.0%}{s.agreement:>8.0%}{s.mean_self_confidence:>7.0%}")
    print("\nMerged:", r["merge_map"] or "none")
    u = r["usage"]
    print(f"\nTokens: {u['input_tokens']:,} in / {u['output_tokens']:,} out  Cost: ${r['cost_usd']:.4f}")
