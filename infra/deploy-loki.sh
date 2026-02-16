#!/usr/bin/env bash
# deploy-loki.sh — Deploy Loki integration to VPS (Dokploy)
#
# This script uploads updated configs to the VPS and triggers redeployment.
# Run from the infra/ directory: cd infra && bash deploy-loki.sh
#
# Prerequisites:
#   - SSH access to the VPS (ssh root@vps.quentinveys.be)
#   - Dokploy otel-stack already deployed
set -euo pipefail

VPS="root@vps.quentinveys.be"
OTEL_FILES="/etc/dokploy/compose/opentelemetry-otelstack-iyizfb/files"

echo "=== Step 1: Upload Loki config for standalone Loki compose ==="
# Create the Loki compose directory structure on VPS
ssh "$VPS" "mkdir -p /etc/dokploy/compose/loki/files"
scp loki-config.yaml "$VPS:$OTEL_FILES/loki-config.yaml"
echo "  ✓ loki-config.yaml uploaded"

echo ""
echo "=== Step 2: Upload updated OTel Collector config (adds loki exporter + logs pipeline) ==="
scp otel-collector-config.yaml "$VPS:$OTEL_FILES/otel-collector-config.yaml"
echo "  ✓ otel-collector-config.yaml uploaded"

echo ""
echo "=== Step 3: Upload Grafana Loki datasource ==="
ssh "$VPS" "mkdir -p $OTEL_FILES/grafana/provisioning/datasources"
scp grafana/provisioning/datasources/loki.yaml "$VPS:$OTEL_FILES/grafana/provisioning/datasources/loki.yaml"
echo "  ✓ loki.yaml datasource uploaded"

echo ""
echo "=== Step 4: Upload dashboards (with \$__range fix) ==="
scp grafana/dashboards/*.json "$VPS:$OTEL_FILES/grafana/dashboards/"
echo "  ✓ dashboards uploaded"

echo ""
echo "=== Done! ==="
echo ""
echo "Next steps in Dokploy UI:"
echo "  1. Create a new compose 'loki' in the OpenTelemetry project"
echo "     - Paste contents of infra/loki/docker-compose.yml"
echo "     - Deploy it"
echo "  2. Redeploy otel-stack (picks up new collector config + Grafana datasource)"
echo "  3. Verify in Grafana > Explore > Loki datasource"
echo "     - Query: {service_name=\"ai-cost-observer\"}"
