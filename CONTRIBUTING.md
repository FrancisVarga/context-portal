# Contributing to Context Portal MCP (ConPort)

Thank you for your interest in contributing to the Context Portal MCP project! We welcome contributions of all kinds, including bug reports, feature requests, documentation improvements, and code contributions.

By participating in this project, you are expected to uphold our [Code of Conduct](CODE_OF_CONDUCT.md). (Note: A CODE_OF_CONDUCT.md file is recommended but not currently present in this repo. You may want to create one.)

## How to Contribute

### Reporting Bugs

If you find a bug, please report it by opening a new issue on the [GitHub repository](https://github.com/GreatScottyMac/context-portal/issues).

When reporting a bug, please include:

*   A clear and concise description of the bug.
*   Steps to reproduce the behavior.
*   The version of ConPort you are using.
*   Your operating system and Python version.
*   Any relevant error messages or logs (like `output.log`).

### Suggesting Enhancements

If you have an idea for a new feature or enhancement, please suggest it by opening a new issue on the [GitHub repository](https://github.com/GreatScottyMac/context-portal/issues).

When suggesting an enhancement, please include:

*   A clear and concise description of the proposed enhancement.
*   The problem it solves or the benefit it provides.
*   Any potential design considerations.

### Setting Up Your Development Environment

To contribute code, you'll need to set up a development environment.

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/GreatScottyMac/context-portal.git
    cd context-portal
    ```

2.  **Create and Activate a Virtual Environment:**
    Using `uv` (recommended):
    ```bash
    uv venv
    source .venv/bin/activate # Linux/macOS
    # .venv\Scripts\activate.bat # Windows Command Prompt
    # .venv\Scripts\Activate.ps1 # Windows PowerShell
    ```
    Using standard `venv`:
    ```bash
    python3 -m venv .venv # Or 'python -m venv .venv'
    source .venv/bin/activate # Linux/macOS
    # .venv\Scripts\activate.bat # Windows Command Prompt
    # .venv\Scripts\Activate.ps1 # Windows PowerShell
    ```

3.  **Install Dependencies:**
    With your virtual environment activated:
    Using `uv` (recommended):
    ```bash
    uv pip install -r requirements.txt
    ```
    Using standard `pip`:
    ```bash
    pip install -r requirements.txt
    ```

### Code Contributions

We follow a standard GitHub pull request workflow.

1.  **Fork the Repository:** Fork the [context-portal repository](https://github.com/GreatScottyMac/context-portal).
2.  **Create a Branch:** Create a new branch for your contribution.
    ```bash
    git checkout -b feature/your-feature-name
    ```
    or
    ```bash
    git checkout -b bugfix/your-bugfix-name
    ```
3.  **Make Your Changes:** Implement your feature or bug fix.
4.  **Write Tests:** If applicable, add tests for your changes.
5.  **Run Tests:** Ensure all tests pass. (Details on running tests TBD - you may want to add a section on testing).
6.  **Code Style:** Adhere to the project's code style (e.g., PEP 8). (Details on code formatting/linting TBD - you may want to add a section on this).
7.  **Commit Your Changes:** Write clear and concise commit messages.
8.  **Push Your Branch:** Push your branch to your fork on GitHub.
9.  **Open a Pull Request:** Open a pull request from your fork to the main repository's `main` branch. Provide a clear description of your changes.

### Building and Publishing Docker Images

Docker images are automatically built and published to GitHub Container Registry (ghcr.io) when releases are created via the automated release workflow.

#### Automated Docker Publishing

The project uses GitHub Actions to automatically:
1. Build Docker images when a new release is published
2. Push images to GitHub Container Registry at `ghcr.io/francisvarga/context-portal`
3. Tag images with both version numbers and `latest`
4. Scan images for security vulnerabilities using Trivy
5. Generate Software Bill of Materials (SBOM) for transparency

#### Security Scanning

All Docker images undergo automated security scanning:

- **Vulnerability Scanning**: Uses Trivy to scan for known vulnerabilities in the OS and application dependencies
- **Severity Filtering**: Builds fail if critical or high-severity vulnerabilities are found
- **Security Reports**: Scan results are uploaded to GitHub's Security tab for review
- **SBOM Generation**: Software Bill of Materials is generated and uploaded as build artifacts
- **Continuous Monitoring**: Security scans run on every release and manual build

To trigger a new Docker image build:
1. Merge changes to the `main` branch
2. The release-please workflow will create a release PR
3. When the release PR is merged, a new release is published
4. The Docker image is automatically built and published

#### Manual Docker Building (Development)

For local development and testing:

1.  **Ensure Docker is Installed:** Make sure Docker Desktop (or Docker Engine) is installed and running on your system.
2.  **Build the Docker Image:**
    Navigate to the root of the `context-portal` repository:

    ```bash
    docker build -t context-portal-mcp:latest .
    # You can also tag with a specific version:
    # docker build -t context-portal-mcp:vX.Y.Z .
    ```

#### Using Published Images

You can pull the published images from GitHub Container Registry:

```bash
docker pull ghcr.io/francisvarga/context-portal:latest
# Or a specific version:
# docker pull ghcr.io/francisvarga/context-portal:v0.2.5
```

### Documentation Improvements

Improving documentation is a valuable contribution! You can suggest changes by opening issues or submitting pull requests directly to the `docs/` or root Markdown files (`README.md`, `CONTRIBUTING.md`, etc.).

### Licensing

By contributing to Context Portal MCP, you agree that your contributions will be licensed under the same [Apache-2.0 License](LICENSE) as the project.

## Code of Conduct

Please note that this project has a [Code of Conduct](CODE_OF_CONDUCT.md). By participating, you are expected to uphold this code. Please report unacceptable behavior to [YOUR_EMAIL_ADDRESS] (Note: Replace with a suitable contact method).