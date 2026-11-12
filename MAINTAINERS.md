# For maintainers: one-time GitHub settings

These settings make "nobody can break an existing episode" true. They live in GitHub, not in files.

1. Settings → Branches → Add rule for `main`:
   - Require a pull request before merging; require approvals: 1;
   - Require review from Code Owners;
   - Require status checks to pass: `check` and `verify` (from `.github/workflows/episodes.yml`);
   - Admins may bypass ("Do not allow bypassing" stays off): with one maintainer, GitHub does not let the author approve their own pull request, so the owner merges their own changes as admin. Everyone else goes through review and checks.

Status (12.11.2026): rule 1 is on for `main`: checks `check` and `verify`, 1 approval, code owner review, no force pushes or deletions.
2. Settings → Actions → General: allow GitHub Actions; for fork pull requests require approval for first-time contributors.
3. Settings → General: enable "Allow squash merging" only, so history stays one commit per change.
