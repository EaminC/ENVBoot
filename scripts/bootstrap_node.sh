#!/bin/bash
set -e
sudo apt-get update
sudo apt-get install -y git curl build-essential

# Miniconda (Linux x86_64)
if ! command -v conda >/dev/null 2>&1; then
  curl -fsSLo ~/miniconda.sh https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh
  bash ~/miniconda.sh -b -p $HOME/miniconda3
  eval "$($HOME/miniconda3/bin/conda shell.bash hook)"
  conda init bash
  source ~/.bashrc
fi

echo "[OK] Node bootstrap complete."