#!/bin/bash
set -o pipefail
set -e

# This script prints each argument and identifies whether it's a named (key=value) or positional argument

for arg in "$@"; do
    if [[ "$arg" == *=* ]]; then
        key="${arg%%=*}"
        value="${arg#*=}"
        echo "Named argument: key='$key', value='$value'"
    else
        echo "Positional argument: value='$arg'"
    fi
done
