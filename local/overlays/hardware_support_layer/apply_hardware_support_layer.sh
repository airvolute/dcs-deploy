#!/bin/bash
# stop when any error occures
set -o pipefail
set -e 

# lib path
SCRIPT_PATH=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
LIB_PATH=$SCRIPT_PATH/../lib

# Include the arg_parser.sh script
source $LIB_PATH/arg_parser.sh

# Global variables
tmp_script_path=/tmp/handle_hardware_services.sh

init_variables "$1" "$2" "$3" "$4" "$5" "$6" "$7"

script_path=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
echo "script_path: $script_path"

resources_path=$script_path/resources
echo "resouce path: $resources_path"

# Setup systemd first boot
service_destination=${L4T_rootfs_path}/etc/systemd/system
# Bin destination
bin_destination=${L4T_rootfs_path}/usr/local/bin
# udev destination
udev_destination=${L4T_rootfs_path}/etc/udev/rules.d
# Utilities destination
util_device_folder=/home/dcs_user/Airvolute/resources
util_destination=${L4T_rootfs_path}${util_device_folder}
# Docs destination
docs_destination=${L4T_rootfs_path}/home/dcs_user/Airvolute/docs
# JSON log file setup
json_file="${L4T_rootfs_path}/home/dcs_user/Airvolute/logs/dcs-deploy/dcs_deploy_data.json"

# Ensure the directory structure exists
sudo mkdir -p "$(dirname "$json_file")"
sudo mkdir -p "$docs_destination"

# Initialize or validate JSON file
initialize_json_file() {
    if [ ! -f "$json_file" ]; then
        echo '{"services":[],"binaries":[]}' | sudo tee "$json_file" > /dev/null
        echo "Initialized JSON file at $json_file"
    else
        # Validate existing file structure
        echo "Validating existing JSON file: $json_file"
        valid_structure=$(sudo jq 'has("services") and has("binaries")' "$json_file" || echo "false")
        if [ "$valid_structure" != "true" ]; then
            echo "Invalid JSON structure. Reinitializing file."
            echo '{"services":[],"binaries":[]}' | sudo tee "$json_file" > /dev/null
        fi
    fi
}

add_service_to_json() {
    local service_path=$1
    sudo jq --arg path "$service_path" \
        'if .services | index($path) then . else .services += [$path] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
    echo "Added service to JSON: $service_path"
}

add_binary_to_json() {
    local binary_path=$1
    sudo jq --arg path "$binary_path" \
        'if .binaries | index($path) then . else .binaries += [$path] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
    echo "Added binary to JSON: $binary_path"
}

add_udev_to_json()
{
    local udev_path=$1
    sudo jq --arg path "$udev_path" \
        'if .udev | index($path) then . else .udev += [$path] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
    echo "Added udev to JSON: $udev_path"
}

add_deb_to_json()
{
    local deb_path=$1
    sudo jq --arg path "$deb_path" \
        'if .deb | index($path) then . else .deb += [$path] end' \
        "$json_file" | sudo tee "$json_file.tmp" > /dev/null
    sudo mv "$json_file.tmp" "$json_file"
    echo "Added deb to JSON: $deb_path"
}

check_patch_compatibility() {
    local patch_dir=$1
    local target_device=$2
    local jetpack_version=$3
    local hwrev=$4
    local board_expansion=$5
    local storage=$6
    local rootfs_type=$7

    # Check if compatibility file exists
    if [[ ! -f "$patch_dir/compatible" ]]; then
        echo "No compatibility file found in $patch_dir. Assuming not compatible."
        return 1
    fi

    local is_compatible=false

    # Parse compatibility file and match
    while IFS= read -r comp; do
        # Extract individual fields for debugging
        devices=$(echo "$comp" | jq -r '.device[]?')
        storages=$(echo "$comp" | jq -r '.storage[]?')
        boards=$(echo "$comp" | jq -r '.board[]?')
        board_expansions=$(echo "$comp" | jq -r '.board_expansion[]?')
        l4t_versions=$(echo "$comp" | jq -r '.l4t_version[]?')
        rootfs_types=$(echo "$comp" | jq -r '.rootfs_type[]?')

        # Match individual fields
        device_match=$(echo "$devices" | grep -qx "$target_device" && echo "true" || echo "false")
        storage_match=$(echo "$storages" | grep -qx "$storage" && echo "true" || echo "false")
        board_match=$(echo "$boards" | grep -qx "$hwrev" && echo "true" || echo "false")
        board_expansion_match=$(echo "$board_expansions" | grep -qx "$board_expansion" || [ -z "$board_expansions" ] && echo "true" || echo "false")
        l4t_match=$(echo "$l4t_versions" | grep -qx "$jetpack_version" && echo "true" || echo "false")
        rootfs_match=$(echo "$rootfs_types" | grep -qx "$rootfs_type" || [ -z "$rootfs_types" ] && echo "true" || echo "false")

        # if any of the fields are "" set them to true
        device_match=$(echo "$devices" | grep -qx "" && echo "true" || echo "$device_match")
        storage_match=$(echo "$storages" | grep -qx "" && echo "true" || echo "$storage_match")
        board_match=$(echo "$boards" | grep -qx "" && echo "true" || echo "$board_match")
        board_expansion_match=$(echo "$board_expansions" | grep -qx "" && echo "true" || echo "$board_expansion_match")
        l4t_match=$(echo "$l4t_versions" | grep -qx "" && echo "true" || echo "$l4t_match")
        rootfs_match=$(echo "$rootfs_types" | grep -qx "" && echo "true" || echo "$rootfs_match")

        # Check compatibility
        if [[ $device_match == "true" ]] &&
           [[ $storage_match == "true" ]] &&
           [[ $board_match == "true" ]] &&
           [[ $board_expansion_match == "true" ]] &&
           [[ $l4t_match == "true" ]] &&
           [[ $rootfs_match == "true" ]]; then
            is_compatible=true
            break
        fi
    done < <(jq -c '.[]' "$patch_dir/compatible")

    if $is_compatible; then
        echo "Patch in $patch_dir is compatible."
        return 0
    else
        echo "Patch in $patch_dir is not compatible."
        return 1
    fi
}

add_service() {
    local service_name=$1
    local service_path=$2
    local service_bin_name=$3
    local service_bin_path=$4

    sudo cp $service_path ${service_destination}/
    add_service_to_json "/etc/systemd/system/${service_name}"

    sudo cp $service_bin_path/$service_bin_name ${bin_destination}/
    sudo chmod +x ${bin_destination}/${service_bin_name}
    add_binary_to_json "/usr/local/bin/${service_bin_name}"

    # Add to tmp hardware service
    echo "sudo systemctl enable $service_name" >> $tmp_script_path
}

add_udev() {
    local udev_name=$1
    local udev_path=$2

    sudo cp $udev_path ${udev_destination}/
    add_udev_to_json "/etc/udev/rules.d/${udev_name}"
}

add_deb() {
    local deb_name=$1     # The name of the .deb package (e.g., package_name.deb)
    local deb_path=$2     # The full path to the .deb package

    # Perform cross-architecture installation into the L4T rootfs
    echo "Installing $deb_name into ${L4T_rootfs_path}/"
    sudo dpkg --root="${L4T_rootfs_path}" --force-architecture -i "$deb_path"

    # Check if the installation succeeded
    if [[ $? -ne 0 ]]; then
        echo "Error: Failed to install $deb_name into ${L4T_rootfs_path}/"
        exit 1
    fi

    # Add the package name to the JSON tracking file
    add_deb_to_json "$deb_name"
    echo "Successfully installed $deb_name into ${L4T_rootfs_path}/"
}

add_docs()
{
    local docs_name=$1
    local docs_path=$2

    sudo cp $docs_path ${docs_destination}/
    add_binary_to_json "/home/dcs_user/Airvolute/docs/${docs_name}"
}

# Initialize the JSON file
initialize_json_file

# Initialize the tmp hardware service
if [ -f $tmp_script_path ]; then
    rm $tmp_script_path
fi
touch $tmp_script_path && chmod +x $tmp_script_path

# Add content to tmp hardware service
echo "#!/bin/bash" >> $tmp_script_path

##### Add hardware support layer #####

# Iterate over patches in the resources folder
patches_dirs=$(find "$resources_path" -mindepth 1 -maxdepth 2 -type d)
for patch_dir in $patches_dirs; do
    echo "Checking patch: $patch_dir"

    if [[ -d $patch_dir ]]; then
        # Check compatibility for each patch
        if check_patch_compatibility "$patch_dir" "$target_device" "$jetpack_version" "$hwrev" "$board_expansion" "$storage" "$rootfs_type"; then
   
            # Check if the patch is service, the path should contain a services folder
            if [[ $patch_dir == *"services"* ]]; then
                echo "Adding service patch: $patch_dir"

                service_name=$(basename "$patch_dir")".service"
                service_path="$patch_dir/$service_name"
                
                base_name=$(basename "$patch_dir")
                if [ -f "$patch_dir/$base_name.py" ]; then
                    binary_name="$base_name.py"
                    binary_path="$patch_dir/$binary_name"
                elif [ -f "$patch_dir/$base_name.sh" ]; then
                    binary_name="$base_name.sh"
                    binary_path="$patch_dir/$binary_name"
                else
                    echo "Error: No .sh or .py file found for $base_name in $patch_dir"
                    exit 1
                fi
                
                if [[ -f $service_path ]] && [[ -f $binary_path ]]; then
                    add_service "$service_name" "$service_path" "$binary_name" "$patch_dir"
                else
                    echo "Skipping patch: $patch_dir"
                fi
            elif [[ $patch_dir == *"udevs"* ]]; then
                echo "Adding udev patch: $patch_dir"
                # Get the udev name .rules
                udev_name=$(find "$patch_dir" -maxdepth 1 -type f -name "*.rules" -exec basename {} \;)
                udev_path="$patch_dir/$udev_name"

                if [[ -f $udev_path ]]; then
                    add_udev "$udev_name" "$udev_path"
                else
                   echo "Skipping patch: $patch_dir"
                fi
            elif [[ $patch_dir == *"debs"* ]]; then
                echo "Adding deb patch: $patch_dir"
                deb_name=$(find "$patch_dir" -maxdepth 1 -type f -name "*.deb" -exec basename {} \;)
                deb_path="$patch_dir/$deb_name"

                if [[ -f $deb_path ]]; then
                    add_deb "$deb_name" "$deb_path"
                else
                    echo "Skipping patch: $patch_dir"
                fi
            elif [[ $patch_dir == *"utilities"* ]]; then
                echo "Adding utility patch: $patch_dir"
                script_name=$(find "$patch_dir" -maxdepth 1 -type f ! -name "compatible" -exec basename {} \;)
                script_path="$patch_dir/$script_name"
                
                if [[ -f $script_path ]]; then
                    if [[ ! -d $util_destination ]]; then
                        sudo mkdir -p $util_destination
                    fi

                    sudo cp $script_path $util_destination/
                    sudo chmod +x $util_destination/$script_name
                    add_binary_to_json "$util_device_folder/$script_name"
                else
                    echo "Skipping patch: $patch_dir"
                fi
            elif [[ $patch_dir == *"apply"* ]]; then
                echo "Applying patch: $patch_dir"
                
                # Get script
                script_name=$(find "$patch_dir" -maxdepth 1 -type f ! -name "compatible" -exec basename {} \;)
                script_path="$patch_dir/$script_name"
                if [[ -f $script_path ]]; then
                    echo "Applying patch: $script_path"
                    # Check result of the script


                    sudo bash $script_path $L4T_rootfs_path $target_device $jetpack_version $hwrev $board_expansion $storage $rootfs_type
                else
                    echo "Skipping patch: $patch_dir"
                fi 
            elif [[ $patch_dir == *"docs"* ]]; then
                echo "Applying patch: $patch_dir"
                
                # Get script
                script_name=$(find "$patch_dir" -maxdepth 1 -type f ! -name "compatible" -exec basename {} \;)
                script_path="$patch_dir/$script_name"
                if [[ -f $script_path ]]; then
                    echo "Applying patch: $script_path"

                    # Check result of the script
                    add_docs "$script_name" "$script_path"
                else
                    echo "Skipping patch: $patch_dir"
                fi
            fi
        else
            echo "Skipping patch: $patch_dir"
        fi
    fi
done

##### End of Add hardware support layer #####

# Add the tmp hardware service to JSON and copy to rootfs
service_bin_name="handle_hardware_services.sh"

sudo cp $tmp_script_path $bin_destination/
sudo chmod +x $bin_destination/$service_bin_name
add_binary_to_json "/usr/local/bin/$service_bin_name"
