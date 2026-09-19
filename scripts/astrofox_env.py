"""Explicitly prepare, build and check a pinned external Astrofox checkout."""

import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations/astrofox"
LOCK = json.loads((INTEGRATION / "lock.json").read_text(encoding="utf-8"))


def run(*args: str, cwd: Path | None = None, capture: bool = False) -> bytes:
    result = subprocess.run(args, cwd=cwd, check=True, capture_output=capture)
    return result.stdout if capture else b""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_hash(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def patch_bytes() -> list[bytes]:
    patches = []
    for item in LOCK["patches"]:
        path = INTEGRATION / "patches" / item["file"]
        content = path.read_bytes()
        if digest(content) != item["sha256"]:
            raise ValueError(f"patch hash mismatch: {path}")
        patches.append(content)
    if digest(b"".join(patches)) != LOCK["patch_stack_sha256"]:
        raise ValueError("patch stack hash mismatch")
    return patches


def runtime_lock(checkout: Path) -> Path:
    return checkout / ".git/mvt-lock.json"


def write_runtime_lock(checkout: Path) -> None:
    identity = {key: LOCK[key] for key in ("commit", "patch_stack_sha256", "applied_diff_sha256")}
    runtime_lock(checkout).write_text(
        json.dumps(identity, sort_keys=True, indent=2) + "\n", encoding="utf-8"
    )


def check(checkout: Path) -> None:
    patches = patch_bytes()
    if not checkout.is_dir():
        raise ValueError(f"checkout missing: {checkout}")
    commit = run("git", "rev-parse", "HEAD", cwd=checkout, capture=True).decode().strip()
    if commit != LOCK["commit"]:
        raise ValueError(f"upstream commit mismatch: {commit}")
    for key, hash_key in (
        ("package_lock", "package_lock_sha256"),
        ("license_file", "license_sha256"),
    ):
        path = checkout / LOCK[key]
        if file_hash(path) != LOCK[hash_key]:
            raise ValueError(f"pinned {key} mismatch: {path}")
    package = json.loads((checkout / "package.json").read_text(encoding="utf-8"))
    if package["license"] != LOCK["license"]:
        raise ValueError("upstream license metadata changed")
    if (
        run("pnpm", "--version", capture=True).decode().strip()
        != LOCK["package_manager"].split("@")[1]
    ):
        raise ValueError("pnpm version differs from lock")
    observed = run("git", "diff", "--binary", "HEAD", cwd=checkout, capture=True)
    if digest(observed) != LOCK["applied_diff_sha256"]:
        raise ValueError("checkout differs from locked downstream patch result")
    untracked = run("git", "ls-files", "--others", "--exclude-standard", cwd=checkout, capture=True)
    if untracked:
        raise ValueError(f"unexpected untracked source: {untracked.decode().strip()}")
    expected_runtime_lock = {
        key: LOCK[key] for key in ("commit", "patch_stack_sha256", "applied_diff_sha256")
    }
    if json.loads(runtime_lock(checkout).read_text(encoding="utf-8")) != expected_runtime_lock:
        raise ValueError("runtime lock differs from repository lock")
    print(
        json.dumps(
            {
                "commit": commit,
                "patches": len(patches),
                "patch_stack_sha256": LOCK["patch_stack_sha256"],
                "checkout": str(checkout),
            }
        )
    )


def prepare(checkout: Path) -> None:
    patch_bytes()
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run(
            "git", "clone", "--filter=blob:none", "--no-checkout", LOCK["repository"], str(checkout)
        )
        run("git", "checkout", "--detach", LOCK["commit"], cwd=checkout)
    current = run("git", "diff", "--binary", "HEAD", cwd=checkout, capture=True)
    if digest(current) == LOCK["applied_diff_sha256"]:
        write_runtime_lock(checkout)
        check(checkout)
        return
    if current:
        raise ValueError("checkout has unexpected edits; choose a fresh external path")
    for item in LOCK["patches"]:
        patch = INTEGRATION / "patches" / item["file"]
        run("git", "apply", "--check", str(patch), cwd=checkout)
        run("git", "apply", str(patch), cwd=checkout)
    if LOCK["new_files"]:
        run("git", "add", "-N", "--", *LOCK["new_files"], cwd=checkout)
    write_runtime_lock(checkout)
    check(checkout)


def build(checkout: Path) -> None:
    check(checkout)
    if shutil.which("pnpm") is None:
        raise ValueError("pnpm is required")
    run("pnpm", "install", "--frozen-lockfile", cwd=checkout)
    run("pnpm", "build:renderer", cwd=checkout)
    run("pnpm", "exec", "tsc", "--noEmit", cwd=checkout)
    run("pnpm", "lint", cwd=checkout)
    check(checkout)
    if not (checkout / "out/index.html").is_file():
        raise ValueError("desktop static renderer missing out/index.html")
    print(json.dumps({"built": True, "entry": str(checkout / "out/index.html")}))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "build", "check"))
    parser.add_argument("--checkout", type=Path, required=True)
    args = parser.parse_args()
    checkout = args.checkout.expanduser().resolve()
    if checkout == ROOT or ROOT in checkout.parents:
        parser.error("Astrofox checkout must be outside the MVT repository")
    try:
        {"prepare": prepare, "build": build, "check": check}[args.action](checkout)
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"astrofox {args.action} failed: {exc}\n")


if __name__ == "__main__":
    main()
