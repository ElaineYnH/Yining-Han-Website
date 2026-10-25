"""One-command replication; the input ZIP and individual records stay local."""
from pathlib import Path
import argparse
import json

from prepare_data import prepare, validate_work_dir
from tutorial import run


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, help='Your registered PSID download ZIP.')
    parser.add_argument('--work-dir', type=Path, default=Path.home()/'blog6_psid_work',
                        help='Private working directory, outside the website repository.')
    parser.add_argument('--reuse-prepared', action='store_true',
                        help='Use a database already prepared in --work-dir.')
    args = parser.parse_args()
    work = validate_work_dir(args.work_dir)
    if args.reuse_prepared:
        audit = json.loads((work/'preparation_audit.json').read_text())
    else:
        if args.input is None:
            parser.error('--input is required unless --reuse-prepared is supplied.')
        _, audit = prepare(args.input.expanduser().resolve(), work)
    run(work, audit)
    from build_post import main as build_post
    build_post()


if __name__ == '__main__':
    main()
