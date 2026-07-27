# Package release procedure

This procedure publishes the Python package. The separately versioned native
Linux engine is published as a GitHub Release before this procedure and is
referenced by `koreanfa/engine_manifest.json`.

`package-release.yml` has only a `workflow_dispatch` trigger. It does not run
when a branch is pushed, a pull request is opened, or a tag is created.

## One-time PyPI and GitHub setup

Before the first release, configure a PyPI pending Trusted Publisher for:

- PyPI project: `koreanfa`
- GitHub owner: `hyung8758`
- GitHub repository: `Korean_FA`
- Workflow filename: `package-release.yml`
- GitHub environment: `pypi`

In the GitHub repository, create an environment named `pypi` and require a
maintainer's approval for deployments. Do not create or store a PyPI API token
in GitHub Secrets: the publish job uses GitHub OIDC through PyPI Trusted
Publishing.

## Release steps

1. Merge the release-ready code into `master`. The feature-branch package CI
   and the `master` pull-request engine candidate build must both be successful.
2. Confirm that the public engine archive URL and SHA-256 in
   `koreanfa/engine_manifest.json` are the intended release artifact.
3. Confirm that `koreanfa/_version.py` contains the intended PEP 440 version,
   for example `2.0.0`.
4. Create and push the matching annotated package tag, for example `v2.0.0`.
   The engine tag `koreanfa-engine-v2.0.0` is not a substitute for this package
   tag.
5. In GitHub Actions, open **Publish KoreanFA package**, select `v2.0.0`, set
   `version` to `2.0.0`, and run it first with `publish` unchecked. This is the
   release dry-run: it verifies the tag, builds the sdist/wheel, validates
   metadata, installs the wheel into a clean virtual environment, installs the
   engine, and executes Korean/Japanese Python API and CLI file/directory
   alignment.
6. Review the successful dry-run and its `koreanfa-2.0.0-distributions`
   artifact. Run the same workflow again with `publish` checked.
7. Approve the protected `pypi` environment when GitHub pauses the publish job.
   PyPI then receives exactly the artifact built by the successful verification
   job.
8. Confirm the release after PyPI indexes it:

   ```bash
   python -m pip install --upgrade koreanfa==2.0.0
   koreanfa engine install
   koreanfa align sample.wav sample.txt
   ```

9. Create the human-facing GitHub Release for `v2.0.0` with release notes and a
   link to the PyPI project. Do not re-upload the same version: PyPI releases
   are immutable. If a correction is needed after publishing, release a new
   version instead.
