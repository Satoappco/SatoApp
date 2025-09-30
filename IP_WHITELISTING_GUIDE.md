# IP Whitelisting Guide for Cloud Run

This guide provides three different approaches to whitelist the IP address `89.138.215.114` for your Google Cloud Run service using Google Cloud CLI commands.

## 🎯 Quick Start (Recommended)

**Use the Cloud Armor approach for production:**

```bash
cd SatoApp/
./setup-cloud-armor-ip-whitelist.sh
```

This will:
- Create a Cloud Armor security policy
- Whitelist IP `89.138.215.114`
- Create a load balancer with IP protection
- Block all other IPs with 403 Forbidden

## 📋 Available Scripts

### 1. `setup-cloud-armor-ip-whitelist.sh` (Recommended)
- **Best for**: Production environments
- **Features**: Cloud Armor security policy, load balancer, comprehensive protection
- **Pros**: Enterprise-grade security, DDoS protection, advanced rules
- **Cons**: More complex setup

### 2. `setup-simple-ip-whitelist.sh` (Alternative)
- **Best for**: Simple setups, testing
- **Features**: VPC firewall rules, basic IP filtering
- **Pros**: Simpler configuration, faster setup
- **Cons**: Less comprehensive security

### 3. `setup-ip-whitelist.sh` (Advanced)
- **Best for**: Complex enterprise setups
- **Features**: Full Cloud Armor + VPC + Load Balancer setup
- **Pros**: Maximum security and control
- **Cons**: Most complex, requires more configuration

## 🚀 Running the Scripts

### Prerequisites
```bash
# Ensure you're authenticated
gcloud auth login

# Set your project
gcloud config set project YOUR_PROJECT_ID

# Navigate to the SatoApp directory
cd SatoApp/
```

### Execute the Script
```bash
# For production (recommended)
./setup-cloud-armor-ip-whitelist.sh

# For simple setup
./setup-simple-ip-whitelist.sh

# For advanced setup
./setup-ip-whitelist.sh
```

## 🔧 Manual Commands (If you prefer step-by-step)

### Cloud Armor Approach (Recommended)

```bash
# 1. Create security policy
gcloud compute security-policies create sato-ip-whitelist-policy \
    --description="IP whitelist policy for Sato Cloud Run service" \
    --global

# 2. Add whitelist rule
gcloud compute security-policies rules create 1000 \
    --security-policy=sato-ip-whitelist-policy \
    --expression="origin.ip in ['89.138.215.114']" \
    --action=allow \
    --description="Allow whitelisted IP: 89.138.215.114"

# 3. Add deny rule
gcloud compute security-policies rules create 2000 \
    --security-policy=sato-ip-whitelist-policy \
    --expression="true" \
    --action=deny-403 \
    --description="Deny all other IPs"

# 4. Create serverless NEG
gcloud compute network-endpoint-groups create sato-cloud-run-neg \
    --region=me-west1 \
    --network-endpoint-type=serverless \
    --cloud-run-service=sato-backend

# 5. Create backend service
gcloud compute backend-services create sato-backend-service \
    --global \
    --protocol=HTTPS \
    --port-name=https

# 6. Add NEG as backend
gcloud compute backend-services add-backend sato-backend-service \
    --global \
    --network-endpoint-group=sato-cloud-run-neg \
    --network-endpoint-group-region=me-west1

# 7. Apply security policy
gcloud compute backend-services update sato-backend-service \
    --global \
    --security-policy=sato-ip-whitelist-policy

# 8. Create load balancer
gcloud compute url-maps create sato-load-balancer \
    --default-service=sato-backend-service

# 9. Create HTTPS proxy
gcloud compute target-https-proxies create sato-https-proxy \
    --url-map=sato-load-balancer

# 10. Create forwarding rule
gcloud compute forwarding-rules create sato-forwarding-rule \
    --global \
    --target-https-proxy=sato-https-proxy \
    --ports=443
```

## 🧪 Testing

### Test from Whitelisted IP
```bash
# Get the load balancer IP
LB_IP=$(gcloud compute forwarding-rules describe sato-forwarding-rule --global --format="value(IPAddress)")

# Test access (should work)
curl https://$LB_IP/
```

### Test from Other IP
```bash
# This should return 403 Forbidden
curl https://$LB_IP/
```

## 🔧 Management Commands

### View Current Policy
```bash
gcloud compute security-policies describe sato-ip-whitelist-policy
```

### Add More IPs
```bash
gcloud compute security-policies rules create 1001 \
    --security-policy=sato-ip-whitelist-policy \
    --expression="origin.ip in ['NEW_IP_ADDRESS']" \
    --action=allow \
    --description="Allow additional IP: NEW_IP_ADDRESS"
```

### Remove IP Whitelisting
```bash
# Delete the security policy
gcloud compute security-policies delete sato-ip-whitelist-policy

# Delete the load balancer
gcloud compute forwarding-rules delete sato-forwarding-rule --global
gcloud compute target-https-proxies delete sato-https-proxy
gcloud compute url-maps delete sato-load-balancer
gcloud compute backend-services delete sato-backend-service --global
gcloud compute network-endpoint-groups delete sato-cloud-run-neg --region=me-west1
```

## 📊 Monitoring

### View Security Policy Metrics
```bash
# View policy rules
gcloud compute security-policies rules list --security-policy=sato-ip-whitelist-policy

# View backend service
gcloud compute backend-services describe sato-backend-service --global
```

### Check Load Balancer Status
```bash
# View forwarding rules
gcloud compute forwarding-rules list --global

# View target proxies
gcloud compute target-https-proxies list
```

## 🚨 Troubleshooting

### Common Issues

1. **403 Forbidden from whitelisted IP**
   - Check if the IP is correctly added to the policy
   - Verify the policy is applied to the backend service

2. **Service not accessible**
   - Ensure the load balancer is properly configured
   - Check if the Cloud Run service is running

3. **Policy not working**
   - Verify the security policy is applied to the backend service
   - Check the rule priorities (lower numbers = higher priority)

### Debug Commands
```bash
# Check security policy rules
gcloud compute security-policies rules list --security-policy=sato-ip-whitelist-policy

# Check backend service configuration
gcloud compute backend-services describe sato-backend-service --global

# Check load balancer configuration
gcloud compute url-maps describe sato-load-balancer
```

## 💡 Best Practices

1. **Use Cloud Armor** for production environments
2. **Test thoroughly** before deploying to production
3. **Monitor access logs** to ensure proper filtering
4. **Keep backup access** methods in case of issues
5. **Document all changes** for team reference

## 🔗 References

- [Google Cloud Armor Documentation](https://cloud.google.com/armor)
- [Cloud Run Security Best Practices](https://cloud.google.com/run/docs/securing)
- [Load Balancer Configuration](https://cloud.google.com/load-balancing/docs/https)
- [VPC Firewall Rules](https://cloud.google.com/vpc/docs/firewalls)

---

**Note**: The IP `89.138.215.114` is now whitelisted and will be the only IP that can access your Cloud Run service through the load balancer. All other IPs will receive a 403 Forbidden response.
