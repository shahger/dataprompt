"""Shared HTTP plumbing; deliberately never print response bodies or credentials."""
import argparse
import math
import os
from pathlib import Path
import time
from urllib.parse import urlsplit

import requests


class ToolError(Exception):
    pass


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError("must be a finite positive number")
    return number


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("base_url", help="service origin, for example http://localhost:8000")
    result.add_argument("api_key", help="X-API-Key value (keep shell history private)")
    result.add_argument("--timeout", type=positive, default=300, help="total per-video deadline in seconds (default: 300)")
    result.add_argument("--request-timeout", type=positive, default=30, help="per-request timeout in seconds (default: 30)")
    result.add_argument("--poll-interval", type=positive, default=2, help="polling interval in seconds (default: 2)")
    return result


def analyze(args, path):
    parsed = urlsplit(args.base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ToolError("BASE_URL must be an http(s) URL without credentials, query or fragment")
    base = args.base_url.rstrip("/")
    started = time.monotonic()
    deadline = started + args.timeout
    headers = {"X-API-Key": args.api_key}
    if os.environ.get("CASHIER_SKIP_BROWSER_WARNING") == "1":
        headers["ngrok-skip-browser-warning"] = "1"

    def request(session, method, endpoint, **kwargs):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ToolError("per-video deadline exceeded")
        try:
            response = session.request(method, base + endpoint, headers=headers,
                                       timeout=min(args.request_timeout, remaining), **kwargs)
        except requests.RequestException as exc:
            raise ToolError(f"HTTP connection/request failed ({type(exc).__name__})") from None
        if not response.ok:
            raise ToolError(f"HTTP {response.status_code} from {endpoint.split('/jobs/')[0]}")
        try:
            payload = response.json()
        except ValueError:
            raise ToolError("server returned invalid JSON") from None
        if not isinstance(payload, dict):
            raise ToolError("server returned an invalid response object")
        return payload

    with requests.Session() as session:
        try:
            with Path(path).open("rb") as stream:
                submitted = request(session, "POST", "/api/v1/analyze", files={"file": (Path(path).name, stream, "video/quicktime")})
        except OSError:
            raise ToolError(f"cannot read video: {Path(path).name}") from None
        job_id = submitted.get("job_id")
        if not isinstance(job_id, str) or not job_id or not job_id.isalnum():
            raise ToolError("upload response has no valid job_id")
        while True:
            job = request(session, "GET", "/api/v1/jobs/" + job_id)
            status = job.get("status")
            if status == "failed":
                raise ToolError(f"job {job_id} failed; inspect the job endpoint for its error")
            if status == "done":
                if job.get("verdict") not in {"violation", "no_violation"} or not isinstance(job.get("violations"), list):
                    raise ToolError("done response has an invalid result schema")
                return job, time.monotonic() - started
            if status != "processing":
                raise ToolError("job response has an unknown status")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ToolError("per-video deadline exceeded")
            time.sleep(min(args.poll_interval, remaining))
