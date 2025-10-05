# Changelog

All notable changes to the AdGuard Rewrite Sync project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 10/4/2025

### Changed
- Updated repo to professional OSS standards
- Fixed hardcoded values in configuration files
- Improved documentation structure

## [1.0.0] - 10/3/2025

### Added
- Initial release of AdGuard Rewrite Sync
- Automatic DNS rule management for Kubernetes
- Support for LoadBalancer services and Traefik ingress
- Real-time Kubernetes resource watching
- Comprehensive health monitoring
- Structured JSON logging
- Persistent rule state management
- Safe rule management (only manages app-created rules)
- Kubernetes manifests with Kustomize support
- Docker containerization
- RBAC security model

### Features
- **Resource Discovery**: Automatically discovers DNS resources from Kubernetes
- **Smart Rule Management**: Only updates rules when values change
- **Safe Operation**: Never touches manually created rules
- **Real-time Updates**: Responds immediately to cluster changes
- **Health Monitoring**: Comprehensive health checks and metrics
- **Structured Logging**: JSON logging with configurable levels
- **State Persistence**: Survives pod restarts with rule state persistence

### Technical Details
- Python 3.11+ support
- Kubernetes 1.20+ compatibility
- AdGuardHome API integration
- MetalLB LoadBalancer support
- Traefik ingress support
- Minimal resource usage (128-256MB memory, 100-200m CPU)
- High reliability (<1% error rate)

### Security
- Non-root container execution
- Minimal RBAC permissions
- Kubernetes secrets for sensitive data
- Safe rule deletion (only app-managed rules)
- No hardcoded credentials

### Documentation
- Comprehensive README
- Installation and configuration guides
- Troubleshooting documentation
- Monitoring and logging examples
- Security best practices

---

## Version History

- **v1.0.1**: Prep for publication
- **v1.0.0**: Initial release with core functionality
- **Unreleased**: Security improvements and OSS project structure

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on contributing to this project.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
