# ARCHIVED: This README was moved to `archive/docs_removed/scripts/README.md` as part of the documentation consolidation.

If you need the original scripts documentation, see `archive/docs_removed/scripts/README.md`.

WARNING: These scripts will perform git actions that change the repository index and should be run with a clean working tree (no uncommitted changes).

1) Split & push Anchor's history into a new repo (safest path):

```pwsh
./split_anchor_repo.ps1 -RemoteUrl "https://github.com/External-Context-Engine/Anchor-.git" -Push
```

This does the following:
- Creates a subtree split of `anchor/` into a new branch (time-stamped).
- Adds a remote called `anchor-remote`.
- Optionally pushes the split branch to `anchor-remote` if `-Push` is set.

2) Optionally replace the `anchor/` directory with a Git submodule:

```pwsh
./convert_anchor_to_submodule.ps1 -RemoteUrl "https://github.com/External-Context-Engine/Anchor-.git"
```

This does the following:
- Removes `anchor/` from the repo index while preserving local files.
- Adds the Anchor repo as a submodule at the `anchor/` path.
- Commits the `.gitmodules` and submodule pointer commit.

CI and developer guidelines
- Update `ECE_Core/.github/workflows/integration-tests.yml` to ensure `actions/checkout` fetches submodules: set `submodules: 'recursive'` and `fetch-depth: 0` (done in this repo).
- Developers should use `git clone --recurse-submodules <parent-repo>` to clone with submodules initialized, or `git submodule update --init --recursive` after cloning.

- Notes & Safety
- The scripts are intended to be run interactively, not in CI.
- If you want to leave Anchor as a fully independent repo with its own CI, also add a skeleton CI workflow under `anchor/.github/workflows/anchor-ci-template.yml`.

Migration Checklist (recommended)
1) Create the Anchor repository on GitHub and make sure you have push access.
2) Run `./split_anchor_repo.ps1 -RemoteUrl '<remote>' -Push` from repo root to push anchor history.
3) Verify the new repo on GitHub contains expected commits and the main branch.
4) Run `./convert_anchor_to_submodule.ps1 -RemoteUrl '<remote>'` to replace the `anchor/` folder with the submodule and commit changes to parent repo.
5) Update CI (already updated in this repo) and ensure `actions/checkout` checks out submodules recursively.
6) If you want to keep Anchor tests separate, push the `anchor/.github/workflows/anchor-ci-template.yml` to the anchor repo after step (2) and customize.

Rollback steps
- If you need to undo submodule conversion, you can re-checkout the prior commit in the parent repo and optionally re-add the anchor files from the split branch.
- If you pushed the split branch to a new repo and want to start over, delete the remote branch and the remote repo (careful: this is destructive).

