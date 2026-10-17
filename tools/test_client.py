"""Smoke-test one video and save returned JPEG evidence."""
import base64
from pathlib import Path
import sys

try:
    from .common import ToolError, analyze, parser
except ImportError:
    from common import ToolError, analyze, parser


def main(argv=None):
    cli = parser(__doc__)
    cli.add_argument("video")
    cli.add_argument("--output-dir", type=Path, default=Path("."))
    args = cli.parse_args(argv)
    try:
        job, duration = analyze(args, args.video)
        args.output_dir.mkdir(parents=True, exist_ok=True)
        for vi, violation in enumerate(job["violations"]):
            frames = violation.get("evidence_frames", [])
            if not 1 <= len(frames) <= 3:
                raise ToolError("violation must contain 1-3 evidence frames")
            for fi, frame in enumerate(frames):
                raw = base64.b64decode(frame["image_base64"], validate=True)
                if not raw.startswith(b"\xff\xd8") or not raw.endswith(b"\xff\xd9"):
                    raise ToolError("evidence is not JPEG")
                destination = args.output_dir / f"evidence_{job['job_id']}_{vi}_{fi}.jpg"
                destination.write_bytes(raw)
        print(f"job_id: {job['job_id']} | status: done | verdict: {job['verdict']} | elapsed: {duration:.3f} s")
        return 0
    except ToolError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except (OSError, ValueError, KeyError, TypeError):
        # Keep invalid base64 and arbitrary response bodies out of error output.
        print("ERROR: smoke test failed; check connectivity, job status, and evidence schema", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
