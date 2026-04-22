# TLS Configuration for NBA Advanced Stats

This directory contains TLS configuration options for securing your NBA Advanced Stats Kubernetes deployment.

## Overview

Two TLS approaches are supported:

1. **Let's Encrypt (cert-manager + ACME)** - for deployments with a real DNS domain
2. **Self-signed certificates (cert-manager)** - for local/homelab deployments with `.local` hostnames

Both require `cert-manager` to be installed on your cluster.

## Option A: Let's Encrypt (Production)

Use this if you have a real, publicly-routable domain name (e.g., `nba-stats.example.com`).

### Prerequisites
- A real domain name
- cert-manager installed on the cluster

### Setup

1. **Install cert-manager** (one-time, cluster-wide):
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.yaml
   kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s
   ```

2. **Configure the ClusterIssuer**:
   - Edit `k8s/cert-manager/clusterissuer.yaml`
   - Replace `<YOUR_EMAIL>` with your email address
   - Replace `<YOUR_DOMAIN>` with your actual domain
   - Apply it:
     ```bash
     kubectl apply -f k8s/cert-manager/clusterissuer.yaml
     ```

3. **Update the Ingress**:
   - Edit `k8s/ingress.yaml`
   - Uncomment the `cert-manager.io/cluster-issuer` annotation
   - Replace `nba-stats.example.com` with your actual domain in both the `hosts` and `rules.host` sections
   - Uncomment the entire `tls` block

4. **Apply the updated Ingress**:
   ```bash
   kubectl apply -f k8s/ingress.yaml
   ```

5. **Verify certificate issuance**:
   ```bash
   kubectl describe certificate -n nba-stats nba-stats-tls
   kubectl get secret -n nba-stats nba-stats-tls
   ```

Certificate renewal is automatic. Let's Encrypt will send renewal reminders to your email.

## Option B: Self-signed Certificate (Homelab/Local)

Use this if you prefer to keep using `.local` hostnames or are in an isolated homelab environment.

### Prerequisites
- cert-manager installed on the cluster

### Setup

1. **Install cert-manager** (one-time, cluster-wide):
   ```bash
   kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.0/cert-manager.yaml
   kubectl wait --for=condition=Ready pod -l app.kubernetes.io/instance=cert-manager -n cert-manager --timeout=300s
   ```

2. **Deploy the self-signed issuer and certificate**:
   ```bash
   kubectl apply -f k8s/cert-manager/selfsigned-issuer.yaml
   kubectl apply -f k8s/cert-manager/selfsigned-certificate.yaml
   ```

3. **Update the Ingress**:
   - Edit `k8s/ingress.yaml`
   - Uncomment the `tls` block (but NOT the cert-manager annotation)
   - Keep the domain as `nba-stats.local` or update as needed

4. **Apply the updated Ingress**:
   ```bash
   kubectl apply -f k8s/ingress.yaml
   ```

5. **Trust the certificate (macOS)**:
   ```bash
   # Export the certificate
   kubectl get secret nba-stats-tls -n nba-stats -o jsonpath='{.data.tls\.crt}' | base64 -d > /tmp/nba-stats.crt
   
   # Add to macOS trusted keychain
   sudo security add-trusted-cert -d -r trustRoot -k /Library/Keychains/System.keychain /tmp/nba-stats.crt
   
   # Verify
   curl --cacert /tmp/nba-stats.crt https://nba-stats.local
   ```

## Option C: No TLS (Not Recommended)

The ingress currently defaults to HTTP. To upgrade, uncomment the TLS section and choose Option A or B above.

## Verification

After applying TLS configuration, verify the setup:

```bash
# Check certificate status
kubectl describe certificate -n nba-stats nba-stats-tls

# Check secret creation
kubectl get secret -n nba-stats nba-stats-tls -o yaml

# Test HTTPS connectivity (after DNS/hosts file update)
curl -kv https://nba-stats.local   # -k ignores self-signed cert warnings
curl https://nba-stats.example.com  # If using Let's Encrypt (no -k needed)
```

## Troubleshooting

### Certificate not issuing
```bash
kubectl describe clusterissuer letsencrypt-prod
kubectl logs -n cert-manager deployment/cert-manager -f
```

### Ingress shows HTTP instead of HTTPS
- Ensure the `tls` block is uncommented in `k8s/ingress.yaml`
- Verify the certificate secret exists: `kubectl get secret nba-stats-tls -n nba-stats`
- Wait a few seconds for the ingress controller to pick up the TLS configuration

### Let's Encrypt rate limits
- Each domain can request 50 new certificates per week
- Failed validations count toward the limit
- Use the staging environment for testing: `https://acme-staging-v02.api.letsencrypt.org/directory`

## DNS Setup (Let's Encrypt only)

Update your DNS records to point to your cluster's Ingress IP:
```bash
# Find your ingress IP
kubectl get ingress -n nba-stats nba-stats -o wide

# Add DNS record
# Type: A, Name: nba-stats.example.com, Value: <INGRESS_IP>
```

For local testing without public DNS, edit `/etc/hosts`:
```bash
# On your local machine
echo "<CLUSTER_IP> nba-stats.local" | sudo tee -a /etc/hosts
```

## Additional Resources

- [cert-manager documentation](https://cert-manager.io/docs/)
- [Let's Encrypt rate limiting](https://letsencrypt.org/docs/rate-limits/)
- [Nginx Ingress TLS termination](https://kubernetes.github.io/ingress-nginx/user-guide/tls/)
