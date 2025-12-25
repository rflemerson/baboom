# 🛡️ Security Tasks (SAST/DAST)

## [SEC-001] Implement Secret Scanning (Gitleaks)
**Priority:** High
**Type:** SAST
**Description:**
Configure `gitleaks` to scan git history for accidental secret commits (API keys, passwords).
**Action Items:**
- [ ] Install `gitleaks` locally or via pre-commit.
- [ ] Run `gitleaks detect -v` on the repository.
- [ ] Add `gitleaks` to CI pipeline or pre-commit hooks.

## [SEC-002] Dynamic Application Security Testing (OWASP ZAP)
**Priority:** Medium
**Type:** DAST
**Description:**
Run OWASP ZAP against the running Django application to detect runtime vulnerabilities (XSS, SQLi, Headers).
**Action Items:**
- [ ] Install OWASP ZAP (Desktop or Docker).
- [ ] Run a "Baseline Scan" against `http://localhost:8000`.
- [ ] Review report and fix "High" and "Medium" alerts.

## [SEC-003] Advanced Code Scanning (Semgrep)
**Priority:** Low
**Type:** SAST
**Description:**
Add Semgrep for more semantic and custom security rules beyond what Ruff/Bandit provides.
**Action Items:**
- [ ] Install `semgrep`.
- [ ] Configure `semgrep` with `p/python` and `p/django` rulesets.
- [ ] Integrate into CI.
