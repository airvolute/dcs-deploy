all_states= {
            "extract_l4t": 0,
            "extract_rootfs": 0,
            "apply_binaries": 0,
            "extract_airvolute_overlay": 0,
            "apply_binaries_t": 0,
            "creating_default_user": 0,
            "extract_nv_ota_tools": 0,
            "install_local_overlay@dcs_first_boot": 0,
            "install_local_overlay@hardware_support_layer": 0,
            "install_local_overlay@save_version.sh": 0
}

def check_overlay_states_match(states: dict, prefix: str, expected_suffixes: list[str]) -> bool:
    """
    Checks if all state keys with the given prefix match exactly the expected suffixes.

    :param states: Dictionary containing current state keys.
    :param prefix: Prefix to filter keys, e.g. "install_local_overlay@".
    :param expected_suffixes: List of expected suffixes, e.g. ["dcs_first_boot", "hardware_support_layer"]
    :return: True if all prefixed keys match the expected suffixes, False otherwise.
    """
    # Extract suffixes of keys with the given prefix
    found_suffixes = [key[len(prefix):] for key in states if key.startswith(prefix)]
    print(found_suffixes)
    # Compare as sets, since order doesn't matter
    return set(expected_suffixes) - set(found_suffixes)

ret = check_overlay_states_match(all_states,"install_local_overlay@", ["dcs_first_boot", "hardware_support_layer", "save_version.sh", "vla"])

print(ret)
