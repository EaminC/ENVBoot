#!/bin/bash
# setup.sh – one-time setup for ENVBoot on Chameleon

set -e  # stop on first error

echo "[INFO] Starting ENVBoot setup..."

# 1. Initialize conda if not already done
if ! command -v conda &> /dev/null; then
    echo "[ERROR] Conda not found. Please install Miniconda/Anaconda first."
    exit 1
fi

# 2. Make sure conda hooks are loaded
eval "$(conda shell.bash hook)"

# 3. Create envboot environment if not exists
if conda env list | grep -q "envboot"; then
    echo "[INFO] Conda environment 'envboot' already exists. Skipping creation."
else
    echo "[INFO] Creating conda environment 'envboot'..."
    conda create -n envboot python=3.10 -y
fi

# 4. Activate env
conda activate envboot

# 5. Install dependencies
echo "[INFO] Installing dependencies..."
pip install --upgrade pip
pip install python-openstackclient git+https://github.com/chameleoncloud/python-blazarclient@chameleoncloud/2023.1 python-dotenv openai

echo "[✅] Setup complete. Next steps:"
echo " - Run: source CHI-xxxx-openrc.sh   # your Chameleon credentials"
echo " - Then: conda activate envboot     # to re-enter this env"
echo " - You’re ready for CLI commands (openstack ...)"