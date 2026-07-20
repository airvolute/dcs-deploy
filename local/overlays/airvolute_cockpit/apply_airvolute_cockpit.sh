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

if [ -n "$cockpit_packages_archive" ]; then
    if [ ! -f "$cockpit_packages_archive" ]; then
        echo "Error: cockpit packages archive '$cockpit_packages_archive' does not exist."
        exit 1
    fi

    tmp_payload_dir=$(mktemp -d)
    trap 'if [ -n "$tmp_payload_dir" ]; then rm -rf "$tmp_payload_dir"; fi' EXIT

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

sudo mkdir -p \
    "${L4T_rootfs_path}/usr/local/share/cockpit" \
    "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit/branding" \
    "${L4T_rootfs_path}/usr/local/share/airvolute/cockpit/password-policy" \
    "${L4T_rootfs_path}/usr/local/bin" \
    "${L4T_rootfs_path}/etc/systemd/system/multi-user.target.wants"

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
