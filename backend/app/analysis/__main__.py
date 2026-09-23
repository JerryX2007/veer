"""Command line: python -m app.analysis match.mp4 [--set net_x=0.45] [--json out.json]

Handy for tuning thresholds on real footage without the web app.
"""

import argparse
import json
import sys

from .config import AnalysisConfig
from .pipeline import analyze_video
from .reel import format_time, reel_to_text


def _parse_overrides(pairs: list[str]) -> dict:
    overrides = {}
    for pair in pairs:
        key, sep, value = pair.partition("=")
        if not sep:
            raise SystemExit(f"--set expects key=value, got {pair!r}")
        overrides[key.strip()] = None if value.strip().lower() == "none" else value.strip()
    return overrides


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Find rallies and highlights in a volleyball video.")
    parser.add_argument("video")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override an AnalysisConfig setting, e.g. --set net_x=0.45")
    parser.add_argument("--json", metavar="PATH", help="also write the full result as JSON")
    args = parser.parse_args(argv)

    try:
        config = AnalysisConfig.from_overrides(_parse_overrides(args.set))
    except ValueError as e:
        parser.error(str(e))

    def progress(fraction: float) -> None:
        print(f"\ranalysing... {fraction:4.0%}", end="", file=sys.stderr, flush=True)

    result = analyze_video(args.video, config, progress)
    print(file=sys.stderr)

    print(f"{len(result.rallies)} rallies:")
    for r in result.rallies:
        serve = f"serve {format_time(r.serve_time)}" if r.serve_time is not None else "serve not seen"
        print(f"  #{r.index}  {format_time(r.start)} - {format_time(r.end)}  ({serve}, {len(r.contacts)} contacts)")
    print(f"\n{len(result.highlights)} highlights:")
    for h in result.highlights:
        print(f"  {format_time(h.time)}  {h.label:<15} score {h.score:.2f}  rally #{h.rally_index}  {h.description}")
    print()
    print(reel_to_text(result.reel))
    print(f"\ndiagnostics: {json.dumps(result.diagnostics)}")

    if args.json:
        with open(args.json, "w") as f:
            json.dump(result.to_dict(), f, indent=2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
