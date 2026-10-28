# Agents

## Run commands in the repo's Nix environment

The repo's tools come from the flake's dev shell, which `.envrc` loads through
direnv, together with `.venv`. An agent's sandbox (Claude Code, Codex) rebuilds
`PATH` for its shells but keeps the variables the environment set: the shell
still has `IN_NIX_SHELL`, `DIRENV_DIR` and `VIRTUAL_ENV`, yet `PATH` has lost
every `/nix/store` entry. `uv`, `node`, `npm`, `pre-commit` and the other
flake tools are then missing, or a system copy answers in their place.
`eval "$(direnv export bash)"` does not repair it: direnv sees `DIRENV_DIR` and
takes the environment for loaded.

Run every command that needs the repo's tools through direnv, from the repo
root:

```bash
direnv exec . just test-core-unit
direnv exec . uv run pytest core
direnv exec . sh -c 'cd gui && npm test'
```

It loads the cached environment in under a second. `nix develop -c <cmd>` works
too but leaves out `.venv` and the `.envrc` steps. Check with
`command -v uv`: it names a path under `/nix/store` when the environment is
right.

A missing tool in an agent's shell is this, not a defect of the repo: do not
change `.envrc`, `flake.nix`, `nix/` or `docker/dev/` for it, and do not install
the tool another way.
