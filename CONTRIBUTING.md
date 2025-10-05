# Contributing to AdGuard Rewrite Sync

Thank you for your interest in contributing to AdGuard Rewrite Sync! This document provides guidelines and information for contributors.

## 🤝 How to Contribute

### Reporting Issues

Before creating an issue, please:
1. Check if the issue already exists
2. Search the documentation and discussions
3. Provide as much detail as possible

**Issue Template:**
- **Description**: Clear description of the problem
- **Steps to Reproduce**: Detailed steps to reproduce the issue
- **Expected Behavior**: What you expected to happen
- **Actual Behavior**: What actually happened
- **Environment**: Kubernetes version, AdGuardHome version, etc.
- **Logs**: Relevant log output

### Suggesting Features

We welcome feature suggestions! Please:
1. Check if the feature has been requested before
2. Provide a clear description of the feature
3. Explain the use case and benefits
4. Consider implementation complexity

### Pull Requests

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/your-feature-name`
3. **Make your changes**
4. **Add tests** for new functionality
5. **Update documentation** if needed
6. **Commit your changes**: `git commit -m "Add your feature"`
7. **Push to your fork**: `git push origin feature/your-feature-name`
8. **Create a Pull Request**

## 🛠️ Development Setup

### Prerequisites

- Python 3.11+
- Docker
- Kubernetes cluster (or minikube/kind)
- AdGuardHome instance

### Local Development

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/adguard-rewrite-sync.git
   cd adguard-rewrite-sync
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up environment variables:**
   ```bash
   export ADGUARD_URL="http://your-adguard:3000"
   export ADGUARD_USERNAME="your-username"
   export ADGUARD_PASSWORD="your-password"
   export LOG_LEVEL="DEBUG"
   ```

5. **Run the application:**
   ```bash
   python app.py
   ```

### Testing

```bash
# Run tests (when available)
python -m pytest tests/

# Run with coverage
python -m pytest --cov=app tests/
```

### Building Docker Image

```bash
# Build the image
docker build -t adguard-rewrite-sync:dev .

# Run the container
docker run --rm -e ADGUARD_URL="http://your-adguard:3000" \
  -e ADGUARD_USERNAME="your-username" \
  -e ADGUARD_PASSWORD="your-password" \
  adguard-rewrite-sync:dev
```

## 📝 Code Style Guidelines

### Python Code

- **Follow PEP 8**: Use `black` for formatting
- **Type hints**: Use type hints for function parameters and return values
- **Docstrings**: Add docstrings for all functions and classes
- **Imports**: Use absolute imports, group imports (stdlib, third-party, local)

**Example:**
```python
from typing import Dict, List, Optional
import logging

def sync_rules(self, target_rules: Dict[str, RewriteRule]) -> bool:
    """
    Sync rules to match target state.
    
    Args:
        target_rules: Dictionary of target rules to sync
        
    Returns:
        True if sync was successful, False otherwise
    """
    # Implementation here
    pass
```

### Documentation

- **README**: Keep the main README up to date
- **Code comments**: Explain complex logic
- **Docstrings**: Use Google-style docstrings
- **Examples**: Provide working examples

### Git Commit Messages

Use conventional commit format:

```
feat: add new feature
fix: fix bug
docs: update documentation
style: formatting changes
refactor: code refactoring
test: add tests
chore: maintenance tasks
```

**Examples:**
- `feat: add structured logging support`
- `fix: resolve rule deletion issue`
- `docs: update installation instructions`

## 🐛 Bug Reports

When reporting bugs, please include:

1. **Environment details**:
   - Kubernetes version
   - AdGuardHome version
   - Python version
   - Operating system

2. **Steps to reproduce**:
   - Clear, numbered steps
   - Expected vs actual behavior
   - Minimal reproduction case

3. **Logs and error messages**:
   - Full error messages
   - Relevant log output
   - Stack traces

4. **Additional context**:
   - Workarounds you've tried
   - Related issues
   - Impact on your use case

## 💡 Feature Requests

When suggesting features:

1. **Describe the problem** you're trying to solve
2. **Explain the proposed solution**
3. **Provide use cases** and examples
4. **Consider alternatives** you've explored
5. **Discuss implementation** if you have ideas

## 📞 Getting Help

- **GitHub Issues**: For bugs and feature requests
- **GitHub Discussions**: For questions and general discussion
- **Documentation**: Check the README and examples

## 🎯 Development Priorities

Current focus areas:

1. **Reliability**: Improve error handling and recovery
2. **Performance**: Optimize sync operations
3. **Monitoring**: Enhanced metrics and alerting
4. **Documentation**: Better examples and guides
5. **Testing**: Comprehensive test coverage

## 📄 License

By contributing to this project, you agree that your contributions will be licensed under the MIT License.

---

Thank you for contributing to AdGuard DNS Sync! 🚀
