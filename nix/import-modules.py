import argparse
import importlib
import importlib.metadata
import json
import pkgutil
import re
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--expect")
parser.add_argument("modules", nargs="+")
args = parser.parse_args()

if args.expect:
    with open(args.expect) as handle:
        expected = json.load(handle)
    installed = {
        re.sub(r"[-_.]+", "-", dist.metadata["Name"]).lower(): dist.version
        for dist in importlib.metadata.distributions()
    }
    if installed != expected:
        missing = sorted(set(expected) - set(installed))
        extra = sorted(set(installed) - set(expected))
        differ = sorted(n for n in set(expected) & set(installed) if expected[n] != installed[n])
        sys.exit(f"closure differs from uv.lock: missing={missing} extra={extra} versions={differ}")

for root in args.modules:
    package = importlib.import_module(root)
    for module in pkgutil.walk_packages(package.__path__, f"{root}."):
        if not module.name.endswith(".__main__"):
            importlib.import_module(module.name)
    print(root)
