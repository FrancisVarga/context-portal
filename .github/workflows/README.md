# GitHub Workflows

This directory contains GitHub Actions workflows for the context-portal project.

## Available Workflows

### 1. CI Workflow (`ci.yml`)
- **Trigger**: On push to `main` or `develop` branches, and on pull requests to `main`
- **Purpose**: Continuous integration testing
- **Actions**:
  - Tests on multiple Python versions (3.9, 3.10, 3.11, 3.12)
  - Runs database verification tests
  - Runs pytest suite (with graceful handling of missing dependencies)

### 2. Release Workflow (`release.yml`)
- **Trigger**: 
  - Automatically on push of version tags (e.g., `v0.2.5`)
  - Manually via workflow dispatch
- **Purpose**: Create releases with built packages
- **Actions**:
  1. **Test Job**: Runs comprehensive tests to ensure quality
     - Database verification tests  
     - Optional pytest suite
  2. **Release Job** (only if tests pass):
     - Builds Python wheel and source distribution
     - Creates GitHub release with version from `pyproject.toml`
     - Uploads built packages as release assets
     - Generates release notes

## How to Use

### Manual Release Creation
1. Go to the Actions tab in GitHub
2. Select "Release" workflow
3. Click "Run workflow"
4. Choose the branch and confirm release creation

### Automatic Release Creation
1. Update the version in `pyproject.toml`
2. Commit and push the changes
3. Create and push a git tag matching the version:
   ```bash
   git tag v0.2.6
   git push origin v0.2.6
   ```

## Test Coverage

The workflows test:
- ✅ Product context management (get/update)
- ✅ Decision logging and retrieval
- ✅ Database persistence verification  
- ✅ Multiple Python version compatibility
- ✅ Error handling and edge cases

This ensures that releases are thoroughly tested and reliable.