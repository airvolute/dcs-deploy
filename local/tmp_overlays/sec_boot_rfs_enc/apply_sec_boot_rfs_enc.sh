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

L4T_dir="${L4T_rootfs_path%/}/.."
RESOURCES_dir="$SCRIPT_DIR/resources"
#TOOLS_dir="$SCRIPT_DIR/tools"
# please provide new value in config_db for public_sources: "public_sources": "https://developer.nvidia.com/downloads/embedded/l4t/r35_release_v4.1/sources/public_sources.tbz2"
TOOLS_dir="${L4T_dir}/source/public/optee/samples/hwkey-agent/host/tool/gen_ekb/"
DECRYPT_FUNC_FILE="decrypt.func"
RESOURCE_ARCHIVE="$RESOURCES_dir/sec_boot_rfs_enc_resources.tar.gz"
KEY_FILE="$RESOURCES_dir/enc.key"


source "$SCRIPT_DIR/$DECRYPT_FUNC_FILE"

# Validate archive
if [[ ! -f "$RESOURCE_ARCHIVE" ]]; then
    echo "[ERROR] Resource archive not found: $RESOURCE_ARCHIVE"
    exit 1
fi

source "${SCRIPT_DIR}/tools.func"

source "${SCRIPT_DIR}/l4t_initrd_secure_params.func"

source "${SCRIPT_DIR}/gen_eks_t234.func"

while(($#)) ; do
  #echo "par $1"
  case $1 in
      "--get-internal-params")
        get_sec_boot_rfs_enc_res $RESOURCE_ARCHIVE $KEY_FILE
        ret=$?
        [[ $ret != 0 ]] && exit $ret  
        [ -z $UEFI_KEYS_CFG_FILE ] && exit 1
        params=$(gen_secured_internal_qspi_params $UEFI_KEYS_CFG_FILE $UEFI_ENC_KEY_fname)
        ret=$?
        [[ $ret != 0 ]] && exit $ret
        echo -n $params
      ;;
      "--get-ext-params")
        get_sec_boot_rfs_enc_res $RESOURCE_ARCHIVE $KEY_FILE
        ret=$?
        [[ $ret != 0 ]] && exit $ret  
        [ -z $UEFI_KEYS_CFG_FILE ] && exit 1
        params=$(gen_secured_external_qspi_params $UEFI_KEYS_CFG_FILE $UEFI_ENC_KEY_fname)
        ret=$?
        [[ $ret != 0 ]] && exit $ret
        echo -n $params
      ;;
      "--gen-and-copy-eks-image")
        EKS_IMAGE_dir=$(mktemp -d)
        get_sec_boot_rfs_enc_res $RESOURCE_ARCHIVE $KEY_FILE
        ret=$?
        [[ $ret != 0 ]] && exit $ret  
        prepare_tee_eks_image
        deploy_tee_eks_image
        secure_delete_dir $EKS_IMAGE_dir
      ;;
      "--cleanup")
         secure_delete_dir "/dev/shm/l-0/"
         exit $?
      ;;
      *)
         echo "incorrect parameter! Exitting!"
         exit 1
      ;;
  esac
  shift
done

