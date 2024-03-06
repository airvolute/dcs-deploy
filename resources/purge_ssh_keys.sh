#!/bin/bash

# Check if a path was provided as an argument
if [ -z "$1" ]; then
  echo "purge_ssh_keys.sh Usage: $0 /path/to/user/.ssh"
  exit 1
fi

SSH_DIR="$1"

# Remove all contents of the specified .ssh directory
if [ -d "$SSH_DIR" ]; then
  echo "Removing all contents of $SSH_DIR"
  rm -rf "$SSH_DIR"/*
else
  echo "Directory $SSH_DIR does not exist. Continue."
fi
