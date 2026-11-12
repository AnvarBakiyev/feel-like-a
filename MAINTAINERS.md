# For maintainers: one-time GitHub settings

These settings make "nobody can break an existing episode" true. They live in GitHub, not in files.

1. Settings → Branches → Add rule for `main`:
   - Require a pull request before merging; require approvals: 1;
   - Require review from Code Owners;
   - Require status checks to pass: `check` and `verify` (from `.github/workflows/episodes.yml`);
   - Do not allow bypassing the above settings (also for admins).
2. Settings → Actions → General: allow GitHub Actions; for fork pull requests require approval for first-time contributors.
3. Settings → General: enable "Allow squash merging" only, so history stays one commit per change.
