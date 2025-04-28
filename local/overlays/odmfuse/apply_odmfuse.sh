#!/bin/bash
# stop when any error occures
set -o pipefail
set -e 

#set -o xtrace

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
source ${SCRIPT_DIR}/../lib/arg_parser.sh

init_variables $@
shift $INIT_VAR_NUM
print_variables

RESOURCES_dir="$SCRIPT_DIR/resources"
DECRYPT_FUNC_FILE="decrypt.func"
ODMFUSE_FILE="odmfuse.func"
RESOURCE_ARCHIVE="$RESOURCES_dir/odmfuse_resources.tar.gz"
KEY_FILE="$RESOURCES_dir/enc.key"
L4T_dir="${L4T_rootfs_path%/}/.."
USE_KEYS_FOR_TEST=0
source "$SCRIPT_DIR/$ODMFUSE_FILE"
source "$SCRIPT_DIR/$DECRYPT_FUNC_FILE"

# Validate archive
if [[ ! -f "$RESOURCE_ARCHIVE" ]]; then
    echo "[ERROR] Resource archive not found: $RESOURCE_ARCHIVE"
    exit 1
fi

source "${SCRIPT_DIR}/tools.func"


while(($#)) ; do
  #echo "par $1"
  case $1 in
      "--fuse"|"--fuse-test"|"--fuse-blob")
        [[ -z $2 ]] && echo "Missing parameter! Please provide board config name eg (airvolute-dcs1.2+p3767-0000) to fuse!" && exit 1
        # Use key if it exists, otherwise fallback to TPM unseal
        if [[ -f "$KEY_FILE" ]]; then
            echo "[INFO] AES key found, using: $KEY_FILE"
            untar_and_decrypt_odmfuse_resources "$RESOURCE_ARCHIVE" "$KEY_FILE"
        else
            echo "[INFO] No key file found, attempting TPM-based decryption"
            untar_and_decrypt_odmfuse_resources "$RESOURCE_ARCHIVE" ""
        fi
     
        if [[ $1 == "--fuse-test" ]]; then 
            odmfuse $2 "test"
        elif [[ $1 == "--fuse-blob" ]]; then 
            ${L4T_dir}/bootloader/fusecmd.sh
        else
            echo "Warning Going to fuse permanetly!"
            odmfuse $2
        fi
        secure_delete_files $RSA_PEM_fname $SBK_KEY_fname $FUSE_XML_fname
        shift
      ;;
      "--is-fused")
        [[ -z $2 ]] && echo "Missing parameter! Please provide board config name eg (airvolute-dcs1.2+p3767-0000) to fuse!" && exit 1
        
        if [[ $USE_KEYS_FOR_TEST != 0 ]]; then
            # Use key if it exists, otherwise fallback to TPM unseal
            if [[ -f "$KEY_FILE" ]]; then
                echo "[INFO] AES key found, using: $KEY_FILE"
                untar_and_decrypt_odmfuse_resources "$RESOURCE_ARCHIVE" "$KEY_FILE"
            else
                echo "[INFO] No key file found, attempting TPM-based decryption"
                untar_and_decrypt_odmfuse_resources "$RESOURCE_ARCHIVE" ""
            fi
        fi
        is_device_fused $2
        exit $?
      ;;

      "--cleanup")
         cleanup
      ;;
      *)
         echo "incorrect parameter! Exitting!"
         exit 1
      ;;
  esac
  shift
done

