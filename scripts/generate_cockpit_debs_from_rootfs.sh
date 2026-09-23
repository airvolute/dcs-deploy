#!/bin/bash
set -euo pipefail

if [ "$#" -lt 2 ] || [ "$#" -gt 3 ]; then
    echo "Usage: $0 <rootfs.tar.bz2|rootfs.tar.gz|rootfs.tar> <output-debs-dir> [work-dir]" >&2
    exit 1
fi

rootfs_archive=$(realpath "$1")
output_dir=$(realpath -m "$2")
work_dir=$(realpath -m "${3:-.dcs_deploy/cockpit_deb_rootfs}")
rootfs_dir="$work_dir/rootfs"
download_dir="/tmp/cockpit-debs"

if [ ! -f "$rootfs_archive" ]; then
    echo "Error: rootfs archive does not exist: $rootfs_archive" >&2
    exit 1
fi

if ! command -v qemu-aarch64-static >/dev/null 2>&1; then
    echo "Error: qemu-aarch64-static is required." >&2
    exit 1
fi

cleanup_mounts() {
    for mount_point in run proc sys dev; do
        while mountpoint -q "$rootfs_dir/$mount_point"; do
            sudo umount "$rootfs_dir/$mount_point" || sudo umount -l "$rootfs_dir/$mount_point"
        done
    done
}

restore_resolv_conf() {
    if [ -f "$rootfs_dir/etc/resolv.conf.dcs-deploy-backup" ]; then
        sudo mv "$rootfs_dir/etc/resolv.conf.dcs-deploy-backup" "$rootfs_dir/etc/resolv.conf"
    fi
}

cleanup() {
    cleanup_mounts
    restore_resolv_conf
}
trap cleanup EXIT

sudo rm -rf "$work_dir"
mkdir -p "$rootfs_dir"

case "$rootfs_archive" in
    *.tar.bz2|*.tbz2)
        sudo tar xpf "$rootfs_archive" -C "$rootfs_dir" -I lbzip2
        ;;
    *.tar.gz|*.tgz)
        sudo tar xpf "$rootfs_archive" -C "$rootfs_dir" -z
        ;;
    *.tar)
        sudo tar xpf "$rootfs_archive" -C "$rootfs_dir"
        ;;
    *)
        echo "Error: unsupported rootfs archive type: $rootfs_archive" >&2
        exit 1
        ;;
esac

sudo cp /usr/bin/qemu-aarch64-static "$rootfs_dir/usr/bin/"

if [ -e "$rootfs_dir/etc/resolv.conf" ]; then
    sudo mv "$rootfs_dir/etc/resolv.conf" "$rootfs_dir/etc/resolv.conf.dcs-deploy-backup"
fi
sudo cp /etc/resolv.conf "$rootfs_dir/etc/resolv.conf"

sudo mount --bind /dev "$rootfs_dir/dev"
sudo mount -t proc proc "$rootfs_dir/proc"
sudo mount -t sysfs sys "$rootfs_dir/sys"
sudo mount --bind /run "$rootfs_dir/run"

sudo chroot "$rootfs_dir" /bin/bash -lc "
    set -euo pipefail
    export DEBIAN_FRONTEND=noninteractive
    rm -rf '$download_dir'
    mkdir -p '$download_dir'
    apt-get update
    apt-get install -y --download-only \
        -o Dir::Cache::archives='$download_dir' \
        cockpit \
        cockpit-networkmanager \
        cockpit-packagekit \
        cockpit-storaged \
        tcpdump
    rm -f '$download_dir/lock'
    rm -rf '$download_dir/partial'
"

sudo rm -rf "$output_dir"
mkdir -p "$output_dir"
sudo cp -a "$rootfs_dir/$download_dir/." "$output_dir/"
sudo chown -R "$(id -u):$(id -g)" "$output_dir"

deb_count=$(find "$output_dir" -maxdepth 1 -type f -name "*.deb" | wc -l)
if [ "$deb_count" -eq 0 ]; then
    echo "Error: no .deb files were downloaded." >&2
    exit 1
fi

echo "Downloaded $deb_count cockpit deb packages to $output_dir"
