# Pemystack Greenlight

AI-powered test selection, execution, and failure diagnosis for every PR.

Instead of running your entire test suite on every change, Greenlight reads the diff, picks only the relevant tests, runs them, and diagnoses failures with root cause and fix suggestions.

## Supported frameworks

Auto-detected from your repo:

- **Playwright** — E2E testing
- **Jest** / **Vitest** — JS unit + integration
- **Pytest** — Python testing
- **Go** — `go test`
- **Android** — Gradle instrumented tests

## Quick start

Add to `.github/workflows/greenlight.yml`:

```yaml
name: Greenlight

on:
  pull_request:
    types: [opened, synchronize, reopened]

jobs:
  greenlight:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: pemystack/greenlight-action@v1
        with:
          github_token: ${{ secrets.GITHUB_TOKEN }}
          # Provide ONE of these — whichever AI provider you use:
          anthropic_api_key: ${{ secrets.ANTHROPIC_API_KEY }}
          # openai_api_key: ${{ secrets.OPENAI_API_KEY }}
          # gemini_api_key: ${{ secrets.GEMINI_API_KEY }}
```

That's it. Greenlight auto-detects your test framework and handles everything.

## What it does

1. **Analyze** — AI reads the PR diff and selects which tests to run
2. **Test** — Runs only the selected tests (not your entire suite)
3. **Diagnose** — If tests fail, AI diagnoses root cause and suggests fixes
4. **Report** — Posts results as a PR comment

## Free plan

- 20 reviews/month
- Root cause diagnosis
- [Upgrade to Pro](https://github.com/marketplace/pemystack) for unlimited reviews, full diagnosis with fix suggestions, and Slack alerts

## Inputs

| Input | Required | Description |
|-------|----------|-------------|
| `github_token` | Yes | GitHub token for PR comments |
| `anthropic_api_key` | One of three | Anthropic (Claude) API key |
| `openai_api_key` | One of three | OpenAI (GPT) API key |
| `gemini_api_key` | One of three | Google (Gemini) API key |
| `test_command` | No | Custom test command (auto-detected) |
| `results_path` | No | Path to JUnit XML results (auto-detected) |
| `force_suite` | No | Override: smoke, targeted, or full |

## License

MIT
