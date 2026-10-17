"""Indicative in-process CPU concurrency benchmark; no model result payload output."""
import argparse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time

try:
    from .model_support import ModelCheckError,execute_model,load_model,offline_guard,quiet_model,timeout_seconds,validate_result,video_duration
except ImportError:
    from model_support import ModelCheckError,execute_model,load_model,offline_guard,quiet_model,timeout_seconds,validate_result,video_duration


def positive(value):
    number=int(value)
    if number<1: raise argparse.ArgumentTypeError('must be a positive integer')
    return number


def percentile(values,fraction):
    ordered=sorted(values)
    index=(len(ordered)-1)*fraction
    lower=int(index); upper=min(lower+1,len(ordered)-1)
    return ordered[lower]+(ordered[upper]-ordered[lower])*(index-lower)


def workload(function,paths,workers,timeout):
    durations=[video_duration(path) for path in paths]
    submitted=time.monotonic()
    def one(index):
        started=time.monotonic()
        try:
            result=execute_model(function,paths[index],submitted,timeout)
            validate_result(result,durations[index])
            status='PASS'
        except Exception as exc:
            status='FAIL: '+(str(exc) if isinstance(exc,ModelCheckError) else type(exc).__name__)
        finished=time.monotonic()
        return {'index':index+1,'service':finished-started,'finish':finished-submitted,'status':status}
    with quiet_model(),ThreadPoolExecutor(max_workers=workers) as pool:
        rows=list(pool.map(one,range(len(paths))))
    last=max(row['finish'] for row in rows)
    safe=last<timeout and all(row['status']=='PASS' for row in rows)
    return rows,last,safe


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--videos',nargs='+',required=True,type=Path)
    parser.add_argument('--count',type=positive,default=5)
    parser.add_argument('--workers',type=positive,default=1)
    parser.add_argument('--sweep',action='store_true',help='measure each WORKERS value 1..4 (repeats inference)')
    parser.add_argument('--no-offline-guard',action='store_true')
    args=parser.parse_args(argv)
    try:
        files=[]
        for path in args.videos:
            if path.is_dir(): files.extend(sorted(p for p in path.iterdir() if p.is_file() and p.suffix.lower()=='.mov'))
            else: files.append(path)
        if not files: raise ModelCheckError('no videos found')
        paths=[files[index%len(files)] for index in range(args.count)]
        timeout=timeout_seconds()
        measured={}; failed=False
        if args.no_offline_guard: print('WARN: offline guard disabled explicitly')
        with offline_guard(not args.no_offline_guard):
            function,warnings=load_model()
            for warning in warnings: print('WARN:',warning)
            for workers in (range(1,5) if args.sweep else [args.workers]):
                rows,last,safe=workload(function,paths,workers,timeout)
                measured[workers]=safe
                print(f'WORKERS={workers} | VIDEO | SERVICE_SEC | FINISH_FROM_SUBMIT_SEC | STATUS')
                for row in rows: print(f"{workers} | {row['index']} | {row['service']:.3f} | {row['finish']:.3f} | {row['status']}")
                service=[row['service'] for row in rows]
                print(f'p50={percentile(service,.5):.3f}s p95={percentile(service,.95):.3f}s max={max(service):.3f}s last_finish={last:.3f}s budget={timeout:g}s -> {"OK" if safe else "TOO SLOW / FAILED"}')
                failed |= not safe
        safe_values=[value for value,safe in measured.items() if safe and 1<=value<=4]
        print('Largest safe MEASURED WORKERS among 1..4: '+(str(max(safe_values)) if safe_values else 'none'))
        if set(measured)!={1,2,3,4}: print('Other worker counts are unmeasured; use --sweep for comparison. No CPU-scaling extrapolation is made.')
        print('Indicative only: shared GIL/CPU/model state; no upload, DB, evidence or HTTP overhead. Threads cannot be killed; models must honor deadlines.')
        return int(failed)
    except Exception as exc:
        print('FAIL:',str(exc) if isinstance(exc,ModelCheckError) else type(exc).__name__)
        return 1


if __name__=='__main__': raise SystemExit(main())
