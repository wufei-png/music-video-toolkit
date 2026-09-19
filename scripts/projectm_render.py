"""Run one pinned projectM provider request without implicit setup or downloads."""

import argparse
import json
from pathlib import Path

from music_video_toolkit.projectm_provider import ProjectMError, render_projectm


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--build", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = render_projectm(args.request, args.output, args.checkout, args.build)
    except ProjectMError as exc:
        print(json.dumps({"status": "failed", "code": exc.code, "details": exc.details}))
        raise SystemExit(5) from exc
    print(json.dumps(result))


if __name__ == "__main__":
    main()
