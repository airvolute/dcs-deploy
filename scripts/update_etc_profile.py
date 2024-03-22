import sys


def update_or_add_line(lines, pattern, new_line=None):
    """
    Update an existing line that starts with a given pattern, add the line if the pattern is not found,
    or remove the line if new_line is None.
    """
    updated_lines = []  # Initialize an empty list to hold updated lines
    line_found = False  # Flag to track if the line was found and updated/removed

    for line in lines:
        if line.startswith(pattern):
            line_found = True
            if new_line is not None:  # Update the line if new_line is provided
                updated_lines.append(new_line)
        else:
            updated_lines.append(line)  # Keep the line if it doesn't match the pattern

    if not line_found and new_line is not None:
        updated_lines.append(new_line)  # Add the new line if the pattern was not found

    return updated_lines  # Return the updated list of lines


def update_etc_profile(etc_profile_path, mav_sys_id, uav_doodle_ip=None, doodle_radio_ip=None):
    """
    Update or add specific environment variable exports in a given profile file.
    Remove the lines if uav_doodle_ip or doodle_radio_ip is None.
    """
    # Read the current contents of the file
    with open(etc_profile_path, 'r') as file:
        lines = file.readlines()

    # Always update or add the MAV_SYS_ID line
    lines = update_or_add_line(lines, 'export MAV_SYS_ID', f'export MAV_SYS_ID={mav_sys_id}\n')

    # Update, add, or remove the UAV_DOODLE_IP line based on uav_doodle_ip value
    lines = update_or_add_line(lines, 'export UAV_DOODLE_IP', f'export UAV_DOODLE_IP={uav_doodle_ip}\n' if uav_doodle_ip else None)

    # Update, add, or remove the DOODLE_RADIO_IP line based on doodle_radio_ip value
    lines = update_or_add_line(lines, 'export DOODLE_RADIO_IP', f'export DOODLE_RADIO_IP={doodle_radio_ip}\n' if doodle_radio_ip else None)

    # Write the updated contents back to the file
    with open(etc_profile_path, 'w') as file:
        file.writelines(lines)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python3 update_etc_profile.py <etc_profile_path> <mav_sys_id> [<uav_doodle_ip> <doodle_radio_ip>]")
        sys.exit(1)

    etc_profile_path = sys.argv[1]
    mav_sys_id = sys.argv[2]
    uav_doodle_ip = sys.argv[3] if len(sys.argv) > 3 else None
    doodle_radio_ip = sys.argv[4] if len(sys.argv) > 4 else None
    update_etc_profile(etc_profile_path, mav_sys_id, uav_doodle_ip, doodle_radio_ip)