# AdGuard Rewrite Sync - Project Analysis Results

## Project Overview

**AdGuard Rewrite Sync** is a Kubernetes operator that automatically manages AdGuardHome DNS rewrite rules based on cluster resources. It's designed for homelab environments running k3s with MetalLB and Traefik.

### Core Functionality
- **DNS Rule Management**: Automatically creates/updates/deletes DNS rewrite rules in AdGuardHome
- **Kubernetes Integration**: Watches LoadBalancer services and Traefik ingress resources
- **Real-time Updates**: Responds immediately to cluster changes via Kubernetes watch API
- **Safe Operation**: Only manages rules it creates, never touches manual rules
- **State Persistence**: Maintains rule state across pod restarts using JSON database

### Target Environment
- **Kubernetes**: 1.20+ (tested with k3s)
- **AdGuardHome**: With API enabled
- **MetalLB**: For LoadBalancer services
- **Traefik**: Built-in k3s Traefik or external Traefik

## Project Structure

```
adguard-rewrite-sync/
├── app.py                    # Main application entry point
├── adguard_client.py         # AdGuardHome API client
├── k8s_client.py            # Kubernetes resource watcher
├── models.py                 # Data models (RewriteRule)
├── database.py               # Rule persistence with backup/restore
├── health.py                 # Health checking system
├── logger.py                 # Structured logging system
├── exceptions.py             # Custom exceptions
├── requirements.txt          # Python dependencies
├── Dockerfile               # Multi-stage container build
├── README.md                # Comprehensive documentation
├── CHANGELOG.md             # Version history
├── LICENSE                  # MIT License
├── CONTRIBUTING.md          # Contribution guidelines
└── examples/
    ├── docker-compose.yml   # Local development setup
    ├── env.example          # Environment variables template
    └── k8s/                 # Kubernetes deployment manifests
        ├── namespace.yaml
        ├── rbac.yaml
        ├── configmap.yaml
        ├── secret.yaml
        ├── pvc.yaml
        ├── deployment.yaml
        ├── service.yaml
        └── kustomization.yaml
```

## Application Lifecycle

### 1. Initialization Phase
```
app.py:main() → AdGuardDNSSync.__init__()
├── _setup_logging()           # Configure structured logging
├── _setup_kubernetes()       # Load k8s config (in-cluster or kubeconfig)
├── _setup_adguard()          # Initialize AdGuardHome client with auth
├── _setup_database()         # Initialize rule persistence
└── _setup_health_checker()   # Initialize health monitoring
```

### 2. Main Loop Phase
```
app.run()
├── start_health_server()      # HTTP server on port 8080 for health checks
├── sync_rules()              # Initial rule synchronization
├── start_periodic_sync()     # Background thread for periodic sync (30s default)
├── start_k8s_watcher()       # Background thread for real-time k8s events
└── Main thread loop          # Keep alive until shutdown signal
```

### 3. Shutdown Phase
```
app.shutdown()
├── shutdown_event.set()      # Signal all threads to stop
├── Wait for threads to finish (5s timeout)
└── Graceful shutdown complete
```

### 4. Core Operations Flow
```
Resource Change Detected
├── handle_resource_change()   # Log change event
├── _schedule_sync()          # Schedule delayed sync (5s batch delay)
└── sync_rules()              # Full rule synchronization
    ├── get_dns_resources()   # Discover k8s resources
    ├── generate_rules()      # Create RewriteRule objects
    ├── adguard.sync_rules()  # Sync with AdGuardHome API
    └── rule_db.save_managed_rules() # Persist state
```

## External Service Calls

### 1. AdGuardHome API
- **Authentication**: `POST /control/login`
- **Health Check**: `GET /control/status`
- **Get Rules**: `GET /control/rewrite/list`
- **Add Rule**: `POST /control/rewrite/add`
- **Update Rule**: `POST /control/rewrite/update`
- **Delete Rule**: `POST /control/rewrite/delete`

### 2. Kubernetes API
- **Services**: `GET /api/v1/services` (LoadBalancer type)
- **Ingress**: `GET /apis/networking.k8s.io/v1/ingresses`
- **Namespaces**: `GET /api/v1/namespaces`
- **Watch Services**: `WATCH /api/v1/services`
- **Watch Ingress**: `WATCH /apis/networking.k8s.io/v1/ingresses`

### 3. External Dependencies
- **Python Packages**: `kubernetes>=28.1.0`, `requests>=2.31.0`
- **Container Registry**: Custom registry (gitlab-registry-secret)
- **Storage**: Longhorn persistent volume (1Gi)
