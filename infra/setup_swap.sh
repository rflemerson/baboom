#!/bin/bash

# ==============================================================================
# Script Name: setup_swap.sh
# Description: Creates a swap file and optimizes kernel settings for low-RAM VPS.
# ==============================================================================

# Exit immediately if a command exits with a non-zero status
set -e

# Variables
SWAP_SIZE="4G"
SWAP_FILE="/swapfile"

echo "[INFO] Starting Swap configuration..."

# 1. Check if swap already exists to prevent duplication
if grep -q "$SWAP_FILE" /proc/swaps; then
    echo "[WARN] Swap file $SWAP_FILE is already active. Skipping creation."
else
    echo "[INFO] Creating $SWAP_SIZE swap file at $SWAP_FILE..."
    
    # Allocate space
    sudo fallocate -l $SWAP_SIZE $SWAP_FILE
    
    # Secure permissions (read/write for root only)
    sudo chmod 600 $SWAP_FILE
    
    # Set up the Linux swap area
    sudo mkswap $SWAP_FILE
    
    # Enable the swap
    sudo swapon $SWAP_FILE
    echo "[SUCCESS] Swap enabled."

    # Make it permanent in /etc/fstab
    if ! grep -q "$SWAP_FILE" /etc/fstab; then
        echo "[INFO] Backing up /etc/fstab..."
        sudo cp /etc/fstab /etc/fstab.bak
        
        echo "[INFO] Updating /etc/fstab for persistence..."
        echo "$SWAP_FILE none swap sw 0 0" | sudo tee -a /etc/fstab
    fi
fi

# 2. Kernel Optimization (Swappiness & Cache Pressure)
# swappiness=10: Only use swap when RAM is ~90% full.
# vfs_cache_pressure=50: Keep inode metadata in RAM longer.
echo "[INFO] Tuning kernel parameters..."

sudo sysctl vm.swappiness=10 > /dev/null
sudo sysctl vm.vfs_cache_pressure=50 > /dev/null

# Persist kernel settings
CONFIG_FILE="/etc/sysctl.conf"

if ! grep -q "vm.swappiness" $CONFIG_FILE; then
    echo "vm.swappiness=10" | sudo tee -a $CONFIG_FILE
fi

if ! grep -q "vm.vfs_cache_pressure" $CONFIG_FILE; then
    echo "vm.vfs_cache_pressure=50" | sudo tee -a $CONFIG_FILE
fi

echo "[SUCCESS] Swap configuration completed successfully."
echo "---------------------------------------------------"
free -h
echo "---------------------------------------------------"