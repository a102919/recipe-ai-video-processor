#!/bin/bash
#
# Migrate GCP VM to Always Free Tier
# Fixes: Static IP, Disk Type, Network Tier
#

set -e

GCP_PROJECT="gen-lang-client-0768313457"
GCP_ZONE="us-central1-c"
OLD_VM="foodai"
NEW_VM="foodai-free"
REGION="us-central1"

echo "============================================="
echo "  Migrate to GCP Always Free Tier"
echo "============================================="
echo ""
echo "⚠️  This script will:"
echo "  1. Create a new FREE VM (e2-micro + pd-standard)"
echo "  2. Release the static IP (saves $7.20/month)"
echo "  3. Use STANDARD network tier (cheaper egress)"
echo "  4. Migrate your data from old VM"
echo "  5. Delete the old VM"
echo ""
echo "Expected savings: ~$8-10/month → $0/month"
echo ""
read -p "Continue? (y/n) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
    echo "Aborted."
    exit 1
fi

echo ""
echo "Step 1/6: Creating snapshot of existing disk..."
SNAPSHOT_NAME="foodai-snapshot-$(date +%Y%m%d-%H%M%S)"
gcloud compute disks snapshot "$OLD_VM" \
    --snapshot-names="$SNAPSHOT_NAME" \
    --zone="$GCP_ZONE" \
    --project="$GCP_PROJECT"
echo "✅ Snapshot created: $SNAPSHOT_NAME"
echo ""

echo "Step 2/6: Creating new FREE disk from snapshot..."
gcloud compute disks create "${NEW_VM}-disk" \
    --size=30GB \
    --type=pd-standard \
    --zone="$GCP_ZONE" \
    --project="$GCP_PROJECT" \
    --source-snapshot="$SNAPSHOT_NAME"
echo "✅ Free disk created (30GB pd-standard)"
echo ""

echo "Step 3/6: Creating new FREE VM..."
gcloud compute instances create "$NEW_VM" \
    --project="$GCP_PROJECT" \
    --zone="$GCP_ZONE" \
    --machine-type=e2-micro \
    --network-interface=network-tier=STANDARD,subnet=default \
    --no-address \
    --maintenance-policy=MIGRATE \
    --provisioning-model=STANDARD \
    --disk=name="${NEW_VM}-disk",device-name="${NEW_VM}",mode=rw,boot=yes,auto-delete=yes \
    --no-shielded-secure-boot \
    --shielded-vtpm \
    --shielded-integrity-monitoring \
    --labels=type=free-tier \
    --reservation-affinity=any

echo "✅ New VM created: $NEW_VM"
echo ""

echo "Step 4/6: Waiting for new VM to boot..."
sleep 10
gcloud compute ssh --zone "$GCP_ZONE" "$NEW_VM" --project "$GCP_PROJECT" \
    --command "echo 'VM is ready'"
echo "✅ VM is online"
echo ""

echo "Step 5/6: Releasing static IP..."
gcloud compute addresses delete video-processor-ip \
    --region="$REGION" \
    --project="$GCP_PROJECT" \
    --quiet
echo "✅ Static IP released (saves $7.20/month)"
echo ""

echo "Step 6/6: Stopping old VM (keep for safety)..."
gcloud compute instances stop "$OLD_VM" \
    --zone="$GCP_ZONE" \
    --project="$GCP_PROJECT"
echo "✅ Old VM stopped"
echo ""

# Get new ephemeral IP
NEW_IP=$(gcloud compute instances describe "$NEW_VM" \
    --zone="$GCP_ZONE" \
    --project="$GCP_PROJECT" \
    --format='get(networkInterfaces[0].accessConfigs[0].natIP)')

echo "============================================="
echo "✅ Migration Complete!"
echo "============================================="
echo ""
echo "New VM Details:"
echo "  Name:          $NEW_VM"
echo "  Type:          e2-micro (FREE)"
echo "  Disk:          30GB pd-standard (FREE)"
echo "  Network:       STANDARD tier (cheaper egress)"
echo "  IP:            $NEW_IP (ephemeral - FREE when in use)"
echo ""
echo "Monthly Cost: $0 (within Always Free limits)"
echo ""
echo "Next Steps:"
echo "  1. Test new VM: gcloud compute ssh --zone '$GCP_ZONE' '$NEW_VM' --project '$GCP_PROJECT'"
echo "  2. Deploy code: cd video-processor && ./deploy_gcp_free.sh"
echo "  3. Verify service: curl http://$NEW_IP:8000/health"
echo "  4. Delete old VM: gcloud compute instances delete '$OLD_VM' --zone='$GCP_ZONE' --project='$GCP_PROJECT'"
echo "  5. Delete old disk: gcloud compute disks delete '$OLD_VM' --zone='$GCP_ZONE' --project='$GCP_PROJECT'"
echo ""
echo "⚠️  Note: Ephemeral IP may change on VM restart"
echo "   Use internal backend or configure dynamic DNS if needed"
echo ""
