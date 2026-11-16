# gh-livekit

Clone, push to, and open PRs on `ndr-data/ndr-ai-core` as the **livekit-staff-aug** GitHub App.

`gh_app_token.py` creates short-lived GitHub App installation tokens. The app currently has
access to `ndr-ai-core` and `nexus-ai-platform`, with write access to contents, pull requests,
workflows and actions. Tokens last 1 hour. The git setup below gets a fresh token for every git
operation and stores nothing.

## Prerequisites

- [uv](https://docs.astral.sh/uv/), git, and the [GitHub CLI](https://cli.github.com/) (`gh`)
- The app's **App ID** and **private key** (`.pem`), from `<where the team keeps them>`

## 1. Set up credentials

Save the private key in this folder as `key.pem`. Then copy `.env.sample` to `.env` and fill it in:

```
GITHUB_APP_ID=<app id>
GITHUB_APP_PRIVATE_KEY_PATH=/absolute/path/to/gh-livekit/key.pem
```

- Use an absolute path, because git runs the script from inside your clone.
- A key saved as a single line (newlines lost, as when copied from a password manager) is fine. The script rebuilds it.
- `GITHUB_APP_INSTALLATION_ID` is optional. The script finds it when the app has one installation.
- Lock the files down and never commit them:

```bash
chmod 600 .env key.pem
```

Check that a token can be created (this prints only the `ghs_` prefix):

```bash
uv run -q --env-file .env gh_app_token.py | cut -c1-4
```

## 2. Clone ndr-ai-core

Point `GH_LIVEKIT` at this folder, then clone:

```bash
GH_LIVEKIT="$HOME/code/gh-livekit"
```

```bash
git clone \
  -c credential.helper= \
  -c "credential.helper=!uv run -q --env-file $GH_LIVEKIT/.env --script $GH_LIVEKIT/gh_app_token.py" \
  https://github.com/ndr-data/ndr-ai-core.git
```

The empty `credential.helper=` turns off your personal GitHub login **for this clone only**. Both
settings are saved in the clone's `.git/config`. Your other repos keep using your own account.

**Already have a clone?** Run these from inside it instead:

```bash
git config --local credential.helper ""
```

```bash
git config --local --add credential.helper "!uv run -q --env-file $GH_LIVEKIT/.env --script $GH_LIVEKIT/gh_app_token.py"
```

## 3. Verify

From inside the clone:

```bash
printf 'protocol=https\nhost=github.com\n\n' | git credential fill | grep username
```

This should print `username=x-access-token`. If you see your own username instead, the
credential helper isn't set up (redo step 2).

Test push access without pushing anything:

```bash
git push --dry-run origin HEAD:refs/heads/dry-run-check
```

This should print `* [new branch]`. A dry run creates nothing on GitHub.

## 4. Branch, commit, push

`main` is **not protected**, and the app can push to it directly. Always work on a branch and open a PR.

```bash
git switch -c my-feature
# ...make changes...
git commit -am "Describe the change"
git push -u origin my-feature
```

The push is made by the app. Commits are authored with your own git `user.name` and `user.email`.

<details>
<summary>Optional: author commits as the app bot</summary>

Run these in the clone only, not globally:

```bash
git config user.name "livekit-staff-aug[bot]"
git config user.email "280518028+livekit-staff-aug[bot]@users.noreply.github.com"
```

`280518028` is the bot account's GitHub user ID. Commits made this way aren't yet confirmed to
show up as the bot on GitHub.
</details>

## 5. Open a PR as the app

`gh` uses your personal login by default. Pass it the app token for a single command:

```bash
GH_TOKEN=$(uv run -q --env-file "$GH_LIVEKIT/.env" --script "$GH_LIVEKIT/gh_app_token.py") gh pr create --draft --fill
```

To make this easier, add a function to `~/.zshrc`:

```bash
ghapp() { GH_TOKEN=$(uv run -q --env-file "$HOME/code/gh-livekit/.env" --script "$HOME/code/gh-livekit/gh_app_token.py") gh "$@"; }
```

Then use `ghapp pr create --draft --fill`, `ghapp pr list`, and so on. PRs show up as
`livekit-staff-aug[bot]`.

Don't `export GH_TOKEN`. The token expires after an hour, and every `gh` command would run as the app.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Git uses your personal account or asks for a password | The credential helper isn't set in this clone (see step 3). Also check `git remote -v` is `https://`. A global `url."git@github.com:".insteadOf` rule sends git over SSH with your own key, so check with `git config --global --get-regexp '^url\.'` |
| `Missing env var: ...` | Wrong `.env` path, or a variable is missing from it |
| `GitHub API ... -> 401` | Wrong App ID or private key |
| `Repository not found` / `404` | The app isn't installed on that repo. Ask an org admin to add the repo to the app's installation |
| `Set GITHUB_APP_INSTALLATION_ID` | The app has several installations. Set the variable to one of the IDs the error lists |

## Files

- `gh_app_token.py`: creates a token. With no arguments it prints the token. As a git credential helper (`get`) it answers git's credential requests.
- `.env.sample`: a template for `.env`.
- `.env`, `key.pem`: your credentials. `.gitignore` excludes them.
