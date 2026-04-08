# Node Pool Balancing Plan (ZeroQwait)

This plan keeps voice workloads responsive while protecting API/data stability.

## Target node pools

- `voice-gpu`: TTS + ASR (latency sensitive, bursty GPU usage)
- `llm-gpu`: Ollama (large, sustained GPU + RAM pressure)
- `core-cpu`: backend + voice-mcp (request path services)
- `edge-cpu`: frontend and ingress edge traffic
- `data-cpu`: postgres + redis (steady I/O + memory)

## Recommended labels

Apply to nodes in each pool:

```bash
kubectl label node <node-name> zeroqwait.io/node-pool=voice-gpu
kubectl label node <node-name> zeroqwait.io/node-pool=llm-gpu
kubectl label node <node-name> zeroqwait.io/node-pool=core-cpu
kubectl label node <node-name> zeroqwait.io/node-pool=edge-cpu
kubectl label node <node-name> zeroqwait.io/node-pool=data-cpu
```

## Recommended taints

Use taints to enforce pool isolation (pods already include matching tolerations):

```bash
kubectl taint node <voice-gpu-node> workload-pool=voice-gpu:NoSchedule
kubectl taint node <llm-gpu-node> workload-pool=llm-gpu:NoSchedule
kubectl taint node <core-cpu-node> workload-pool=core-cpu:NoSchedule
kubectl taint node <edge-cpu-node> workload-pool=edge-cpu:NoSchedule
kubectl taint node <data-cpu-node> workload-pool=data-cpu:NoSchedule
```

## Why this balance works

- Voice path gets highest scheduling priority (`voice-critical`) and avoids sharing a host with Ollama when possible.
- Ollama gets dedicated preference and high priority (`llm-critical`) to reduce model eviction and cold starts.
- Backend/voice-mcp/data services get `app-critical` to preserve API reliability under pressure.
- Frontend runs as `app-standard` so user traffic remains served without starving critical backends.

## Capacity guidance (starting point)

- `voice-gpu`: 1 GPU node (or 2 for high availability)
- `llm-gpu`: 1 GPU node dedicated to LLM inference
- `core-cpu`: 2 CPU nodes (N+1 for backend and gateway)
- `edge-cpu`: 1 to 2 CPU nodes based on ingress traffic
- `data-cpu`: 1 CPU node minimum, 2 for failover planning

## Rollout

1. Apply priority classes and updated manifests.
2. Label nodes.
3. Add taints one pool at a time.
4. Verify placement:

```bash
kubectl get pods -n zeroqwait -o wide
kubectl get pods -n llm -o wide
kubectl describe pod <pod> -n <ns> | grep -A5 -E "Node-Selectors|Tolerations|Priority Class"
```

5. Watch latency and queue health before tainting the next pool.
