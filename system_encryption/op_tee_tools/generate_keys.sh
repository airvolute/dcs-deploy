#!/bin/bash

# [T234 example]
# Fill your OEM_K1 fuse key value
echo "2d4a614e645267556b58703273357638792f423f4428472b4b6250655368566d" > oem_k1.key

# This is the fixed vector for deriving EKB root key from fuse.
# It is expected user to replace the FV below with a user specific
# FV, and code the exact same user specific FV into OP-TEE.
echo "bad66eb4484983684b992fe54a648bb8" > fv_ekb_t234

# Generate user-defined symmetric key files
openssl rand -rand /dev/urandom -hex 32 > sym_t234.key    # kernel/kernel-dtb encryption key
openssl rand -rand /dev/urandom -hex 16 > sym2_t234.key   # disk encryption key


# Build the Docker image
docker build -t gen-ekb-tool .
# Run the container with arguments
docker run --rm -v $(pwd):/app gen-ekb-tool