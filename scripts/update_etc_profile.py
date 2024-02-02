import sys


def update_or_add_line(lines, pattern, new_line):
    """
    Update an existing line that starts with a given pattern, or add the line if the pattern is not found.
    """
    for i, line in enumerate(lines):
        if line.startswith(pattern):
            lines[i] = new_line
            return
    lines.append(new_line)

def update_etc_profile(etc_profile_path, mav_sys_id, uav_doodle_ip=None, doodle_radio_ip=None):
    """
    Update or add specific environment variable exports in a given profile file.
    """
    # Read the current contents of the file
    with open(etc_profile_path, 'r') as file:
        lines = file.readlines()

    # Update or add the MAV_SYS_ID line
    update_or_add_line(lines, 'export MAV_SYS_ID', f'export MAV_SYS_ID={mav_sys_id}\n')

    if uav_doodle_ip:
        # Update or add the UAV_DOODLE_IP line
        update_or_add_line(lines, 'export UAV_DOODLE_IP', f'export UAV_DOODLE_IP={uav_doodle_ip}\n')

    if doodle_radio_ip:
        # Update or add the DOODLE_RADIO_IP line
        update_or_add_line(lines, 'export DOODLE_RADIO_IP', f'export DOODLE_RADIO_IP={doodle_radio_ip}\n')

    # Write the updated contents back to the file
    with open(etc_profile_path, 'w') as file:
        file.writelines(lines)

if __name__ == "__main__":
    if len(sys.argv) < 5:
        print("Usage: python3 update_etc_profile.py <etc_profile_path> <mav_sys_id> [<uav_doodle_ip> <doodle_radio_ip>]")
        sys.exit(1)

    etc_profile_path = sys.argv[1]
    mav_sys_id = sys.argv[2]
    uav_doodle_ip = sys.argv[3] if len(sys.argv) > 3 else None
    doodle_radio_ip = sys.argv[4] if len(sys.argv) > 4 else None
    update_etc_profile(etc_profile_path, mav_sys_id, uav_doodle_ip, doodle_radio_ip)