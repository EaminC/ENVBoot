#!/bin/bash
set -e
echo "[INFO] ENVBoot: creating env + installing deps"

# assumes conda is installed; if not, see bootstrap below
eval "$(conda shell.bash hook)"
conda env list | grep -q "^envboot " || conda create -n envboot python=3.10 -y
conda activate envboot

pip install --upgrade pip
pip install \
  openstacksdk \
  typer \
  python-dotenv \
  git+https://github.com/chameleoncloud/python-blazarclient@chameleoncloud/2023.1

echo "[OK] ENV ready. Next:"
echo "  source CHI-<project>-openrc.sh"
echo "  python -m envboot.cli resources"