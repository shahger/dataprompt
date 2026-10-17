"""Submit N videos simultaneously; measure wall time from upload to terminal result."""
from concurrent.futures import ThreadPoolExecutor, as_completed
import sys

try:
    from .common import ToolError, analyze, parser
except ImportError:
    from common import ToolError, analyze, parser


def main(argv=None):
    cli = parser(__doc__)
    cli.add_argument("videos", nargs="+")
    args = cli.parse_args(argv)
    durations, failed = [], False
    with ThreadPoolExecutor(max_workers=len(args.videos)) as pool:
        futures = {pool.submit(analyze, args, path): path for path in args.videos}
        for future in as_completed(futures):
            path = futures[future]
            try:
                job, duration = future.result()
                durations.append(duration)
                print(f"{path}: done {job['verdict']} {duration:.3f} s")
            except ToolError as exc:
                print(f"ERROR: {path}: {exc}", file=sys.stderr)
                failed = True
            except (OSError, ValueError, KeyError, TypeError):
                print(f"ERROR: {path}: invalid input or API response", file=sys.stderr)
                failed = True
    if durations:
        worst = max(durations)
        print(f"WORST: {worst:.3f} s -> {'OK (< 300 s)' if worst < 300 else 'TOO SLOW'}")
        failed |= worst >= 300
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
