# Multi-User Architecture for Jupyter MCP Server

## Overview

When deploying Jupyter MCP Server for multiple users, you need to consider isolation levels, resource management, and security requirements. This guide compares different architectural approaches.

## Isolation Levels Comparison

| Approach | Security Isolation | Resource Isolation | Complexity | Cost |
|----------|-------------------|-------------------|------------|------|
| **Separate Containers** | ⭐⭐⭐⭐⭐ Complete | ⭐⭐⭐⭐⭐ Complete | ⭐⭐⭐ Medium | ⭐⭐⭐⭐ High |
| **Shared + Redis** | ⭐⭐ Application-level | ⭐⭐ Shared resources | ⭐⭐ Medium | ⭐⭐ Low |
| **Namespace Separation** | ⭐⭐⭐⭐ Strong | ⭐⭐⭐ Good | ⭐⭐⭐⭐ High | ⭐⭐⭐ Medium |
| **Multi-tenant Service** | ⭐⭐⭐ Application-level | ⭐⭐ Shared resources | ⭐⭐⭐⭐⭐ Very High | ⭐⭐ Low |

## Approach 1: Separate Containers Per User (Your Original Idea)

### Architecture

```yaml
# docker-compose-multi-user.yml
version: '3.8'

services:
  # User 1 Stack
  user1-jupyter:
    image: jupyter/datascience-notebook:latest
    container_name: jupyter-user1
    ports:
      - "8881:8888"
    environment:
      - JUPYTER_TOKEN=user1-token-${RANDOM_SUFFIX}
    volumes:
      - ./notebooks/user1:/home/jovyan/work
      - user1_data:/home/jovyan
    networks:
      - user1-network

  user1-mcp:
    image: datalayer/jupyter-mcp-server:latest
    container_name: mcp-user1
    ports:
      - "4041:4040"
    environment:
      - ROOM_URL=http://user1-jupyter:8888
      - ROOM_TOKEN=user1-token-${RANDOM_SUFFIX}
      - ROOM_ID=notebook.ipynb
    depends_on:
      - user1-jupyter
    networks:
      - user1-network

  # User 2 Stack
  user2-jupyter:
    image: jupyter/datascience-notebook:latest
    container_name: jupyter-user2
    ports:
      - "8882:8888"
    environment:
      - JUPYTER_TOKEN=user2-token-${RANDOM_SUFFIX}
    volumes:
      - ./notebooks/user2:/home/jovyan/work
      - user2_data:/home/jovyan
    networks:
      - user2-network

  user2-mcp:
    image: datalayer/jupyter-mcp-server:latest
    container_name: mcp-user2
    ports:
      - "4042:4040"
    environment:
      - ROOM_URL=http://user2-jupyter:8888
      - ROOM_TOKEN=user2-token-${RANDOM_SUFFIX}
      - ROOM_ID=notebook.ipynb
    depends_on:
      - user2-jupyter
    networks:
      - user2-network

volumes:
  user1_data:
  user2_data:

networks:
  user1-network:
    driver: bridge
  user2-network:
    driver: bridge
```

### Pros ✅
- **Complete isolation**: Separate kernels, filesystems, network namespaces
- **Security**: Users cannot access each other's data or processes
- **Resource limits**: Can set CPU/memory limits per user
- **Independent scaling**: Each user stack scales independently
- **Fault isolation**: One user's issues don't affect others

### Cons ❌
- **Resource overhead**: Each user needs full stack (2 containers minimum)
- **Port management**: Need to manage unique ports for each user
- **Orchestration complexity**: Dynamic user creation is complex
- **Monitoring overhead**: More services to monitor and maintain

## Approach 2: Redis Session Management (Shared Services)

### What Redis Actually Provides

Redis in this context is **NOT** a replacement for container isolation. Instead, it provides:

```python
# Redis stores user session data, not isolation
{
    "user_sessions": {
        "user1": {
            "notebook_path": "/notebooks/user1/analysis.ipynb",
            "kernel_id": "kernel-abc123",
            "last_activity": "2024-01-15T10:30:00Z",
            "permissions": ["read", "write", "execute"]
        },
        "user2": {
            "notebook_path": "/notebooks/user2/research.ipynb", 
            "kernel_id": "kernel-def456",
            "last_activity": "2024-01-15T10:25:00Z",
            "permissions": ["read", "execute"]
        }
    }
}
```

### Implementation Example

```python
# Multi-user MCP server with Redis session management
import redis
import asyncio
from typing import Dict, Optional

class MultiUserMCPServer:
    def __init__(self):
        self.redis = redis.Redis(host='redis', port=6379, decode_responses=True)
        self.user_kernels: Dict[str, KernelClient] = {}
    
    async def get_user_session(self, user_id: str) -> Optional[dict]:
        """Get user session from Redis"""
        session_key = f"session:{user_id}"
        session_data = self.redis.hgetall(session_key)
        return session_data if session_data else None
    
    async def create_user_session(self, user_id: str, notebook_path: str) -> dict:
        """Create isolated user session"""
        # Create user-specific kernel
        kernel = KernelClient(
            server_url=f"http://jupyter:8888",
            token=self.get_jupyter_token(),
            kernel_id=None  # Will create new kernel
        )
        await kernel.start()
        
        # Store session in Redis
        session_data = {
            "notebook_path": notebook_path,
            "kernel_id": kernel.kernel_id,
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat()
        }
        
        session_key = f"session:{user_id}"
        self.redis.hset(session_key, mapping=session_data)
        self.redis.expire(session_key, 3600)  # 1 hour TTL
        
        self.user_kernels[user_id] = kernel
        return session_data
    
    @mcp.tool()
    async def execute_code_for_user(self, user_id: str, code: str) -> list[str]:
        """Execute code in user's isolated session"""
        session = await self.get_user_session(user_id)
        if not session:
            session = await self.create_user_session(user_id, f"/notebooks/{user_id}/default.ipynb")
        
        # Get user's kernel
        kernel = self.user_kernels.get(user_id)
        if not kernel:
            # Reconnect to existing kernel
            kernel = KernelClient(kernel_id=session["kernel_id"])
            self.user_kernels[user_id] = kernel
        
        # Execute in user's notebook context
        notebook = NbModelClient(
            get_notebook_websocket_url(
                server_url="http://jupyter:8888",
                token=self.get_jupyter_token(),
                path=session["notebook_path"]
            )
        )
        
        await notebook.start()
        try:
            cell_index = notebook.add_code_cell(code)
            notebook.execute_cell(cell_index, kernel)
            
            # Update last activity
            self.redis.hset(f"session:{user_id}", "last_activity", datetime.now().isoformat())
            
            outputs = notebook._doc._ycells[cell_index]["outputs"]
            return safe_extract_outputs(outputs)
        finally:
            await notebook.stop()
```

### Updated Docker Compose for Shared + Redis

```yaml
version: '3.8'

services:
  jupyter:
    image: jupyter/datascience-notebook:latest
    container_name: shared-jupyter
    ports:
      - "8888:8888"
    environment:
      - JUPYTER_TOKEN=${JUPYTER_TOKEN}
    volumes:
      - ./notebooks:/home/jovyan/work  # All user notebooks
      - jupyter_data:/home/jovyan
    networks:
      - shared-network

  redis:
    image: redis:7-alpine
    container_name: session-redis
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    networks:
      - shared-network

  multi-user-mcp:
    build: .  # Custom image with multi-user support
    container_name: multi-user-mcp
    ports:
      - "4040:4040"
    environment:
      - REDIS_URL=redis://redis:6379
      - JUPYTER_URL=http://jupyter:8888
      - JUPYTER_TOKEN=${JUPYTER_TOKEN}
    depends_on:
      - jupyter
      - redis
    networks:
      - shared-network

  auth-proxy:
    image: oauth2-proxy/oauth2-proxy:latest
    container_name: auth-proxy
    ports:
      - "4180:4180"
    environment:
      - OAUTH2_PROXY_PROVIDER=github
      - OAUTH2_PROXY_CLIENT_ID=${GITHUB_CLIENT_ID}
      - OAUTH2_PROXY_CLIENT_SECRET=${GITHUB_CLIENT_SECRET}
      - OAUTH2_PROXY_UPSTREAM=http://multi-user-mcp:4040
    depends_on:
      - multi-user-mcp
    networks:
      - shared-network

volumes:
  jupyter_data:
  redis_data:

networks:
  shared-network:
```

### Pros ✅
- **Resource efficient**: Single Jupyter server for all users
- **Simpler orchestration**: Fewer containers to manage
- **Session persistence**: User sessions survive container restarts
- **Centralized logging**: Easier to monitor and debug

### Cons ❌
- **Limited isolation**: Users share the same Jupyter server process
- **Security risks**: Potential for cross-user data access if misconfigured
- **Resource contention**: Users compete for CPU/memory
- **Kernel conflicts**: Shared kernel namespace could cause issues

## Approach 3: Kubernetes Namespace Separation (Recommended for Scale)

### Architecture

```yaml
# User namespace template
apiVersion: v1
kind: Namespace
metadata:
  name: user-${USER_ID}
  labels:
    purpose: jupyter-mcp
    user: ${USER_ID}
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: jupyter-mcp-stack
  namespace: user-${USER_ID}
spec:
  replicas: 1
  selector:
    matchLabels:
      app: jupyter-mcp
  template:
    metadata:
      labels:
        app: jupyter-mcp
    spec:
      containers:
      - name: jupyter
        image: jupyter/datascience-notebook:latest
        ports:
        - containerPort: 8888
        env:
        - name: JUPYTER_TOKEN
          valueFrom:
            secretKeyRef:
              name: user-secrets
              key: jupyter-token
        volumeMounts:
        - name: user-notebooks
          mountPath: /home/jovyan/work
        resources:
          requests:
            memory: "512Mi"
            cpu: "250m"
          limits:
            memory: "2Gi"
            cpu: "1000m"
      
      - name: mcp-server
        image: datalayer/jupyter-mcp-server:latest
        ports:
        - containerPort: 4040
        env:
        - name: ROOM_URL
          value: "http://localhost:8888"
        - name: JUPYTER_TOKEN
          valueFrom:
            secretKeyRef:
              name: user-secrets
              key: jupyter-token
      
      volumes:
      - name: user-notebooks
        persistentVolumeClaim:
          claimName: user-${USER_ID}-notebooks
---
# Network policies for isolation
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: user-isolation
  namespace: user-${USER_ID}
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: ingress-system
  egress:
  - to: []
    ports:
    - protocol: TCP
      port: 80
    - protocol: TCP
      port: 443
```

### User Management Service

```python
# Kubernetes user management
from kubernetes import client, config
import asyncio

class KubernetesUserManager:
    def __init__(self):
        config.load_incluster_config()  # or load_kube_config() for local
        self.v1 = client.CoreV1Api()
        self.apps_v1 = client.AppsV1Api()
    
    async def create_user_environment(self, user_id: str) -> dict:
        """Create isolated user environment in Kubernetes"""
        namespace_name = f"user-{user_id}"
        
        # Create namespace
        namespace = client.V1Namespace(
            metadata=client.V1ObjectMeta(
                name=namespace_name,
                labels={"purpose": "jupyter-mcp", "user": user_id}
            )
        )
        self.v1.create_namespace(namespace)
        
        # Create user secrets
        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name="user-secrets", namespace=namespace_name),
            data={"jupyter-token": base64.b64encode(f"token-{user_id}".encode()).decode()}
        )
        self.v1.create_namespaced_secret(namespace_name, secret)
        
        # Deploy user stack (jupyter + mcp)
        # ... deployment creation code ...
        
        return {
            "user_id": user_id,
            "namespace": namespace_name,
            "jupyter_url": f"https://jupyter-{user_id}.your-domain.com",
            "mcp_url": f"https://mcp-{user_id}.your-domain.com"
        }
    
    async def delete_user_environment(self, user_id: str):
        """Clean up user environment"""
        namespace_name = f"user-{user_id}"
        self.v1.delete_namespace(namespace_name)
```

## Approach 4: Dynamic Container Orchestration

### Docker Compose Template Generator

```python
# Dynamic container orchestration
import docker
import yaml
from pathlib import Path

class DynamicUserManager:
    def __init__(self):
        self.docker_client = docker.from_env()
        self.base_port = 8000
        self.users = {}
    
    def create_user_stack(self, user_id: str) -> dict:
        """Create dedicated container stack for user"""
        user_port_jupyter = self.base_port + (len(self.users) * 2)
        user_port_mcp = user_port_jupyter + 1
        
        # Create user directories
        user_dir = Path(f"./users/{user_id}")
        user_dir.mkdir(parents=True, exist_ok=True)
        (user_dir / "notebooks").mkdir(exist_ok=True)
        
        # Generate docker-compose for user
        compose_config = {
            "version": "3.8",
            "services": {
                f"{user_id}-jupyter": {
                    "image": "jupyter/datascience-notebook:latest",
                    "container_name": f"jupyter-{user_id}",
                    "ports": [f"{user_port_jupyter}:8888"],
                    "environment": [f"JUPYTER_TOKEN=token-{user_id}"],
                    "volumes": [
                        f"./users/{user_id}/notebooks:/home/jovyan/work",
                        f"{user_id}_data:/home/jovyan"
                    ],
                    "networks": [f"{user_id}-network"]
                },
                f"{user_id}-mcp": {
                    "image": "datalayer/jupyter-mcp-server:latest",
                    "container_name": f"mcp-{user_id}",
                    "ports": [f"{user_port_mcp}:4040"],
                    "environment": [
                        f"ROOM_URL=http://{user_id}-jupyter:8888",
                        f"ROOM_TOKEN=token-{user_id}",
                        "ROOM_ID=notebook.ipynb"
                    ],
                    "depends_on": [f"{user_id}-jupyter"],
                    "networks": [f"{user_id}-network"]
                }
            },
            "volumes": {f"{user_id}_data": None},
            "networks": {f"{user_id}-network": {"driver": "bridge"}}
        }
        
        # Write compose file
        compose_file = user_dir / "docker-compose.yml"
        with open(compose_file, 'w') as f:
            yaml.dump(compose_config, f)
        
        # Start stack
        import subprocess
        subprocess.run(["docker-compose", "-f", str(compose_file), "up", "-d"])
        
        self.users[user_id] = {
            "jupyter_port": user_port_jupyter,
            "mcp_port": user_port_mcp,
            "compose_file": str(compose_file)
        }
        
        return self.users[user_id]
    
    def delete_user_stack(self, user_id: str):
        """Remove user's container stack"""
        if user_id in self.users:
            compose_file = self.users[user_id]["compose_file"]
            subprocess.run(["docker-compose", "-f", compose_file, "down", "-v"])
            del self.users[user_id]
```

## Recommendations

### For Small Scale (< 10 users)
**Use separate containers per user** - Your original idea is actually the best approach:
- Simple to implement and understand
- Perfect security isolation
- Easy to manage with Docker Compose
- Predictable resource usage

### For Medium Scale (10-100 users)
**Use Kubernetes with namespace separation**:
- Better resource management
- Automated scaling and recovery
- Strong isolation with network policies
- Professional orchestration

### For Large Scale (100+ users)
**Build multi-tenant service with Redis**:
- Custom authentication and authorization
- Shared resource pools
- Advanced session management
- Cost-effective at scale

## Security Considerations

| Concern | Separate Containers | Shared + Redis | K8s Namespaces |
|---------|-------------------|----------------|-----------------|
| **Data isolation** | ✅ Complete | ⚠️ App-level | ✅ Strong |
| **Process isolation** | ✅ Complete | ❌ Shared | ✅ Complete |
| **Network isolation** | ✅ Complete | ❌ Shared | ✅ Strong |
| **Resource limits** | ✅ Per-user | ⚠️ Global | ✅ Per-user |
| **Audit trail** | ✅ Per-user logs | ⚠️ Mixed logs | ✅ Per-user logs |

## Conclusion

**Your original idea of separate containers per user is actually the most secure and straightforward approach for most use cases.** Redis session management is a complementary technology for coordination, not a replacement for isolation.

Consider separate containers when:
- Security is paramount
- Users have different resource needs
- You need predictable performance
- Compliance requires strict isolation

Consider shared services + Redis when:
- Cost is the primary concern
- Users have similar, light workloads
- You have strong application-level security
- You need rapid user onboarding 