#!/bin/bash
set -o pipefail
set -e

L4T_rootfs_path=$1
shift || true

if [ -z "$L4T_rootfs_path" ] || [ ! -d "$L4T_rootfs_path" ]; then
    echo "Error: L4T_rootfs_path '$L4T_rootfs_path' does not exist."
    exit 1
fi

script_path=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &> /dev/null && pwd)
resources_path="$script_path/resources"

if [ ! -d "$resources_path" ]; then
    echo "Error: resources path '$resources_path' does not exist."
    exit 1
fi

cockpit_packages_archive=""
for arg in "$@"; do
    case "$arg" in
        cockpit_packages_archive=*)
            cockpit_packages_archive="${arg#cockpit_packages_archive=}"
            ;;
    esac
done

payload_path="$resources_path"
tmp_payload_dir=""
chroot_deb_dir="/tmp/airvolute-cockpit-debs"
copied_qemu=0
mounted_paths=()

cleanup() {
    for ((i=${#mounted_paths[@]}-1; i>=0; i--)); do
        if mountpoint -q "${mounted_paths[$i]}"; then
            sudo umount "${mounted_paths[$i]}"
        fi
    done
    if [ "$copied_qemu" -eq 1 ]; then
        sudo rm -f "${L4T_rootfs_path}/usr/bin/qemu-aarch64-static"
    fi
    sudo rm -rf "${L4T_rootfs_path}${chroot_deb_dir}"
    if [ -n "$tmp_payload_dir" ]; then
        rm -rf "$tmp_payload_dir"
    fi
}
trap cleanup EXIT

if [ -n "$cockpit_packages_archive" ]; then
    if [ ! -f "$cockpit_packages_archive" ]; then
        echo "Error: cockpit packages archive '$cockpit_packages_archive' does not exist."
        exit 1
    fi

    tmp_payload_dir=$(mktemp -d)

    tar -xf "$cockpit_packages_archive" -C "$tmp_payload_dir"

    if [ -d "$tmp_payload_dir/packages" ]; then
        payload_path="$tmp_payload_dir"
    else
        first_dir=$(find "$tmp_payload_dir" -mindepth 1 -maxdepth 1 -type d | head -n 1)
        if [ -n "$first_dir" ] && [ -d "$first_dir/packages" ]; then
            payload_path="$first_dir"
        else
            echo "Error: cockpit packages archive must contain a packages directory."
            exit 1
        fi
    fi
fi

if [ ! -d "$payload_path/packages" ]; then
    echo "Error: cockpit packages path '$payload_path/packages' does not exist."
    exit 1
fi

if [ ! -d "$payload_path/debs" ]; then
    echo "Error: cockpit deb packages path '$payload_path/debs' does not exist."
    exit 1
fi

json_file="${L4T_rootfs_path}/home/dcs_user/Airvolute/logs/dcs-deploy/dcs_deploy_data.json"
sudo mkdir -p "$(dirname "$json_file")"
if [ ! -f "$json_file" ]; then
    echo '{"services":[],"binaries":[]}' | sudo tee "$json_file" > /dev/null
fi

add_json_entry() {
    local key=$1
    local value=$2

    sudo jq --arg key "$key" --arg value "$value" \
        '.[$key] = (.[$key] // []) | if .[$key] | index($value) then . else .[$key] += [$value] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
}

add_debs() {
    local deb_dir=$1
    local deb_files=()

    while IFS= read -r deb_file; do
        deb_files+=("$deb_file")
    done < <(find "$deb_dir" -maxdepth 1 -type f -name "*.deb" | sort)

    if [ ${#deb_files[@]} -eq 0 ]; then
        echo "Error: cockpit deb packages path '$deb_dir' does not contain any .deb files."
        exit 1
    fi

    echo "Installing official Cockpit deb packages into ${L4T_rootfs_path}/"

    if [ ! -x "${L4T_rootfs_path}/usr/bin/qemu-aarch64-static" ]; then
        if [ ! -x "/usr/bin/qemu-aarch64-static" ]; then
            echo "Error: /usr/bin/qemu-aarch64-static is required to install Cockpit deb packages in chroot."
            exit 1
        fi
        sudo cp /usr/bin/qemu-aarch64-static "${L4T_rootfs_path}/usr/bin/qemu-aarch64-static"
        copied_qemu=1
    fi

    sudo rm -rf "${L4T_rootfs_path}${chroot_deb_dir}"
    sudo mkdir -p "${L4T_rootfs_path}${chroot_deb_dir}"
    sudo cp -a "$deb_dir"/. "${L4T_rootfs_path}${chroot_deb_dir}/"

    for mount_name in dev proc sys run; do
        local mount_target="${L4T_rootfs_path}/${mount_name}"
        if ! mountpoint -q "$mount_target"; then
            case "$mount_name" in
                proc)
                    sudo mount -t proc proc "$mount_target"
                    ;;
                sys)
                    sudo mount -t sysfs sysfs "$mount_target"
                    ;;
                *)
                    sudo mount --bind "/$mount_name" "$mount_target"
                    ;;
            esac
            mounted_paths+=("$mount_target")
        fi
    done

    sudo chroot "${L4T_rootfs_path}" /bin/bash -lc "
        set -e
        export DEBIAN_FRONTEND=noninteractive
        dpkg -i ${chroot_deb_dir}/*.deb || dpkg --configure -a
    "

    for deb_file in "${deb_files[@]}"; do
        add_json_entry deb "$(basename "$deb_file")"
    done
}

sudo mkdir -p \
    "${L4T_rootfs_path}/usr/local/share/cockpit" \
    "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit/branding" \
    "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit/password-policy" \
    "${L4T_rootfs_path}/usr/local/bin" \
    "${L4T_rootfs_path}/etc/systemd/system/multi-user.target.wants"

add_debs "$payload_path/debs"

for package_dir in "$payload_path"/packages/*; do
    if [ ! -d "$package_dir" ]; then
        continue
    fi
    package_name=$(basename "$package_dir")
    sudo rm -rf "${L4T_rootfs_path}/usr/local/share/cockpit/${package_name}"
    sudo mkdir -p "${L4T_rootfs_path}/usr/local/share/cockpit/${package_name}"
    sudo cp -a "${package_dir}/." "${L4T_rootfs_path}/usr/local/share/cockpit/${package_name}/"
    sudo chown -R root:root "${L4T_rootfs_path}/usr/local/share/cockpit/${package_name}"
    add_json_entry cockpit_packages "/usr/local/share/cockpit/${package_name}"
done

if [ -d "$payload_path/branding" ]; then
    sudo cp -a "$payload_path"/branding/. "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit/branding/"
fi
if [ -d "$payload_path/password-policy" ]; then
    sudo cp -a "$payload_path"/password-policy/. "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit/password-policy/"
fi
sudo chown -R root:root "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit"

sudo cp "$resources_path/airvolute_cockpit_first_boot.sh" "${L4T_rootfs_path}/usr/local/bin/airvolute_cockpit_first_boot.sh"
sudo chmod +x "${L4T_rootfs_path}/usr/local/bin/airvolute_cockpit_first_boot.sh"
sudo cp "$resources_path/airvolute_cockpit_first_boot.service" "${L4T_rootfs_path}/etc/systemd/system/airvolute_cockpit_first_boot.service"
sudo ln -sf /etc/systemd/system/airvolute_cockpit_first_boot.service \
    "${L4T_rootfs_path}/etc/systemd/system/multi-user.target.wants/airvolute_cockpit_first_boot.service"

add_json_entry services "/etc/systemd/system/airvolute_cockpit_first_boot.service"
add_json_entry binaries "/usr/local/bin/airvolute_cockpit_first_boot.sh"

echo "Airvolute Cockpit overlay installed into ${L4T_rootfs_path}"
