# Repository Security and Access

This repository follows a public-read, owner-write model. Making the repository
public allows anyone to view, clone, and fork it; it does not give the public
permission to push or merge changes into the original repository.

## Access policy

- The repository owner is the only account with write and administrative
  access unless another collaborator is deliberately invited.
- Pull request creation is limited to collaborators.
- Issues, Discussions, and Wiki are disabled.
- The `main` branch rejects deletion and force pushes and requires the CI checks
  to pass before changes are merged.
- GitHub Actions receives read-only repository contents permission by default
  and cannot approve pull requests.

## Security automation

The public repository enables the security features available for its GitHub
plan:

- Dependabot vulnerability alerts and the existing dependency update schedule.
- Secret scanning and push protection.
- CodeQL default setup for Python.
- Private vulnerability reporting.

Repository settings are enforced on GitHub and therefore are not completely
represented by files in the Git history. Recheck them after ownership,
visibility, or GitHub plan changes.

## Licensing boundary

The Apache License 2.0 applies only to original project code and documentation.
It does not replace or expand the licenses of upstream datasets, models, or
third-party artifacts. Generated artifacts may be published only after their
source licenses and redistribution conditions have been verified.
