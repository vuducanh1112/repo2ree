"""Register stores and mint the tokens their workbenches dial in with, on the service host.

    python -m repo2ree_api.store_admin add lab-a --label "Lab A"
    python -m repo2ree_api.store_admin token lab-a     # prints a new token, once
    python -m repo2ree_api.store_admin revoke <first 8 characters of a token>
    python -m repo2ree_api.store_admin list

A token is shown once and kept only as a digest; whoever runs a store's workbench starts it
with ``--store lab-a=PATH`` and that token.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from repo2ree_api.settings import service_settings
from repo2ree_supervisor import StoreRegistry, UnknownStoreError


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m repo2ree_api.store_admin")
    commands = parser.add_subparsers(dest="command", required=True)
    add = commands.add_parser("add", help="register a store")
    add.add_argument("store_id")
    add.add_argument("--label", default="")
    commands.add_parser("token", help="mint a token for a store's workbench").add_argument("store_id")
    commands.add_parser("revoke", help="revoke the tokens starting with PREFIX").add_argument("prefix")
    commands.add_parser("list", help="list the registered stores")
    args = parser.parse_args(argv)

    stores = StoreRegistry(service_settings.CONTROL_STATE_DIR / "stores.json")
    try:
        if args.command == "add":
            record = stores.add(args.store_id, args.label)
            sys.stdout.write(f"registered store {record.store_id}\n")
        elif args.command == "token":
            sys.stdout.write(f"{stores.mint_token(args.store_id)}\n")
        elif args.command == "revoke":
            revoked = stores.revoke(args.prefix)
            sys.stdout.write(f"revoked {revoked} token(s)\n")
            return 0 if revoked else 1
        else:
            for record in stores.all():
                sys.stdout.write(f"{record.store_id}\t{record.label}\n")
    except (ValueError, UnknownStoreError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
