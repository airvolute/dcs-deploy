#!/usr/bin/env python3

import subprocess

#flash_path = os.path.join(self.dsc_deploy_root, 'flash', config_relative_path)
#l4t_root_dir = os.path.join(flash_path, 'Linux_for_Tegra')
#create_user_script_path = os.path.join(l4t_root_dir, 'tools', 'l4t_create_default_user.sh')
create_user_script_path = '/media/data/work/.dcs_deploy/flash/xavier_nx_nvme_1.2_512_bone300/Linux_for_Tegra/tools/l4t_create_default_user.sh'

# example: retcode = cmd_exec("sudo tar xpf %s --directory %s" % (self.rootfs_file_path, self.rootfs_extract_dir))
def cmd_exec(command_line:str, print_command = False) -> int:
    if print_command:
        print("calling: " + command_line)
    try:
        return subprocess.call(command_line, shell=True)
    except Exception as e:
        print("Command %s execution failed!!. Error %s" % (command_line, str(e)))
        print("Exitting!")
        exit(5)
        
ret = cmd_exec("sudo " + create_user_script_path + " -u dcs_user -p dronecore -n dcs --accept-license")
print(f"ret={ret}")
print("finished..")
