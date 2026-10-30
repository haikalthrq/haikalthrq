# Coding activity chart

This profile uses a rolling 12-calendar-month history of source files changed in commits authored by **haikalthrq**. It is an activity summary, not a language-proficiency score or an estimate of coding hours.

## Enable private + public history

1. Open [GitHub fine-grained personal access tokens](https://github.com/settings/personal-access-tokens/new).
2. Set **Resource owner** to `haikalthrq`. Select **All repositories** if every owned public and private repository should count, including newly created projects. Otherwise choose the exact repositories to include.
3. Set **Repository permissions > Contents** to **Read-only**. Leave the remaining permissions at their minimum defaults. Give the token a short expiration and renew it before it expires.
4. Copy the token **only** into [this profile repository's Actions secrets](https://github.com/haikalthrq/haikalthrq/settings/secrets/actions), using the name `CODING_ACTIVITY_TOKEN`. Do not paste the token into a README, issue, commit, chat, or log.
5. Open [Refresh coding activity](https://github.com/haikalthrq/haikalthrq/actions/workflows/refresh-coding-activity.yml) in GitHub Actions and choose **Run workflow** on `main`.
6. After the run succeeds, the chart at `assets/coding-activity.svg` is updated. Further refreshes are scheduled weekly on Mondays at 03:37 UTC.

The profile workflow's default `GITHUB_TOKEN` has `contents: write` only for the public profile repository and saves the generated chart. The separate `CODING_ACTIVITY_TOKEN` is passed only to the data-gathering Python step and requires read access only.

If the workflow cannot push the resulting commit, check this repository's Actions workflow permissions and any branch protection rules.

## What counts

- **Period:** the preceding 12 calendar months, measured in UTC.
- **Repos:** owned repositories the read-only token can access; public and private.
- **Branches:** all accessible branches. The same commit SHA is counted once per repository, even if several branches reference it.
- **Author:** commits associated with the GitHub username `haikalthrq` (not automated commits authored by bots).
- **Unit:** one source-file change per commit. Editing two Python files in one commit counts as two Python file edits. Editing the same Python file in three separate commits counts as three.
- **Notebook handling:** `.ipynb` file changes count as **Python (notebooks)**, separately from `.py` edits; notebook size and embedded charts do not multiply their weight. This classification assumes the notebook uses Python.
- **Forks:** exclude forks that have no additional commits ahead of their upstream default branch. Modified forks are eligible, but only commits authored by `haikalthrq` count.
- **Excluded:** docs, common generated/bundled files, dependencies, and files without a recognized source extension.

The chart contains **aggregate language counts only**. It publishes no private repo names, branch names, paths, commit identifiers, messages, or source contents. Logs show only counts and total GitHub API requests.

## Limitations

This is a count of source-file edits, not lines added, time spent, language expertise, or actual execution. A notebook's change might modify an output cell rather than executable Python. Work committed under an unlinked author identity, in inaccessible repositories, or outside the selected token scope is not counted. The script fails without replacing the previous chart when GitHub's API returns an error, the token lacks access, or the request budget is exhausted.

## Source and tests

- `scripts/coding_activity.py` gathers activity through GitHub's REST API and renders SVG without external chart services.
- `tests/test_coding_activity.py` checks date boundaries, source-file language mapping, branch deduplication, and privacy properties.
- `.github/workflows/test-coding-activity.yml` checks syntax and runs those tests on relevant changes.
- `.github/workflows/refresh-coding-activity.yml` validates and refreshes the chart with a GitHub Actions secret.
