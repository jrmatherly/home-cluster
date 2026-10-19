#!/bin/sh
# Get or create, so a rerun converges: a key pair that exists gets the
# current secret and policy.
set -eu
endpoint=http://rustfs-svc.rustfs.svc.cluster.local:9000
tries=0
until wget -q -O /dev/null "$endpoint/health/ready"; do
  tries=$((tries + 1))
  if [ "$tries" -ge 60 ]; then
    echo "RustFS is not ready after five minutes" >&2
    exit 1
  fi
  sleep 5
done
rc alias set root "$endpoint" "$RUSTFS_ACCESS_KEY" "$RUSTFS_SECRET_KEY"
provision() {
  name=$1 bucket=$2
  access_key=$(cat "/secrets/$name-access-key")
  secret_key=$(cat "/secrets/$name-secret-key")
  policy=/tmp/$name-policy.json
  printf '{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Action":["s3:*"],"Resource":["arn:aws:s3:::%s","arn:aws:s3:::%s/*"]}]}' "$bucket" "$bucket" > "$policy"
  rc bucket create --ignore-existing "root/$bucket"
  if rc admin service-account info root "$access_key" >/dev/null 2>&1; then
    rc admin service-account update root "$access_key" --secret-key "$secret_key" --policy "$policy"
  else
    rc admin service-account create root "$access_key" "$secret_key" --name "$name" --policy "$policy"
  fi
  echo "provisioned $name in $bucket"
}
provision ai-kb ai-kb-files
provision langfuse langfuse-events
