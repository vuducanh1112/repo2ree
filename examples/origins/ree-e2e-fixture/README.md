# ree-e2e-fixture

A tiny project the end-to-end suites fetch as an origin: by git, and as a tarball.
The testbed serves it from a stack of its own (`repo2ree_testbed.stack.origins`), with
a fixed author and date, so the commit and its SWHID are the same on every run.
