#!/bin/bash
set -e

# Usage: ./deploy.sh "Optional commit message"
MSG="${1:-Update code}"

# Ensure we are in the project root directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=========================================="
echo "🚀 Mobiz Carwash: Git Push & Server Deploy"
echo "=========================================="

# 1. Stage and commit
echo "📦 Staging changes..."
git add .

if git diff-index --quiet HEAD --; then
    echo "ℹ️  No new changes to commit."
else
    echo "💾 Committing: \"$MSG\""
    git commit -m "$MSG"
fi

# 2. Push to GitHub
echo "⬆️  Pushing to GitHub (origin main)..."
git push origin main

# 3. Connect to Server, Pull, Migrate, and Restart
echo "🌐 Connecting to server (68.183.94.11)..."
sshpass -p 'mobiz321@' ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null root@68.183.94.11 "bash -s" << 'EOF'
set -e
echo "📥 Pulling latest code on server..."
cd /home/mobiz/webapps/car_wash/live
git pull origin main



echo "🔄 Checking migrations..."
/home/mobiz/webapps/car_wash/venv/bin/python manage.py migrate --noinput

echo "🎨 Collecting static files..."
/home/mobiz/webapps/car_wash/venv/bin/python manage.py collectstatic --noinput

echo "♻️  Restarting car_wash.service..."
systemctl restart car_wash.service

echo "📊 Verifying status:"
systemctl status car_wash.service --no-pager
EOF

echo ""
echo "=========================================="
echo "✅ Deployed and server restarted successfully!"
echo "=========================================="
