# Cutting a release archive

Non-technical users install the app from a downloadable `.zip`/`.tar.gz` archive
rather than cloning the repo. `.github/workflows/release.yml` builds that archive —
never distribute a plain GitHub "Download ZIP", since it leaves the
`cdisc-bc-ncit-alignment` git submodule as an empty folder.

## Normal release

Release tags must be pushed from `main` and prefixed `version-` (e.g. `version-1.2.3`).
The workflow verifies the tagged commit is actually on `main` (via
`git merge-base --is-ancestor`) and fails immediately if it isn't — a tag on any other
branch will not produce a release.

1. On `main`, tag the commit you want to release and push the tag:
   ```bash
   git checkout main && git pull
   git tag version-1.2.3
   git push origin version-1.2.3
   ```
2. The `Release` workflow checks out the repo (with the submodule fully resolved via
   `submodules: recursive`), confirms the tag is on `main`, runs
   `scripts/build_release.py`, and publishes a GitHub Release named `version-1.2.3`
   (the tag name, used as-is for the release title) with two attached assets:
   - `cdisc-concept-curation-version-1.2.3.zip` (for Windows users)
   - `cdisc-concept-curation-version-1.2.3.tar.gz` (for Mac/Linux users)

## Testing the workflow without cutting a release

Run it via **Actions → Release → Run workflow** (workflow_dispatch) **from the `main`
branch** — the same "must be on main" check applies to a manual run, so triggering it
against any other branch fails fast. Optionally supply a `version` string. This builds
the same archives and uploads them as a workflow artifact instead of publishing a
GitHub Release — download the artifact from the workflow run summary to test it.

## Testing the packaging step locally

```bash
git submodule update --init --recursive   # only needed for a local test run
python scripts/build_release.py --version version-0.0.0-test
```

Writes `dist/cdisc-concept-curation-version-0.0.0-test.zip` and `.tar.gz`. Extract one
and confirm `cdisc-bc-ncit-alignment/` contains real files (not just a `.git`
pointer), then run the installer against the extracted copy to confirm it still works
end to end.

## What's inside the archive

Every file `git ls-files --recurse-submodules` reports as tracked — i.e. the same
files you'd get from a full recursive clone, minus all `.git` metadata — including
`install.py` and its platform wrapper scripts (`install.sh`, `Install (Mac).command`,
`Install (Windows).bat`) at the top level, ready for a non-technical user to
double-click after extracting.
