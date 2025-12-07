#!/bin/bash

# ==============================================================================
# Script Name: install_docker.sh
# Description: Installs Docker Engine (Community) and Docker Compose v2.
#              Configures the current user to run Docker without sudo.
# ==============================================================================

# Exit immediately if a command exits with a non-zero status
set -e

echo "[INFO] Starting Docker installation..."

# 1. Clean up old versions (if any) to avoid conflicts
echo "[INFO] Removing conflicting packages..."
for pkg in docker.io docker-doc docker-compose docker-compose-v2 podman-docker containerd runc; do 
    sudo apt-get remove -y $pkg || true
done

# 2. Update package index and install prerequisites
echo "[INFO] Updating apt package index..."
sudo apt-get update
sudo apt-get install -y ca-certificates curl gnupg

# 3. Add Docker's official GPG key
echo "[INFO] Adding Docker GPG key..."
sudo install -m 0755 -d /etc/apt/keyrings
if [ -f /etc/apt/keyrings/docker.gpg ]; then
    sudo rm /etc/apt/keyrings/docker.gpg
fi
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# 4. Set up the stable repository
echo "[INFO] Adding Docker repository..."
echo \
  "deb [arch=\"$(dpkg --print-architecture)\" signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 5. Install Docker Engine, containerd, and Docker Compose
echo "[INFO] Installing Docker packages..."
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin

# 6. Post-installation steps (Manage Docker as a non-root user)
echo "[INFO] Configuring user permissions..."
if ! getent group docker > /dev/null; then
    sudo groupadd docker
fi

sudo usermod -aG docker $USER

echo "[SUCCESS] Docker installed successfully."
echo "---------------------------------------------------"
docker --version
docker compose version
echo "---------------------------------------------------"
echo "IMPORTANT: You must log out and log back in for group changes to take effect."
echo "Type 'exit' to disconnect, then SSH back in."