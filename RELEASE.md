# Creating a New Release

This document outlines the process for creating a new release of the IBM API Connect Theme Manager.

## Release Process

1. **Update CHANGELOG.md**

   First, update the CHANGELOG.md file with details about the new release:

   - Move changes from "Unreleased" to a new version section
   - Add date to the new version entry
   - Document all significant changes, additions, and fixes

2. **Commit Changes**

   Commit all final changes to the main branch:

   ```bash
   git add CHANGELOG.md
   git commit -m "Prepare release vX.Y.Z"
   git push origin main
   ```

3. **Create and Push a Tag**

   Create a new version tag and push it to trigger the release workflow:

   ```bash
   git tag -a vX.Y.Z -m "Release version X.Y.Z"
   git push origin vX.Y.Z
   ```

4. **Monitor GitHub Actions**

   The release workflow will automatically:

   - Build the release package
   - Create a GitHub release
   - Attach assets to the release
   - Use the CHANGELOG.md as the release notes

   We can monitor the progress in the Actions tab of the GitHub repository.

5. **Verify the Release**

   Once the workflow completes:

   - Check the Releases page on GitHub
   - Verify that all assets are attached
   - Confirm the release notes are correct

## Version Numbering Convention

We follow semantic versioning (SEMVER):

- **MAJOR version (X)**: Incompatible API changes
- **MINOR version (Y)**: Add functionality in a backward-compatible manner
- **PATCH version (Z)**: Backward-compatible bug fixes

## Release Checklist

- [ ] Update CHANGELOG.md
- [ ] Commit all changes
- [ ] Create and push the version tag
- [ ] Verify the release workflow completed successfully
- [ ] Test the released assets
- [ ] Announce the release to users (if applicable)
