from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from wheelbuilder.builder import BuildPlatform, build_wheels, compare_versions
from wheelbuilder.piprepo import RepoFolder
from wheelbuilder.registry import WEEKLY_WHEELS, WHEELS


def _write_build_summary(failed: list[str]) -> None:
    """Print a build summary and write it to $GITHUB_STEP_SUMMARY if available."""
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not failed:
        print("\n✅ All packages built successfully.\n")
        if summary_path:
            with open(summary_path, "a") as f:
                f.write("## ✅ All packages built successfully\n")
        return
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"⚠️  FAILED ({len(failed)}):")
    for name in failed:
        print(f"  ✗ {name}")
    print(f"{sep}\n")
    if summary_path:
        with open(summary_path, "a") as f:
            f.write(f"## ⚠️ Failed Packages ({len(failed)})\n\n")
            for name in failed:
                f.write(f"- `{name}`\n")
            f.write("\n> These packages will be retried on the next scheduled run.\n")


class WheelBuilderCLI:
    def __init__(self) -> None:
        self.parser = self._make_parser()

    def _make_parser(self) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(prog="wheelbuilder")
        sub = parser.add_subparsers(dest="command", required=True)

        build = sub.add_parser("build", help="Build a single anaconda package")
        build.add_argument("package")
        build.add_argument("output")
        build.add_argument("--version", default=None)
        build.add_argument(
            "--platform",
            choices=[p.value for p in BuildPlatform],
            default=None,
        )
        build.add_argument("--all", action="store_true")
        build.set_defaults(func=self.cmd_build)

        build_all = sub.add_parser("build-all", help="Build every supported package")
        build_all.add_argument("output")
        build_all.add_argument(
            "--platform",
            choices=[p.value for p in BuildPlatform],
            default=None,
        )
        build_all.set_defaults(func=self.cmd_build_all)

        action = sub.add_parser(
            "action-build",
            help="Build all packages, optionally only those needing updates",
        )
        action.add_argument("output")
        action.add_argument(
            "--checks",
            action="store_true",
            help="Only build packages whose pypi version is newer than anaconda",
        )
        action.set_defaults(func=self.cmd_action_build)

        repo = sub.add_parser("pip-repo", help="Generate a simple-index HTML repo")
        repo.add_argument("src_folder")
        repo.add_argument("output")
        repo.set_defaults(func=self.cmd_pip_repo)

        return parser

    # -------------------------------------------------------------- commands

    def cmd_build(self, args: argparse.Namespace) -> None:
        wheel_cls = WHEELS.get(args.package)
        if wheel_cls is None:
            raise SystemExit(f"unsupported package: {args.package}")
        platform = BuildPlatform(args.platform) if args.platform else None
        failures = build_wheels(wheel_cls, args.version, platform, Path(args.output))
        if failures:
            raise SystemExit(f"Build failures: {', '.join(failures)}")

    def cmd_build_all(self, args: argparse.Namespace) -> None:
        platform = BuildPlatform(args.platform) if args.platform else None
        all_failures: list[str] = []
        for wheel_cls in WHEELS.values():
            all_failures.extend(build_wheels(wheel_cls, None, platform, Path(args.output)))
        if all_failures:
            raise SystemExit("Build failures:\n" + "\n".join(f"  {f}" for f in all_failures))

    def cmd_action_build(self, args: argparse.Namespace) -> None:
        output = Path(args.output)
        failed: list[str] = []
        for name, wheel_cls in WEEKLY_WHEELS.items():
            try:
                if args.checks:
                    platforms = compare_versions(name, wheel_cls)
                    if not platforms:
                        continue
                    filter_ = platforms[0] if len(platforms) == 1 else None
                    failed.extend(build_wheels(wheel_cls, None, filter_, output))
                else:
                    failed.extend(build_wheels(wheel_cls, None, None, output))
            except Exception as exc:
                print(f"[FAILED] {name}: {exc}")
                failed.append(name)
        _write_build_summary(failed)

    def cmd_pip_repo(self, args: argparse.Namespace) -> None:
        repo = RepoFolder(Path(args.src_folder))
        repo.generate_simple(Path(args.output))

    # ------------------------------------------------------------------ run

    def run(self, argv: list[str] | None = None) -> int:
        args = self.parser.parse_args(argv)
        args.func(args)
        return 0


def main(argv: list[str] | None = None) -> int:
    return WheelBuilderCLI().run(argv if argv is not None else sys.argv[1:])
