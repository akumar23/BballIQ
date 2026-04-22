# Sealed Secrets for Kubernetes

This guide explains how to use Sealed Secrets to securely manage credentials in your Kubernetes deployment without committing them to git.

## What is Sealed Secrets?

Sealed Secrets is a Kubernetes controller that encrypts secrets using a cluster-specific keypair. Only your cluster can decrypt them, making them safe to commit to git.

**Key benefits:**
- Secrets are encrypted at rest in git
- Cluster-specific encryption (can't be moved between clusters)
- GitOps-friendly workflow
- No external secret manager required

## Setup (One-Time)

### 1. Install the Sealed Secrets Controller

```bash
kubectl apply -f https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.27.1/controller.yaml
kubectl wait --for=condition=Ready pod -l app.kubernetes.io/name=sealed-secrets -n kube-system --timeout=300s
```

Verify installation:
```bash
kubectl get deployment sealed-secrets-controller -n kube-system
```

### 2. Install the kubeseal CLI Tool

**macOS:**
```bash
brew install kubeseal
```

**Linux:**
```bash
wget https://github.com/bitnami-labs/sealed-secrets/releases/download/v0.27.1/kubeseal-0.27.1-linux-amd64.tar.gz
tar xfz kubeseal-0.27.1-linux-amd64.tar.gz
sudo install -m 755 kubeseal /usr/local/bin/kubeseal
```

**Windows:**
Download from: https://github.com/bitnami-labs/sealed-secrets/releases

## Usage Workflow

### Step 1: Create a Local Secret (Never commit this)

Create a temporary `secrets.yaml` file locally with your real credentials:

```bash
cat > /tmp/secrets.yaml << 'EOF'
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: nba-stats
type: Opaque
stringData:
  POSTGRES_USER: your_actual_username
  POSTGRES_PASSWORD: your_actual_password
  POSTGRES_DB: nba_stats
  DATABASE_URL: postgresql://username:password@postgres:5432/nba_stats
---
apiVersion: v1
kind: Secret
metadata:
  name: redis-credentials
  namespace: nba-stats
type: Opaque
stringData:
  REDIS_URL: redis://redis:6379/0
  CELERY_BROKER_URL: redis://redis:6379/1
  CELERY_RESULT_BACKEND: redis://redis:6379/2
EOF
```

**IMPORTANT:** Do NOT commit `/tmp/secrets.yaml` to git.

### Step 2: Seal the Secret

Encrypt the secret using the cluster's public key:

```bash
kubeseal < /tmp/secrets.yaml > /tmp/sealed-secrets.yaml
```

### Step 3: Commit the Sealed Secret

The sealed secrets are now safe to commit to git:

```bash
cp /tmp/sealed-secrets.yaml k8s/sealed-secrets.yaml
git add k8s/sealed-secrets.yaml
git commit -m "Add sealed secrets for production deployment"
```

### Step 4: Apply to Cluster

```bash
kubectl apply -f k8s/sealed-secrets.yaml
```

The sealed-secrets controller will automatically decrypt and create the real Secret objects.

### Step 5: Verify

```bash
kubectl get secrets -n nba-stats
kubectl describe secret db-credentials -n nba-stats
```

## Rotating Secrets

### If you need to update a secret:

1. Create a new local secret with updated values:
   ```bash
   kubectl create secret generic db-credentials \
     --from-literal=POSTGRES_USER=newuser \
     --from-literal=POSTGRES_PASSWORD=newpass \
     --from-literal=DATABASE_URL='postgresql://newuser:newpass@postgres:5432/nba_stats' \
     -n nba-stats \
     --dry-run=client -o yaml > /tmp/new-secrets.yaml
   ```

2. Seal it:
   ```bash
   kubeseal < /tmp/new-secrets.yaml > k8s/sealed-secrets.yaml
   ```

3. Apply:
   ```bash
   kubectl apply -f k8s/sealed-secrets.yaml
   ```

4. Restart affected deployments to pick up new secrets:
   ```bash
   kubectl rollout restart deployment/backend -n nba-stats
   kubectl rollout restart deployment/celery-worker -n nba-stats
   kubectl rollout restart deployment/celery-beat -n nba-stats
   ```

## Credential Rotation (URGENT)

**The old `postgres/postgres` credentials were committed to git history and are compromised.**

### Before applying sealed secrets:

1. Change the PostgreSQL password in your live cluster:
   ```bash
   kubectl exec -n nba-stats postgres-pod-name -- \
     psql -U postgres -c "ALTER USER postgres WITH PASSWORD 'new-strong-password';"
   ```

   Or if using a PostgreSQL StatefulSet:
   ```bash
   kubectl set env deployment/postgres \
     POSTGRES_PASSWORD='new-strong-password' \
     -n nba-stats
   kubectl rollout restart deployment/postgres -n nba-stats
   ```

2. Update all services to use the new password (via sealed secrets)

3. Verify everything works before cleaning up old credentials

## Sealed Secrets Management

### Backup the sealing key (optional but recommended for disaster recovery):

```bash
kubectl get secret sealed-secrets-key -n kube-system -o yaml > ~/sealed-secrets-key-backup.yaml
```

**SECURE THIS FILE** — it's your cluster's master secret.

### View sealed secret content (debug only):

```bash
# Shows the encrypted data
kubectl get sealedsecret sealed-secrets -n nba-stats -o yaml

# To decrypt (requires cluster access):
# The controller automatically decrypts to a normal Secret
kubectl get secret db-credentials -n nba-stats -o yaml
```

## Troubleshooting

### "failed to unseal secret" error

Usually means the sealed secret was sealed on a different cluster.

```bash
# Check which cluster sealed the secret
kubectl get sealedsecrets sealed-secrets -n nba-stats -o yaml | grep scope

# Re-seal on current cluster:
# 1. Get plaintext secret from source cluster
# 2. kubeseal on current cluster
# 3. Apply to current cluster
```

### kubeseal can't connect to cluster

```bash
# Ensure you're connected to the right cluster
kubectl cluster-info
kubectl config current-context

# Ensure sealed-secrets controller is running
kubectl get pods -n kube-system | grep sealed
```

### Sealed secret exists but Secret doesn't appear

```bash
# Check the sealed-secrets controller logs
kubectl logs -n kube-system -l app.kubernetes.io/name=sealed-secrets -f

# Check the SealedSecret status
kubectl describe sealedsecret sealed-secrets -n nba-stats
```

## Additional Resources

- [Sealed Secrets GitHub](https://github.com/bitnami-labs/sealed-secrets)
- [Official Documentation](https://sealed-secrets.dev/)
- [Kubernetes Secret Best Practices](https://kubernetes.io/docs/concepts/configuration/secret/)

## Alternative: Using External Secrets Operator

If you prefer to use an external secret manager (HashiCorp Vault, AWS Secrets Manager, etc.), consider [External Secrets Operator](https://external-secrets.io/). The workflow is similar but secrets are stored outside the cluster.
