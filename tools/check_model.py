"""Check local notebook inference without FastAPI/Postgres or result payload output."""
import argparse
from pathlib import Path
import time

try:
    from .model_support import ModelCheckError,execute_model,load_model,offline_guard,quiet_model,timeout_seconds,validate_result,video_duration
except ImportError:
    from model_support import ModelCheckError,execute_model,load_model,offline_guard,quiet_model,timeout_seconds,validate_result,video_duration


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video',action='append',required=True,type=Path)
    parser.add_argument('--no-offline-guard',action='store_true')
    args=parser.parse_args(argv)
    failed=False
    if args.no_offline_guard: print('WARN: offline guard disabled explicitly')
    try:
        timeout=timeout_seconds()
        with offline_guard(not args.no_offline_guard):
            function,warnings=load_model()
            for warning in warnings: print('WARN:',warning)
            print('VIDEO | SECONDS | EVENTS | STATUS')
            for index,path in enumerate(args.video,1):
                started=time.monotonic()
                try:
                    duration=video_duration(path)
                    with quiet_model():
                        result=execute_model(function,path,started,timeout)
                        count=validate_result(result,duration)
                    elapsed=time.monotonic()-started
                    if elapsed>=timeout: raise ModelCheckError('JOB_TIMEOUT_SEC exceeded')
                    print(f'{index} | {elapsed:.3f} | {count} | PASS')
                except Exception as exc:
                    # Model exception text/result values may contain payloads.
                    message=str(exc) if isinstance(exc,ModelCheckError) else type(exc).__name__
                    print(f'{index} | {time.monotonic()-started:.3f} | - | FAIL: {message}')
                    failed=True
    except Exception as exc:
        message=str(exc) if isinstance(exc,ModelCheckError) else type(exc).__name__
        print('FAIL:',message)
        return 1
    return int(failed)


if __name__=='__main__': raise SystemExit(main())
