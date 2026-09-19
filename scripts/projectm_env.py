"""Prepare, build, and validate the pinned external projectM runtime."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INTEGRATION = ROOT / "integrations/projectm"
LOCK = json.loads((INTEGRATION / "lock.json").read_text(encoding="utf-8"))


def run(*args: str, cwd: Path | None = None) -> str:
    result = subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=True)
    return result.stdout.strip()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def patch_bytes() -> list[bytes]:
    patches = []
    for item in LOCK["patches"]:
        path = INTEGRATION / "patches" / item["file"]
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError(f"patch changed: {path}")
        patches.append(data)
    if hashlib.sha256(b"".join(patches)).hexdigest() != LOCK["patch_stack_sha256"]:
        raise ValueError("patch stack changed")
    return patches


def library_path(build: Path) -> Path:
    return build / "src/libprojectM/libprojectM-4.dylib"


def provider_path(build: Path) -> Path:
    return build / "mvt-projectm-render"


def runtime_lock(checkout: Path) -> Path:
    return checkout / ".git/mvt-projectm-lock.json"


def build_lock(build: Path) -> Path:
    return build / "mvt-projectm-build.json"


def build_identity(checkout: Path, build: Path) -> dict[str, str]:
    return {
        "checkout": str(checkout),
        "commit": LOCK["commit"],
        "patch_stack_sha256": LOCK["patch_stack_sha256"],
        "library_sha256": sha256(library_path(build)),
        "provider_sha256": sha256(provider_path(build)),
        "provider_source_sha256": sha256(INTEGRATION / "provider.cpp"),
        "cmake_cache_sha256": sha256(build / "CMakeCache.txt"),
    }


def check(checkout: Path, build: Path | None = None) -> dict[str, str]:
    patch_bytes()
    if run("git", "rev-parse", "HEAD", cwd=checkout) != LOCK["commit"]:
        raise ValueError("upstream commit differs from lock")
    if (
        run("git", "-C", str(checkout / "vendor/projectm-eval"), "rev-parse", "HEAD")
        != LOCK["eval_submodule_commit"]
    ):
        raise ValueError("evaluation submodule differs from lock")
    if sha256(checkout / LOCK["license_file"]) != LOCK["license_sha256"]:
        raise ValueError("license differs from lock")
    diff = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=checkout, capture_output=True, check=True
    ).stdout
    if hashlib.sha256(diff).hexdigest() != LOCK["applied_diff_sha256"]:
        raise ValueError("checkout differs from locked patch")
    if run("git", "ls-files", "--others", "--exclude-standard", cwd=checkout):
        raise ValueError("unexpected untracked source in checkout")
    expected = {key: LOCK[key] for key in ("commit", "patch_stack_sha256")}
    if json.loads(runtime_lock(checkout).read_text(encoding="utf-8")) != expected:
        raise ValueError("runtime lock differs")
    result = {"checkout": str(checkout), **expected}
    if build is not None:
        identity = build_identity(checkout, build)
        if json.loads(build_lock(build).read_text(encoding="utf-8")) != identity:
            raise ValueError("build binary or configuration differs from recorded identity")
        cache = (build / "CMakeCache.txt").read_text(encoding="utf-8")
        if f"CMAKE_HOME_DIRECTORY:INTERNAL={checkout}" not in cache:
            raise ValueError("build configured from another source checkout")
        result["library_sha256"] = identity["library_sha256"]
    return result


def prepare(checkout: Path, source: str) -> dict[str, str]:
    patch_bytes()
    if not checkout.exists():
        checkout.parent.mkdir(parents=True, exist_ok=True)
        run("git", "clone", "--no-checkout", source, str(checkout))
        run("git", "checkout", "--detach", LOCK["commit"], cwd=checkout)
        run("git", "submodule", "update", "--init", "vendor/projectm-eval", cwd=checkout)
    current = subprocess.run(
        ["git", "diff", "--binary", "HEAD"], cwd=checkout, capture_output=True, check=True
    ).stdout
    if hashlib.sha256(current).hexdigest() != LOCK["applied_diff_sha256"]:
        if current:
            raise ValueError("checkout has unexpected edits; choose a fresh external directory")
        for item in LOCK["patches"]:
            patch = INTEGRATION / "patches" / item["file"]
            run("git", "apply", "--check", "--unidiff-zero", str(patch), cwd=checkout)
            run("git", "apply", "--unidiff-zero", str(patch), cwd=checkout)
    runtime_lock(checkout).write_text(
        json.dumps({key: LOCK[key] for key in ("commit", "patch_stack_sha256")}, sort_keys=True)
        + "\n",
        encoding="utf-8",
    )
    return check(checkout)


def build_runtime(checkout: Path, build: Path) -> dict[str, str]:
    check(checkout)
    run(
        "cmake",
        "-S",
        str(checkout),
        "-B",
        str(build),
        "-DCMAKE_BUILD_TYPE=Release",
        "-DENABLE_PLAYLIST=OFF",
        "-DBUILD_TESTING=OFF",
        "-DENABLE_SDL_UI=OFF",
        "-DENABLE_SYSTEM_PROJECTM_EVAL=OFF",
        "-DENABLE_INSTALL=ON",
    )
    run("cmake", "--build", str(build), "--parallel", "6")
    lib = library_path(build)
    run(
        "c++",
        "-std=c++17",
        "-O2",
        "-DGL_SILENCE_DEPRECATION",
        "-I",
        str(checkout / "src/api/include"),
        "-I",
        str(build / "src/api/include"),
        str(INTEGRATION / "provider.cpp"),
        "-L",
        str(lib.parent),
        "-lprojectM-4",
        f"-Wl,-rpath,{lib.parent}",
        "-framework",
        "OpenGL",
        "-o",
        str(provider_path(build)),
    )
    build_lock(build).write_text(
        json.dumps(build_identity(checkout, build), sort_keys=True) + "\n", encoding="utf-8"
    )
    return check(checkout, build)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("prepare", "build", "check"))
    parser.add_argument("--checkout", type=Path, required=True)
    parser.add_argument("--build", type=Path)
    parser.add_argument("--source", default=LOCK["repository"])
    args = parser.parse_args()
    checkout = args.checkout.expanduser().resolve()
    build = args.build.expanduser().resolve() if args.build else None
    if (
        checkout == ROOT
        or ROOT in checkout.parents
        or (build is not None and (build == ROOT or ROOT in build.parents))
    ):
        parser.error("projectM source and build must be outside the MVT repository")
    if args.action == "build" and build is None:
        parser.error("--build is required for build")
    try:
        if args.action == "prepare":
            result = prepare(checkout, args.source)
        elif args.action == "build":
            assert build is not None
            result = build_runtime(checkout, build)
        else:
            result = check(checkout, build)
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        parser.exit(1, f"projectM {args.action} failed: {exc}\n")
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
