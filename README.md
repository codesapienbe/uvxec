# UV Cross-Platform Installer

A cross-platform installer for uv-based Python applications that provides GUI-based installation with automatic dependency management, shortcut creation, and OS-specific integration.

## Features

- **Cross-platform support**: Windows, macOS, and Linux
- **GUI installation wizard**: User-friendly directory selection and progress feedback
- **Automatic dependency management**: Uses uv for fast, reliable package installation
- **Desktop integration**: Creates shortcuts and application launchers
- **Repository cloning**: Direct installation from GitHub repositories
- **Python version validation**: Ensures compatibility before installation

## Requirements

- Python >= 3.9
- Git (for repository cloning)
- Operating system specific dependencies:
  - Windows: `winshell` (automatically installed)
  - macOS: Standard system tools
  - Linux: Standard desktop environment

## Installation

### From PyPI

```bash
pip install uv-cross-installer
```

### From Source

```bash
git clone https://github.com/codesapienbe/uv-cross-installer.git
cd uv-cross-installer
uv sync
uv pip install -e .
```

## Usage

### Command Line Interface

```bash
uv-install <repository-url> <app-name> [--python-version <version>]
```

Example:
```bash
uv-install https://github.com/user/my-app.git MyApp --python-version 3.9
```

### Programmatic Usage

```python
from uv_cross_installer import CrossPlatformInstaller

installer = CrossPlatformInstaller(
    repo_url="https://github.com/user/my-app.git",
    app_name="MyApp",
    python_version="3.9"
)

success = installer.install()
```

## Development

### Building the Project

#### Prerequisites

Ensure you have uv installed:
```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

#### Development Setup

1. **Clone the repository**:
   ```bash
   git clone https://github.com/codesapienbe/uv-cross-installer.git
   cd uv-cross-installer
   ```

2. **Create and sync the virtual environment**:
   ```bash
   uv sync
   ```

3. **Install development dependencies**:
   ```bash
   uv sync --extra dev
   ```

4. **Activate the virtual environment**:
   ```bash
   source .venv/bin/activate  # Linux/macOS
   .venv\Scripts\activate     # Windows
   ```

#### Running Tests

```bash
uv run pytest
```

#### Code Formatting and Linting

```bash
# Format code
uv run black .

# Lint code
uv run flake8
```

### Building Distribution Packages

#### Build wheel and source distribution

```bash
uv build
```

This creates distribution files in the `dist/` directory:
- `uv_cross_installer-1.0.0-py3-none-any.whl`
- `uv_cross_installer-1.0.0.tar.gz`

#### Verify the build

```bash
# Check package metadata
uv run python -m pip show uv-cross-installer

# Test installation from wheel
uv pip install dist/uv_cross_installer-1.0.0-py3-none-any.whl
```

## Deployment

### Publishing to PyPI

#### Prerequisites

1. **Install publishing tools**:
   ```bash
   uv add --dev twine
   ```

2. **Configure PyPI credentials**:
   ```bash
   # Create ~/.pypirc file
   cat > ~/.pypirc << EOF
   [distutils]
   index-servers = pypi

   [pypi]
   username = __token__
   password = your-pypi-api-token
   EOF
   ```

#### Publishing Steps

1. **Clean previous builds**:
   ```bash
   rm -rf dist/ build/ *.egg-info/
   ```

2. **Build the package**:
   ```bash
   uv build
   ```

3. **Verify the package**:
   ```bash
   uv run twine check dist/*
   ```

4. **Upload to TestPyPI (recommended first)**:
   ```bash
   uv run twine upload --repository testpypi dist/*
   ```

5. **Test installation from TestPyPI**:
   ```bash
   pip install --index-url https://test.pypi.org/simple/ uv-cross-installer
   ```

6. **Upload to PyPI**:
   ```bash
   uv run twine upload dist/*
   ```

### Publishing with uv (Alternative Method)

uv provides a streamlined publishing workflow:

```bash
# Build and publish in one command
uv publish

# Or with explicit PyPI token
uv publish --token your-pypi-api-token
```

### GitHub Actions CI/CD

Create `.github/workflows/publish.yml` for automated publishing:

```yaml
name: Publish to PyPI

on:
  release:
    types: [published]

jobs:
  publish:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    
    - name: Install uv
      uses: astral-sh/setup-uv@v2
      with:
        version: "latest"
    
    - name: Set up Python
      run: uv python install 3.9
    
    - name: Build package
      run: uv build
    
    - name: Publish to PyPI
      run: uv publish
      env:
        UV_PUBLISH_TOKEN: ${{ secrets.PYPI_API_TOKEN }}
```

### Docker Deployment

Create a `Dockerfile` for containerized deployment:

```dockerfile
FROM python:3.9-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy project files
COPY . .

# Install dependencies
RUN uv sync --frozen

# Set entrypoint
ENTRYPOINT ["uv", "run", "uv-install"]
```

Build and run:
```bash
docker build -t uv-cross-installer .
docker run uv-cross-installer https://github.com/user/repo.git MyApp
```

## Project Structure

```
uv-cross-installer/
├── src/
│   └── uv-cross-installer/
│       └── __init__.py          # Main installer implementation
├── tests/
│   └── test_installer.py        # Test suite
├── pyproject.toml               # Project configuration
├── README.md                    # This file
└── LICENSE                      # MIT license
```

## Configuration

The installer behavior can be customized through:

- **Environment variables**: Set `UV_INSTALLER_LOG_LEVEL` for logging control
- **Configuration files**: Place `.uv-installer.json` in user home directory
- **Command line arguments**: Override defaults with CLI flags

## Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make changes and add tests
4. Run the test suite: `uv run pytest`
5. Format code: `uv run black .`
6. Submit a pull request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/codesapienbe/uv-cross-installer/issues)
- **Documentation**: [Project Wiki](https://github.com/codesapienbe/uv-cross-installer/wiki)
- **Discussions**: [GitHub Discussions](https://github.com/codesapienbe/uv-cross-installer/discussions)

