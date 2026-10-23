"""Run a desktop entry's argv in its declared directory, without a shell."""
import os
import sys


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) < 2:
        print("kilix-icewm: launch needs a working directory and command", file=sys.stderr)
        return 1
    try:
        os.chdir(args[0])
        os.execvp(args[1], args[1:])
    except OSError as exc:
        print(f"kilix-icewm: could not launch application: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
