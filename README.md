# AdGuard Rewrite Sync

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-1.20+-blue.svg)](https://kubernetes.io/)
[![Docker](https://img.shields.io/badge/docker-latest-blue.svg)](https://www.docker.com/)

A Kubernetes operator that automatically manages AdGuardHome rewrite rules based on your cluster's LoadBalancer services and Traefik ingress resources.

## 🚀 Features

- **Automatic Rewrite Management**: Automatically creates and manages rewrite rules in AdGuardHome
- **Kubernetes Integration**: Watches LoadBalancer services and Traefik ingress resources
- **Real-time Updates**: Responds immediately to cluster changes
- **Safe Operation**: Only manages rules it creates, never touches manual rules
- **Comprehensive Monitoring**: Built-in health checks and metrics
- **Structured Logging**: JSON logging with configurable levels
- **Persistent State**: Survives pod restarts with rule state persistence

## 📋 Prerequisites

- **Kubernetes**: 1.20+ (tested with k3s)
- **AdGuardHome**: With API enabled
- **MetalLB**: For LoadBalancer services (ServiceLB disabled)
- **Traefik**: Built-in k3s Traefik or external Traefik

## 🛠️ Installation

### Quick Start

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/adguard-rewrite-sync.git
   cd adguard-rewrite-sync
   ```

2. **Update configuration:**
   ```bash
   # Edit the ConfigMap
   kubectl edit configmap adguard-sync-config -n adguard-rewrite-sync
   
   # Update the secret with your AdGuardHome password
   kubectl edit secret adguard-sync-secret -n adguard-rewrite-sync
   ```

3. **Deploy to Kubernetes:**
   ```bash
   kubectl apply -k examples/k8s/
   ```

4. **Verify deployment:**
   ```bash
   kubectl get pods -n adguard-rewrite-sync
   kubectl logs -f deployment/adguard-sync -n adguard-rewrite-sync
   ```

### k3s Specific Setup

For k3s users with built-in Traefik and MetalLB:

1. **Disable ServiceLB** (if not already done):
   ```bash
   # Add to k3s server startup
   --disable servicelb
   ```

2. **Install MetalLB**:
   ```bash
   kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.13.12/config/manifests/metallb-native.yaml
   ```

3. **Configure MetalLB**:
   ```yaml
   apiVersion: metallb.io/v1beta1
   kind: IPAddressPool
   metadata:
     name: first-pool
     namespace: metallb-system
   spec:
     addresses:
     - 192.168.1.100-192.168.1.200
   ```

4. **Deploy AdGuard Rewrite Sync**:
   ```bash
   kubectl apply -k examples/k8s/
   ```

   **For detailed k3s setup, see**: [examples/k3s/README.md](examples/k3s/README.md)

### Configuration

#### AdGuardHome Connection
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ADGUARD_URL` | `http://adguard:3000` | AdGuardHome API URL |
| `ADGUARD_USERNAME` | `admin` | AdGuardHome username |
| `ADGUARD_PASSWORD` | *(required)* | AdGuardHome password |

#### AdGuardHome API Configuration
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `ADGUARD_MAX_RETRIES` | `3` | Maximum retry attempts for API calls |
| `ADGUARD_RETRY_DELAY` | `2` | Base delay between retries (seconds) |
| `ADGUARD_REQUEST_TIMEOUT` | `10` | HTTP request timeout (seconds) |
| `ADGUARD_SAFETY_THRESHOLD` | `0.8` | Safety threshold for rule deletion (0.1-1.0) |

#### Application Configuration
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `SYNC_INTERVAL` | `30` | Sync interval in seconds |
| `APP_CHANGE_WAIT_TIME` | `5` | Wait time for additional changes (seconds) |
| `APP_MAIN_LOOP_SLEEP` | `1` | Main loop sleep interval (seconds) |
| `APP_THREAD_JOIN_TIMEOUT` | `5` | Thread join timeout (seconds) |
| `APP_HEALTH_SERVER_PORT` | `8080` | Health check server port |

#### Database Configuration
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `DB_MAX_BACKUPS` | `5` | Maximum number of backup files to keep |
| `DB_LOCK_TIMEOUT` | `30.0` | Database lock acquisition timeout (seconds) |
| `DB_DEBUG_LOG_CHARS` | `500` | Maximum characters to show in debug logs |

#### Health Checker Configuration
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `HEALTH_CACHE_DURATION` | `30` | Health check cache duration (seconds) |
| `HEALTH_MAX_CONSECUTIVE_FAILURES` | `3` | Maximum consecutive failures before marking unhealthy |
| `HEALTH_CHECK_TIMEOUT` | `10` | Health check HTTP timeout (seconds) |

#### Kubernetes Client Configuration
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `K8S_WATCH_TIMEOUT` | `0` | Kubernetes API watch timeout (0 = no timeout) |

#### Logging Configuration
| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `LOG_LEVEL` | `INFO` | Logging level (DEBUG, INFO, WARNING, ERROR) |
| `JSON_LOGGING` | `false` | Enable structured JSON logging |

## 🔧 How It Works

### Resource Discovery
The operator automatically discovers DNS resources by:
- Scanning Kubernetes services with `type: LoadBalancer` (MetalLB)
- Identifying Traefik LoadBalancer IP addresses
- Discovering ingress resources with Traefik annotations
- Creating DNS mappings for discovered resources

### Rule Management
- **Smart Updates**: Only updates rules when values actually change
- **Safe Deletion**: Only deletes rules it previously created
- **Manual Rule Protection**: Never touches manually created rules
- **State Persistence**: Maintains rule state across pod restarts

### Real-time Monitoring
- **Health Checks**: Comprehensive health endpoint at `/health`
- **Metrics**: Built-in performance and error metrics
- **Logging**: Structured JSON logging with configurable levels
- **Alerting**: Automatic detection of issues and performance degradation

## 📊 Monitoring

### Health Endpoint

The application provides a comprehensive health endpoint:

```bash
kubectl port-forward deployment/adguard-sync 8080:8080 -n adguard-rewrite-sync
curl http://localhost:8080/health
```

**Example Response:**
```json
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "adguard_healthy": true,
  "k8s_healthy": true,
  "metrics": {
    "sync_operations": 45,
    "rules_created": 12,
    "rules_updated": 8,
    "rules_deleted": 2,
    "errors": 0,
    "uptime_seconds": 3600
  }
}
```

### Logging

The application supports both human-readable and structured JSON logging:

```bash
# Human-readable logs
kubectl logs deployment/adguard-sync -n adguard-rewrite-sync

# Structured JSON logs (when JSON_LOGGING=true)
kubectl logs deployment/adguard-sync -n adguard-rewrite-sync | jq '.'
```

## 🐛 Troubleshooting

### Common Issues

#### 1. DNS Rules Not Updating
```bash
# Check application logs
kubectl logs -f deployment/adguard-sync -n adguard-rewrite-sync

# Verify AdGuardHome connectivity
kubectl exec -it deployment/adguard-sync -n adguard-rewrite-sync -- \
  curl -s http://your-adguard:3000/control/status
```

#### 2. Health Check Failures
```bash
# Check health endpoint directly
kubectl port-forward deployment/adguard-sync 8080:8080 -n adguard-rewrite-sync
curl -v http://localhost:8080/health

# Check consecutive failures
kubectl logs deployment/adguard-sync -n adguard-rewrite-sync | grep "consecutive"
```

#### 3. Authentication Issues
```bash
# Verify credentials
kubectl get secret adguard-sync-secret -n adguard-rewrite-sync -o yaml

# Test authentication
kubectl exec -it deployment/adguard-sync -n adguard-rewrite-sync -- \
  python3 -c "from adguard_client import AdGuardHomeClientV2; print('Auth test')"
```

#### 4. k3s Specific Issues

**ServiceLB Conflict:**
```bash
# Check if ServiceLB is still running
kubectl get pods -n kube-system | grep servicelb

# If ServiceLB is running, disable it in k3s config
# Add to /etc/rancher/k3s/config.yaml:
# disable:
#   - servicelb
```

**MetalLB Not Working:**
```bash
# Check MetalLB status
kubectl get pods -n metallb-system
kubectl get ipaddresspools -n metallb-system

# Check LoadBalancer services
kubectl get svc --all-namespaces | grep LoadBalancer
```

**Traefik Integration:**
```bash
# Check Traefik is running
kubectl get pods -n kube-system | grep traefik

# Check Traefik LoadBalancer IP
kubectl get svc -n kube-system traefik
```

### Debug Commands

```bash
# Enable debug logging
kubectl patch configmap adguard-sync-config -n adguard-rewrite-sync --type merge -p '{"data":{"LOG_LEVEL":"DEBUG"}}'
kubectl rollout restart deployment/adguard-sync -n adguard-rewrite-sync

# Check metrics
kubectl port-forward deployment/adguard-sync 8080:8080 -n adguard-rewrite-sync
curl http://localhost:8080/health | jq '.metrics'

# View structured logs
kubectl logs deployment/adguard-sync -n adguard-rewrite-sync | jq '.'
```

## 🔒 Security

- **RBAC**: Minimal Kubernetes permissions (read-only access)
- **Non-root**: Runs as non-root user (UID 1000)
- **Secrets**: Sensitive data stored in Kubernetes secrets
- **Network**: Only outbound connections to AdGuardHome and Kubernetes API
- **Safe Operation**: Only manages rules it creates, never touches manual rules

## 📈 Performance

- **Memory**: 128-150MB typical usage
- **CPU**: 25-100m typical usage
- **Storage**: Minimal (rule database only)
- **Sync Duration**: Typically 1-3 seconds

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

### Development Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/your-username/adguard-rewrite-sync.git
   cd adguard-rewrite-sync
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run locally:**
   ```bash
   export ADGUARD_URL="http://your-adguard:3000"
   export ADGUARD_USERNAME="your-username"
   export ADGUARD_PASSWORD="your-password"
   python app.py
   ```

### Code Style

- Follow PEP 8 for Python code
- Use type hints where appropriate
- Add docstrings for all functions
- Include tests for new features

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [AdGuardHome](https://github.com/AdguardTeam/AdGuardHome) for the excellent DNS server
- [Kubernetes](https://kubernetes.io/) for the container orchestration platform
- [K3S](https://k3s.io/) for the lightweight kubernetes distrobution
- [Traefik](https://traefik.io/) for the ingress controller
- [MetalLB](https://metallb.universe.tf/) for the LoadBalancer implementation

## 📞 Support

- **Issues**: [GitHub Issues](https://github.com/your-username/adguard-rewrite-sync/issues)
- **Discussions**: [GitHub Discussions](https://github.com/your-username/adguard-rewrite-sync/discussions)
- **Documentation**: [Wiki](https://github.com/your-username/adguard-rewrite-sync/wiki)

---

**Made with ❤️ for the Kubernetes community**