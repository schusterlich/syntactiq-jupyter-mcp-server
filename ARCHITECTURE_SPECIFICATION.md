# Multi-User Jupyter MCP Platform - Architecture Specification

## Executive Summary

A containerized, multi-tenant Jupyter notebook platform that provides isolated Python environments for users within a web-based chat/application platform. Each user receives a dedicated container with their own Jupyter instance and MCP server, accessible only through the main platform via secure iframe integration.

## System Overview

### Core Principles
- **One container per user maximum** - complete resource and security isolation
- **Multiple notebooks per user** - within their single container environment  
- **Zero cross-user interaction** - no sharing or collaboration features
- **Platform-only access** - Jupyter instances not directly accessible externally
- **Resource-bounded** - fixed RAM limits with system-wide capacity management
- **On-demand provisioning** - containers created when users first access platform

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Web Platform (Frontend)                      │
│  ┌─────────────────┐                    ┌─────────────────────┐ │
│  │   Chat/App UI   │                    │   Jupyter iFrame    │ │
│  │                 │◄──────────────────►│   (user-specific)   │ │
│  └─────────────────┘                    └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                   Platform Backend API                          │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │   Auth Layer    │  │ Container Mgmt  │  │ Resource Monitor │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              Container Orchestration Layer                      │
│                                                                 │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐ │
│  │  Nginx Reverse  │  │  Session Store  │  │   Warm Pool     │ │
│  │     Proxy       │  │   (SQLite/Redis)│  │   Manager       │ │
│  └─────────────────┘  └─────────────────┘  └─────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                    User Container Layer                         │
│                                                                 │
│ ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────────┐ │
│ │   User A        │ │   User B        │ │   User C            │ │
│ │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────────┐ │ │
│ │ │ JupyterLab  │ │ │ │ JupyterLab  │ │ │ │ JupyterLab      │ │ │
│ │ │ :8888       │ │ │ │ :8888       │ │ │ │ :8888           │ │ │
│ │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────────┘ │ │
│ │ ┌─────────────┐ │ │ ┌─────────────┐ │ │ ┌─────────────────┐ │ │
│ │ │ MCP Server  │ │ │ │ MCP Server  │ │ │ │ MCP Server      │ │ │
│ │ │ :4040       │ │ │ │ :4040       │ │ │ │ :4040           │ │ │
│ │ └─────────────┘ │ │ └─────────────┘ │ │ └─────────────────┘ │ │
│ │ Port: 8001-8002 │ │ Port: 8003-8004 │ │ Port: 8005-8006     │ │
│ └─────────────────┘ └─────────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## Component Architecture

### 1. Container Management Service

**Responsibilities:**
- Container lifecycle management (create, start, stop, destroy)
- Port allocation and deallocation
- Template-based container provisioning
- Resource monitoring and enforcement
- Idle timeout management

**Key Features:**
```python
class ContainerManager:
    def create_user_container(user_id: str, template: str) -> ContainerInfo
    def get_user_container(user_id: str) -> Optional[ContainerInfo]
    def destroy_idle_containers() -> List[str]
    def check_system_resources() -> ResourceStatus
    def allocate_ports() -> PortPair
    def warm_pool_maintenance() -> None
```

### 2. Session Management

**SQLite vs Redis Comparison:**

| Feature | SQLite | Redis |
|---------|--------|-------|
| **Persistence** | ✅ Durable to disk | ⚠️ Optional persistence |
| **Concurrency** | ⚠️ Limited writers | ✅ High concurrency |
| **Expiration** | ❌ Manual cleanup | ✅ Built-in TTL |
| **Atomic Operations** | ✅ ACID transactions | ✅ Atomic commands |
| **Memory Usage** | ✅ Disk-based | ⚠️ RAM-based |
| **Setup Complexity** | ✅ Zero config | ⚠️ Additional service |
| **Performance** | ✅ Fast for reads | ✅ Faster for frequent updates |

**Recommendation: Start with SQLite, migrate to Redis if needed**

**Session Schema:**
```sql
-- SQLite Schema
CREATE TABLE user_sessions (
    user_id TEXT PRIMARY KEY,
    container_id TEXT NOT NULL,
    jupyter_port INTEGER NOT NULL,
    mcp_port INTEGER NOT NULL,
    template_type TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_activity TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'active' -- active, idle, stopping
);

CREATE TABLE container_templates (
    template_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT,
    docker_image TEXT NOT NULL,
    environment_vars JSON,
    volume_mounts JSON,
    resource_limits JSON
);

CREATE TABLE system_resources (
    id INTEGER PRIMARY KEY,
    total_memory_mb INTEGER NOT NULL,
    used_memory_mb INTEGER NOT NULL,
    container_count INTEGER NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 3. Resource Management

**System Configuration:**
```yaml
resource_limits:
  per_container:
    memory: "2GB"      # Fixed RAM per container
    cpu: "1.0"         # 1 CPU core max
    disk: "10GB"       # Notebook storage limit
  
  system_wide:
    max_containers: 50           # Total concurrent containers
    memory_reserve: "4GB"        # Keep free for system
    warm_pool_size: 3           # Pre-warmed containers
    idle_timeout_minutes: 30    # Auto-shutdown timer
```

**Resource Monitoring Logic:**
```python
def can_create_container() -> bool:
    current_memory = get_used_memory()
    reserved_memory = config.MEMORY_RESERVE
    container_memory = config.PER_CONTAINER_MEMORY
    total_memory = get_total_memory()
    
    available = total_memory - current_memory - reserved_memory
    return available >= container_memory

def get_resource_status() -> ResourceStatus:
    return ResourceStatus(
        can_create_container=can_create_container(),
        containers_running=count_active_containers(),
        memory_usage_percent=(get_used_memory() / get_total_memory()) * 100,
        containers_remaining=calculate_max_new_containers()
    )
```

### 4. Port Management

**Dynamic Port Allocation:**
```python
class PortManager:
    def __init__(self):
        self.port_range = range(8000, 9000)  # Available ports
        self.allocated_ports = set()
    
    def allocate_port_pair(self) -> Tuple[int, int]:
        """Allocate consecutive ports for Jupyter and MCP"""
        for port in self.port_range:
            if port not in self.allocated_ports and (port + 1) not in self.allocated_ports:
                jupyter_port = port
                mcp_port = port + 1
                self.allocated_ports.update([jupyter_port, mcp_port])
                return jupyter_port, mcp_port
        raise PortExhaustionError("No available port pairs")
    
    def release_ports(self, jupyter_port: int, mcp_port: int):
        self.allocated_ports.discard(jupyter_port)
        self.allocated_ports.discard(mcp_port)
```

### 5. Container Templates

**Template Configuration:**
```yaml
templates:
  basic_python:
    name: "Python Data Science"
    image: "jupyter/datascience-notebook:latest"
    description: "Standard Python with pandas, numpy, matplotlib"
    environment:
      - JUPYTER_ENABLE_LAB=yes
    volumes:
      - type: bind
        source: "./data/users/{user_id}/notebooks"
        target: "/home/jovyan/work"
    resources:
      memory: "2GB"
      cpu: "1.0"
  
  database_analyst:
    name: "Database Analyst"
    image: "custom/jupyter-db:latest"
    description: "Python + PostgreSQL, MySQL connectors"
    environment:
      - JUPYTER_ENABLE_LAB=yes
      - DB_HOST=${DB_HOST}
      - DB_CREDENTIALS_PATH=/app/db-creds
    volumes:
      - type: bind
        source: "./data/users/{user_id}/notebooks"
        target: "/home/jovyan/work"
      - type: bind
        source: "./db-credentials"
        target: "/app/db-creds"
        read_only: true
    resources:
      memory: "2GB"
      cpu: "1.0"
  
  ml_engineer:
    name: "Machine Learning"
    image: "tensorflow/tensorflow:latest-jupyter"
    description: "TensorFlow, PyTorch, scikit-learn"
    environment:
      - JUPYTER_ENABLE_LAB=yes
    volumes:
      - type: bind
        source: "./data/users/{user_id}/notebooks"
        target: "/home/jovyan/work"
      - type: bind
        source: "./data/shared/datasets"
        target: "/datasets"
        read_only: true
    resources:
      memory: "4GB"  # More memory for ML workloads
      cpu: "2.0"
```

### 6. Warm Pool Management

**Pre-warmed Container Strategy:**
```python
class WarmPoolManager:
    def __init__(self, pool_size: int = 3):
        self.pool_size = pool_size
        self.warm_containers = {}  # template -> [container_ids]
    
    def maintain_warm_pool(self):
        """Ensure we have warm containers for each template"""
        for template in get_active_templates():
            current_count = len(self.warm_containers.get(template, []))
            needed = self.pool_size - current_count
            
            for _ in range(needed):
                if can_create_container():
                    container = self.create_warm_container(template)
                    self.warm_containers.setdefault(template, []).append(container)
    
    def assign_warm_container(self, user_id: str, template: str) -> Optional[str]:
        """Assign a pre-warmed container to user"""
        if template in self.warm_containers and self.warm_containers[template]:
            container_id = self.warm_containers[template].pop(0)
            self.configure_for_user(container_id, user_id)
            return container_id
        return None
```

## Security Model

### 1. Network Isolation

**Container Network Design:**
```yaml
# Each user gets isolated network
networks:
  user-{user_id}-network:
    driver: bridge
    internal: true  # No external internet access by default
    ipam:
      config:
        - subnet: 172.20.{user_id}.0/24
```

### 2. Reverse Proxy Configuration

**Nginx Route Management:**
```nginx
# Dynamic user routing
location ~ ^/user/([a-zA-Z0-9]+)/jupyter/ {
    set $user_id $1;
    
    # Verify user session
    auth_request /auth/verify;
    auth_request_set $container_port $upstream_http_container_port;
    
    # Rate limiting per user
    limit_req zone=user_jupyter:$user_id burst=10 nodelay;
    
    # Proxy to user's container
    proxy_pass http://127.0.0.1:$container_port/;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-User-ID $user_id;
    
    # WebSocket support
    proxy_http_version 1.1;
    proxy_set_header Upgrade $http_upgrade;
    proxy_set_header Connection "upgrade";
}

location ~ ^/user/([a-zA-Z0-9]+)/mcp/ {
    set $user_id $1;
    auth_request /auth/verify;
    auth_request_set $mcp_port $upstream_http_mcp_port;
    
    proxy_pass http://127.0.0.1:$mcp_port/;
    # ... similar configuration
}
```

### 3. Authentication Flow

```python
def verify_user_access(user_id: str, session_token: str) -> bool:
    """Verify user can access their container"""
    # 1. Validate session token
    if not validate_session_token(session_token):
        return False
    
    # 2. Check token belongs to user
    token_user = get_user_from_token(session_token)
    if token_user != user_id:
        return False
    
    # 3. Verify container exists and belongs to user
    container = get_user_container(user_id)
    if not container or container.status != 'running':
        return False
    
    # 4. Update last activity
    update_last_activity(user_id)
    return True
```

## API Design

### Core Endpoints

```python
# Container Management API
POST   /api/users/{user_id}/container
GET    /api/users/{user_id}/container/status
DELETE /api/users/{user_id}/container
GET    /api/users/{user_id}/container/logs

# Template Management
GET    /api/templates
POST   /api/users/{user_id}/container/template/{template_id}

# System Monitoring
GET    /api/system/resources
GET    /api/system/containers
GET    /api/admin/warm-pool/status

# Iframe Access URLs
GET    /user/{user_id}/jupyter/   # Returns iframe-safe Jupyter URL
GET    /user/{user_id}/mcp/       # Returns MCP server URL
```

### Container Creation Flow

```python
async def create_user_container(user_id: str, template: str) -> ContainerResponse:
    # 1. Check if user already has container
    existing = get_user_container(user_id)
    if existing:
        return ContainerResponse(error="User already has active container")
    
    # 2. Check system resources
    if not can_create_container():
        return ContainerResponse(error="System at capacity")
    
    # 3. Try to assign warm container first
    container_id = warm_pool.assign_warm_container(user_id, template)
    
    # 4. If no warm container, create new one
    if not container_id:
        container_id = await create_container_from_template(user_id, template)
    
    # 5. Allocate ports
    jupyter_port, mcp_port = port_manager.allocate_port_pair()
    
    # 6. Configure container
    await configure_container(container_id, jupyter_port, mcp_port, user_id)
    
    # 7. Start container
    await start_container(container_id)
    
    # 8. Store session
    store_user_session(UserSession(
        user_id=user_id,
        container_id=container_id,
        jupyter_port=jupyter_port,
        mcp_port=mcp_port,
        template=template,
        status='active'
    ))
    
    # 9. Schedule idle timeout
    schedule_idle_check(user_id, timeout_minutes=30)
    
    return ContainerResponse(
        jupyter_url=f"/user/{user_id}/jupyter/",
        mcp_url=f"/user/{user_id}/mcp/",
        status="running"
    )
```

## Data Storage Strategy

### File System Layout
```
data/
├── users/
│   ├── {user_id}/
│   │   ├── notebooks/           # User's Jupyter notebooks
│   │   │   ├── project-1/
│   │   │   ├── project-2/
│   │   │   └── shared/
│   │   ├── data/               # User's data files
│   │   └── config/             # User preferences
│   └── {user_id}/
├── templates/
│   ├── basic_python/
│   ├── database_analyst/
│   └── ml_engineer/
├── system/
│   ├── logs/
│   ├── backups/
│   └── session.db              # SQLite session store
└── warm-pool/
    └── ready-containers/
```

### Backup Strategy
```python
def backup_user_data(user_id: str):
    """Backup user notebooks and data"""
    user_path = f"data/users/{user_id}"
    backup_path = f"data/system/backups/{user_id}/{datetime.now().isoformat()}"
    
    # Create compressed backup
    shutil.make_archive(backup_path, 'gztar', user_path)
    
    # Retain last 7 backups
    cleanup_old_backups(user_id, keep=7)
```

## Deployment Strategy

### Docker Compose Structure
```yaml
# Main platform services
version: '3.8'
services:
  platform-backend:
    build: ./backend
    ports: ["3000:3000"]
    volumes:
      - ./data:/app/data
      - /var/run/docker.sock:/var/run/docker.sock
    environment:
      - SESSION_DB_PATH=/app/data/system/session.db
      - CONTAINER_DATA_PATH=/app/data
  
  nginx-proxy:
    image: nginx:alpine
    ports: ["80:80", "443:443"]
    volumes:
      - ./nginx-templates:/etc/nginx/templates
      - ./data/system/logs:/var/log/nginx
    depends_on: [platform-backend]
  
  # User containers are created dynamically
  # No need to define them in this compose file
```

### System Requirements

**Minimum Server Specs:**
- **RAM**: 16GB (supports ~6 concurrent 2GB containers + system overhead)
- **CPU**: 8 cores (1 core per container + system processes)
- **Storage**: 500GB SSD (notebooks, backups, container images)
- **Network**: 1Gbps (for container communication and user downloads)

**Recommended Production Specs:**
- **RAM**: 64GB (supports ~25 concurrent containers)
- **CPU**: 16 cores 
- **Storage**: 2TB NVMe SSD
- **Network**: 10Gbps

## Monitoring & Alerting

### Key Metrics
```python
metrics = {
    "containers_active": count_active_containers(),
    "containers_idle": count_idle_containers(),
    "memory_usage_percent": get_memory_usage_percent(),
    "disk_usage_percent": get_disk_usage_percent(),
    "warm_pool_size": get_warm_pool_size(),
    "average_container_age": get_average_container_age(),
    "failed_container_starts": get_failed_starts_last_hour()
}
```

### Alert Conditions
- **Memory usage > 80%**: Stop creating new containers
- **Memory usage > 90%**: Force cleanup of idle containers
- **Disk usage > 85%**: Trigger backup cleanup
- **Container start failures > 5/hour**: System health alert
- **Warm pool < 1**: Performance degradation warning

## Implementation Phases

### Phase 1: Core Infrastructure (Week 1-2)
- Container management service
- Port allocation system
- SQLite session storage
- Basic nginx proxy configuration
- Single template support

### Phase 2: Resource Management (Week 3)
- Memory monitoring and limits
- Idle timeout implementation
- Resource-based container creation limits
- Basic logging and metrics

### Phase 3: Advanced Features (Week 4-5)
- Multiple template support
- Warm pool management
- Enhanced security (CSP, rate limiting)
- Backup system
- Admin monitoring dashboard

### Phase 4: Production Hardening (Week 6)
- Comprehensive error handling
- Performance optimization
- Security audit and testing
- Load testing with multiple concurrent users
- Documentation and deployment guides

## Risk Mitigation

### Technical Risks
- **Port exhaustion**: Implement port recycling and monitoring
- **Memory leaks**: Regular container cleanup and monitoring
- **Storage growth**: Automated backup rotation and user quotas
- **Container startup failures**: Retry logic and warm pool fallback

### Security Risks
- **Container escape**: Use unprivileged containers, security scanning
- **Resource exhaustion attacks**: Rate limiting, user quotas
- **Data exposure**: Network isolation, access logging
- **Session hijacking**: Secure token management, session validation

### Operational Risks
- **System overload**: Graceful degradation, queue management
- **Data loss**: Regular backups, container persistence
- **Service availability**: Health checks, automatic recovery
- **Scaling bottlenecks**: Horizontal scaling preparation

This architecture provides a robust foundation for your multi-user Jupyter platform while maintaining simplicity and strong security isolation. 