#!/usr/bin/env python3

import argparse
import json
import subprocess
import os
import wget
from threading import Thread, Event
import time
from urllib.parse import urlparse
import sys as _sys

dcs_deploy_version = "0.1.0"


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

def check_and_create_symlink(link_path, target_path):
    """
    Check if a symbolic link exists at link_path and points to target_path.
    If it does not exist or points to a different target, create or update the symlink using sudo.
    """
    # Check if the link already exists
    if os.path.islink(link_path):
        # Check if the existing link points to the correct target
        current_target = os.readlink(link_path)
        if current_target == target_path:
            print(f"Symlink already exists and points to the correct target: {target_path}")
            return 0  # Assuming 0 is your success return code
        else:
            # The link exists but points to a different target, remove it
            print(f"Symlink exists but points to a different target. Removing it.")
            remove_cmd = f"sudo rm {link_path}"
            remove_ret = cmd_exec(remove_cmd)
            if remove_ret != 0:
                print(f"Failed to remove existing symlink: {link_path}")
                return remove_ret

    # Proceed to create the symlink
    create_cmd = f"sudo ln -s {target_path} {link_path}"
    create_ret = cmd_exec(create_cmd)
    if create_ret == 0:
        print(f"Symlink created/updated successfully: {link_path} -> {target_path}")
    else:
        print(f"Failed to create symlink: {link_path} -> {target_path}")
    return create_ret

def extract(source_file_path:str, destination_path:str) -> int:
    if "tbz2" in source_file_path or "tar.bz2" in source_file_path:
        return cmd_exec("sudo tar xpf " + source_file_path + " --directory " + destination_path + " -I lbzip2")
    else:
        return cmd_exec("sudo tar xpf " + source_file_path + " --directory " + destination_path)

def cmd_exist(name: str) -> bool:
    """Check whether command `name` exist in system"""
    return cmd_exec("which " + name + " > /dev/null") == 0

def package_installed(name:str) -> bool:
    return cmd_exec("dpkg -l " + name + "> /dev/null 2>&1") == 0

def yes_no_question(question):
    yes_choices = ['yes', 'y']
    no_choices = ['no', 'n']

    while True:
        user_input = input(question + "([y]es/[N]o): ")
        if user_input.lower() in yes_choices:
            return True
        elif user_input.lower() in no_choices:
            return False
        elif user_input == "":
            return False
        else:
            print('Type yes or no')

class ProcessingStatus:
    def __init__(self, status_file_name:str, initial_group:str = "general", default_identifier:list = None):
        self.group = initial_group
        self.status_file_name = status_file_name
        self.current_identifier = default_identifier
        self.load()

    def load(self):
        if os.path.isfile(self.status_file_name):
            with open(self.status_file_name, "r") as status_file:
                self.status = json.load(status_file)
        else:
            self.status = {}
        self._init_identifier()
        self._init_group_status()
    
    def _init_identifier(self):
        if "identifier" in self.status:
            self.prev_identifier = self.status["identifier"]
        else:
            self.prev_identifier = []
        
        if self.current_identifier == None:
            self.status["identifier"] = _sys.argv[1:]
        else:
            self.status["identifier"] = self.current_identifier
        print("identifier: %s" % str(self.status["identifier"]))
        print("prev_identifier: %s" % str(self.prev_identifier))

    def _init_group_status(self, group = None):
        if group == None:
            group = self.group
        if group in self.status:
            return
        self.status[group] = {
            "status" : False,
            "last_processing_step" : "",
            "states": {}
        }

    def save(self):
        with open(self.status_file_name, "w") as status_file:
            json.dump(self.status, status_file,  indent = 4)
    
    def get_prev_identifier(self):
        return self.prev_identifier
    
    def get_identifier(self):
        return self.status["identifier"]
    
    def _remove_identifier(self, identifier, remove_list):
        if remove_list == []:
            return identifier
        # Remove not matching identifiers
        cleaned_identifier = identifier[:] # Copy identifiers into new list
        for remove in remove_list:
            if remove in cleaned_identifier:
                cleaned_identifier.remove(remove)

        return cleaned_identifier

    def is_identifier_same_as_prev(self, no_match_list=[]):
        identifier = self._remove_identifier(self.status["identifier"], no_match_list)
        prev_identifier = self._remove_identifier(self.prev_identifier, no_match_list)
        if len(identifier) != len(prev_identifier):
            return False
        if len(set(identifier).difference(set(prev_identifier))) != 0:
            print("identifier not same as previous!")
            return False
        return True

    def change_group(self, group):
        self.group = group
        if not group in self.status:
            self._init_group_status()

    def set_processing_step(self, processing_step_name:str):
        self.last_processing_step = processing_step_name
        self.status[self.group]["last_processing_step"] = processing_step_name
        self.status[self.group]["states"][processing_step_name] = -1
        self.status[self.group]["status"] = False
        self.save()

    def set_status(self, status:int, processing_step_name:str = None, last_step = False):
        if processing_step_name == None:
            processing_step_name = self.last_processing_step
        states = self.status[self.group]["states"]
        states[processing_step_name] = status
        if last_step == True:
            # Check all status codes
            self.check_status()
        self.save()
    
    def check_status(self, group = None):
        if group == None:
            group = self.group
        states = self.status[group]["states"]
        self.status[group]["status"] = True
        for key in states:
            if states[key] != 0:
                self.status[group]["status"] = False
                break
    
    def get_status(self, group = None):
        # Check if configuration was deleled. If yes, reload default configuration
        if not os.path.isfile(self.status_file_name):
            self.load()

        if group == None:
            group = self.group
        return self.status[group]["status"]

class BatchCounter:
    def __init__(self, counter_file_path:str, counter_value:int = 0):
        try:
            counter_value = int(counter_value)
        except ValueError:
                raise ValueError(f"Invalid counter_value: {counter_value}. Must be an integer.")
        
        if (counter_value < 1 or counter_value > 254) and (counter_value != 0):
            print('Invalid counter value! Counter value must be between 1 and 254.')
            exit()
        self.counter_file_path = counter_file_path

        # Check if the file exists
        if not os.path.isfile(self.counter_file_path):
            # If counter_value is within the desired range, use it; otherwise, default to 1
            self.counter = counter_value if 1 <= counter_value <= 254 else 1
            with open(self.counter_file_path, 'w') as file:
                # Write the initial counter value to the file
                file.write(str(self.counter))
                print("Batch counter file created.")
        else:
            with open(self.counter_file_path, 'r') as file:
                stored_value = file.read()
                try:
                    stored_value = int(stored_value)
                    # If counter_value is within the desired range, use it;
                    # otherwise, use the value read from the file
                    self.counter = counter_value if 1 <= counter_value <= 254 else stored_value
                except ValueError:
                    self.counter = 1
                    print("Warning: Batch counter file was corrupt or empty, resetting to 1.")

        # This ensures that even if the file exists and counter_value is within the desired range,
        # the counter is set accordingly and saved to the file.
        if 1 <= counter_value <= 254:
            self.save()
        print(f"Jetson is going to be flashed with ID: {self.counter}.")
        
    def increment(self):
        if self.counter < 254:
            self.counter += 1
        else:
            print("Batch counter has reached its maximum value. Resetting to 1.")
            self.counter = 1
        self.save()

    def save(self):
        with open(self.counter_file_path, 'w') as file:
            file.write(str(self.counter))

class DcsDeploy:
    def __init__(self):
        self.check_dependencies()
        self.parser = self.create_parser()
        self.args = self.parser.parse_args()
        self.process_optional_args()
        self.sanitize_args()
        self.selected_config_name = None
        self.load_db()
        if self.args.command != 'list':
            self.load_selected_config()
            self.init_filesystem()
            self.check_optional_arguments()

            if self.args.batch_counter is not None:
                self.batch_counter = BatchCounter(
                    os.path.join(self.flash_path, "batch_counter"), 
                    counter_value=self.args.batch_counter
                )
            else:
                self.batch_counter = BatchCounter(os.path.join(self.flash_path, "batch_counter"))

    def add_common_parser(self, subparser):
        target_device_help = 'REQUIRED. Which type of device are we setting up. Options: [xavier_nx]'
        subparser.add_argument('target_device', help=target_device_help)

        jetpack_help = 'REQUIRED. Which jetpack are we going to use. Options: [51].'
        subparser.add_argument('jetpack', help=jetpack_help)

        hwrev_help = 'REQUIRED. Which hardware revision of carrier board are we going to use. Options: [1.2].'
        subparser.add_argument('hwrev', help=hwrev_help)
        
        storage_help = 'REQUIRED. Which storage medium are we going to use. Options: [emmc, nvme].'
        subparser.add_argument('storage', help=storage_help)

        rootfs_type_help = 'REQUIRED. Which rootfs type are we going to use. Options: [minimal, full].'
        subparser.add_argument('rootfs_type', help=rootfs_type_help)
        
        force_help = 'Files will be deleted, downloaded and extracted again.'
        subparser.add_argument('--force', action='store_true', help=force_help)

        regen_help = 'Regenerate files. Extract resources and apply them again'
        subparser.add_argument('--regen', action='store_true', help=regen_help)

        ab_partition_help = 'Prepare ab partion for system update. Only available for nvme devices'
        subparser.add_argument('--ab_partition', action='store_true', help=ab_partition_help)

        opt_app_size_help = 'Set APP partition size in GB. Use when you get "No space left on device" error while flashing custom rootfs'
        subparser.add_argument('--app_size', help=opt_app_size_help)

        rootfs_help = 'Path to customized root filesystem. Keep in mind that this needs to be a valid tbz2 archive.' 
        subparser.add_argument('--rootfs', help=rootfs_help)

        doodle_radio_setup_help = 'Enable OEM setup for doodle radios. Format: <doodle_radio_ip>' 
        subparser.add_argument(
            '--setup_doodle_radio', help=doodle_radio_setup_help)
        
        batch_counter_help = '''
            Counter for batch flashing. It is used to keep track of the number of devices flashed in a single batch.
            It can be set to any value between 1 and 254. If not set, the counter defaults to 1. Counter is incremented
            after each successfuly flashed device. If the counter reaches 254, it is reset to 1.
            '''
        subparser.add_argument('--batch_counter', help=batch_counter_help)

    def create_parser(self):
        """
        Create an ArgumentParser and all its options
        """
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='command', help='Command')

        list = subparsers.add_parser(
            'list', help='list available versions')

        flash = subparsers.add_parser(
            'flash', help='Run the entire flash process')
        
        self.add_common_parser(flash)

        parser.add_argument('--version', action='store_true',  default='', help="Show version")
        
        return parser

    def check_optional_arguments(self):
        if self.args.ab_partition == True and self.config['storage'] != 'nvme':
            print("AB partition is allowed only for nvme devices! (%s)" % self.config['storage'])
            print("Exitting!")
            exit(6)

        if self.args.rootfs is not None and self.args.app_size is None:
            print('''
                  WARNING! You did not specify --app_size parameter. 
                  You may get 'No space left on device' error while flashing custom rootfs.
                  ''')
            user_input = input("Do you want to continue? [Y/n]: ")
            if user_input.lower() == 'n':
                print("Exiting!")
                exit(6)

    def process_optional_args(self):
        if self.args.version == True:
            print("dcs_deploy version: " + dcs_deploy_version)
            exit(0)
    
    def sanitize_args(self):
        """
        Check if the supplied arguments are valid and perform some fixes
        """
        if self.args.command is None:
            print("No command specified!")
            self.parser.print_usage()
            quit()

    def load_db(self):
        """ 
        Load db from server. 
        Warning! currently it is local file!
        """
        try:
            db_file = open('local/config_db.json')
        except Exception as e:
            print("could not open local/config_db.json!" + str(e))
            print("exitting!")
            exit(2)

        self.config_db = json.load(db_file)
        # Unify specific parameters into list
        update_to_list_fields = ['device', 'board', 'storage']
        required_variables = ['storage', 'board', 'l4t_version', 'nvidia_overlay', 'airvolute_overlay', 'l4t', 'nv_ota_tools', 'rootfs', 'rootfs_type']
        for key in self.config_db:
                if not all(variable in self.config_db[key] for variable in required_variables):
                    print(f"The key {key} does not contain all the required variables. Database corrupted. Exiting.")
                    exit(1)
        for config in self.config_db:
            for update_field in update_to_list_fields:
                if (type(self.config_db[config][update_field]) is not list):
                    self.config_db[config][update_field] = [self.config_db[config][update_field]]
                
    def loading_animation(self, event):
        """Just animate rotating line - | / — \
        """
        cnt = 0

        while True:
            if cnt == 0:
                print ("\r | ", end="")
            elif cnt == 1:  
                print ("\r / ", end="")
            elif cnt == 2:
                print ("\r — ", end="")
            elif cnt == 3:
                print ("\r \\ ", end="")

            cnt += 1
            cnt %= 4
            time.sleep(0.5)
            
            if event.is_set():
                print()
                return

    def run_loading_animation(self, event):
        t = Thread(target=self.loading_animation, args=(event,))
        t.start()
        return t
    
    def get_download_file_path(self, url:str) -> str:
        if url == None:
            return ""
        path = self.download_path
        u = urlparse(url)
        path += "/" + u.hostname
        replace_str = "/download"
        if "downloads" in u.path:
            replace_str = "/downloads"
        path += u.path.replace(replace_str, '')
        return path

    def cleanup_old_download_dir(self):
        old_download_dir = self.config['device'] + '_' + self.config['storage'] + '_' + self.config['board'] + '_'
        
        for dir in [f for f in os.listdir(self.download_path) if not os.path.isfile(f)]:
            if old_download_dir in dir:
                del_dir = self.download_path + "/" + dir
                print("download dir to delete: " + del_dir)
                cmd_exec("rm -rf " + del_dir)

    def init_filesystem(self):
        config_relative_path = (
            self.config['device'] + '_' + 
            self.config['storage'] + '_' + 
            self.config['board'] + '_' +
            self.config['l4t_version'] + '_' +
            self.config['rootfs_type']
        )

        self.home = os.path.expanduser('~')
        self.dsc_deploy_root = os.path.join(self.home, '.dcs_deploy')
        self.download_path = os.path.join(self.dsc_deploy_root, 'download')
        self.flash_path = os.path.join(self.dsc_deploy_root, 'flash', config_relative_path)
        self.rootfs_extract_dir = os.path.join(self.flash_path, 'Linux_for_Tegra', 'rootfs')
        self.l4t_root_dir = os.path.join(self.flash_path, 'Linux_for_Tegra')
        self.apply_binaries_path = os.path.join(self.l4t_root_dir, 'apply_binaries.sh')
        self.create_user_script_path = os.path.join(self.l4t_root_dir, 'tools', 'l4t_create_default_user.sh')
        self.first_boot_file_path = os.path.join(self.rootfs_extract_dir, 'etc', 'first_boot')

        # Generate download resource paths
        resource_keys = ["rootfs", "l4t","nvidia_overlay", "airvolute_overlay", "nv_ota_tools"]
        self.resource_paths = {}

        for res_name in resource_keys:
            #print(" %s key: %s" % (res_name, self.config[res_name]))
            if res_name == "rootfs" and self.args.rootfs is not None:
                print(self.args.rootfs)
                self.resource_paths[res_name] = self.args.rootfs
                continue
            self.resource_paths[res_name] = self.get_download_file_path(self.get_resource_url(res_name))

        if not os.path.isdir(self.download_path):
            os.makedirs(self.download_path)

        # Remove old download directories
        self.cleanup_old_download_dir()

        if self.config['device'] == 'xavier_nx': 
            self.device_type = 't194'

        # Handle dcs-deploy root dir
        if not os.path.isdir(self.dsc_deploy_root):
            os.mkdir(self.dsc_deploy_root)

        # Create dcs-deploy download dir
        for key in self.resource_paths:
            if self.resource_paths[key] == "":
                continue
            if not os.path.isdir(os.path.dirname(self.resource_paths[key])):
                print("Creating directory: ",self.resource_paths[key])
                os.makedirs(os.path.dirname(self.resource_paths[key]))

        # Handle dcs-deploy flash dir
        if not os.path.isdir(self.flash_path):
            os.makedirs(self.flash_path)
        elif self.args.force == True or self.args.regen == True:
            print('Removing previous L4T folder ...')
            self.cleanup_flash_dir()

        self.prepare_status = ProcessingStatus(os.path.join(self.flash_path, "prepare_status.json"), initial_group="prepare")
    
    def cleanup_flash_dir(self):
            prepare_status_path = os.path.join(self.flash_path, "prepare_status.json")
            print("cleanup_flash_dir...")
            cmd_exec(f"sudo rm -rf {self.l4t_root_dir} && sync")
            cmd_exec(f"rm {prepare_status_path} && sync")

    def check_dependencies(self):
        l4t_tool = ["abootimg", "binfmt-support", "binutils", "cpp", "device-tree-compiler", "dosfstools", "lbzip2",
                     "libxml2-utils", "nfs-kernel-server", "python3", "python3-yaml", "qemu-user-static", "sshpass",
                     "udev", "uuid-runtime", "whois", "openssl", "cpio", "lz4"]
        l4t_other_dependencies = ["python-is-python3"]
        dcs_deploy_dependencies = ["qemu-user-static", "sshpass", "abootimg", "lbzip2"]
        
        dependencies = l4t_tool
        # Append dcs_deploy_dependencies which are unique
        for dependency in dcs_deploy_dependencies + l4t_other_dependencies:
            if dependency not in dependencies:
                dependencies.append(dependency)
        
        to_install = []
        for dependency in dependencies:
            if package_installed(dependency) == False:
                to_install.append(dependency)

        if len(to_install) != 0:
            print("please install %s tools. eg: sudo apt-get install -y %s" % (to_install, " ".join(to_install)))
            print("exitting!")
            exit(1)
        return 0


    def get_missing_resources(self, force_all_missing = False):
        res = []
        for resouce in self.resource_paths:
            if os.path.isfile(self.resource_paths[resouce]) and force_all_missing == False:
                continue
            # Return only resource which is possible to download
            if(self.get_resource_url(resouce) != None):
                res += [resouce]
        return res

    def download_resources(self):
        for missing_resource in self.get_missing_resources(force_all_missing = self.args.force):
            if missing_resource == "rootfs" and self.args.rootfs is not None:
                if not os.path.isfile(self.args.rootfs):
                    print("The file specified in --rootfs does not exist: %s" % self.args.rootfs)
                    exit(6)
                print("rootfs will not be downloaded, because you want to use custom rootfs.")
                continue
            print("missing resource '%s'. Going to download it!" % missing_resource)
            ret = self.download_resource(missing_resource, self.resource_paths[missing_resource])
            if ret < 0:
                print("can't download resource '" + missing_resource + "'!.")
                print("exitting!")
                exit(4)
            # Regenerate
            self.cleanup_flash_dir()
        print('Resources for your config are already downloaded!')
        return True

    def get_resource_url(self, resource_name):
        url = self.config[resource_name]
        if url == None or url == "none" or url == "":
            return None
        return url

    def download_resource(self, resource_name, dst_path):
        if resource_name  not in self.config:
            return 1
        if self.get_resource_url(resource_name) == None:
            print("Skipping downloading resource" + resource_name)
            return 2
        print("Downloading %s:" % resource_name)
        # Remove any existing temporary files
        cmd_exec("rm -f " + dst_path + "*.tmp")

        # Check if file already exist
        if os.path.isfile(dst_path) and self.args.force == False:
            yes = yes_no_question("Downloaded file %s already exist! Would you like to download it again? " % dst_path)
            if yes == False:
                return 0
        if os.path.isfile(dst_path):
            print("removing existing file! " + dst_path)
            cmd_exec(f"rm '{dst_path}'", print_command=True)
        try:
            wget.download(
                self.config[resource_name],
                dst_path
            )
        except Exception as e:
            print("Got error while downloading resource", resource_name, "Error: ", str(e))
            print("download params: %s, %s" %(self.config[resource_name], dst_path))
            return -1
        print()
        return 0

    def extract_resource(self, resource, extract_path = None, need_sudo = False):
        if extract_path == None:
            extract_path = self.flash_path
        stop_event = Event()
        print('Extracting ' + resource + " ... (" + self.resource_paths[resource] + ")" )
        self.prepare_status.set_processing_step("extract_" + resource)
        if need_sudo:
            print('This part needs sudo privilegies:')
            # Run sudo identification
            cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        stop_event.clear()
        l4t_animation_thread = self.run_loading_animation(stop_event)
        ret = extract(self.resource_paths[resource], extract_path)
        self.prepare_status.set_status(ret)
        stop_event.set()
        l4t_animation_thread.join()
        return ret
    
    def prepare_sources_mandatory(self, ret=0):
        # Regenerate ssh access in rootfs
        print("Purging ssh keys, this part needs sudo privilegies:")
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        ret += cmd_exec("sudo resources/purge_ssh_keys.sh " + 
                 os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user','.ssh'))
        self.networking_setup()
        
        # Set default power mode to max
        print("Setting up power mode, this part needs sudo privilegies:")
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        if self.args.target_device == 'xavier_nx':
            ret += cmd_exec("sudo python scripts/set_default_powermode.py " +
                            os.path.join(self.rootfs_extract_dir, 'etc', 'nvpmodel', 'nvpmodel_t194_p3668.conf') +
                            " 8")
        if self.args.target_device == 'orin_nx':
            # TODO: find nvpmodel.conf file for Orin and it's specific high power mode
            print('Default power mode for Orin NX is not implemented yet.')

    def prepare_sources_production(self):
        if self.prepare_status.get_status() == True:
            self.prepare_sources_mandatory()
            print("Binaries already prepared!. Skipping!")
            return 0
        else:
            self.cleanup_flash_dir()
            self.prepare_status.load()

        # Extract Linux For Tegra
        self.extract_resource("l4t")
        # Extract Root Filesystem
        self.extract_resource("rootfs", self.rootfs_extract_dir, need_sudo=True)
        # Extract Nvidia overlay if needed
        if self.get_resource_url('nvidia_overlay') != None:
            print('Applying Nvidia overlay ...')
            self.prepare_nvidia_overlay()

        # Apply binaries
        print('Applying binaries ...')
        print('This part needs sudo privilegies:')
        # Run sudo identification
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        
        self.prepare_status.set_processing_step("apply_binaries")
        ret = cmd_exec("/usr/bin/sudo " + self.apply_binaries_path)
        self.prepare_status.set_status(ret)

        print('Applying Airvolute overlay ...')
        self.prepare_airvolute_overlay()
        
        self.prepare_status.set_processing_step("apply_binaries_t")
        ret = cmd_exec("/usr/bin/sudo " + self.apply_binaries_path + " -t False")
        self.prepare_status.set_status(ret)

        print('Creating default user ...')
        self.prepare_status.set_processing_step("creating_default_user")
        ret = cmd_exec("sudo " + self.create_user_script_path + " -u dcs_user -p dronecore -n dcs --accept-license")
        self.prepare_status.set_status(ret)

        if self.get_resource_url('nv_ota_tools') != None:
            print('Applying Nvidia OTA tools ...')
            ret = self.extract_resource('nv_ota_tools')

        self.prepare_sources_mandatory()

        self.prepare_status.set_processing_step("install_first_boot_setup")
        ret = self.install_first_boot_setup()
        self.prepare_status.set_status(ret, last_step = True)

    def prepare_airvolute_overlay(self):
        return self.extract_resource('airvolute_overlay')

    def prepare_nvidia_overlay(self):
        return self.extract_resource('nvidia_overlay')

    def networking_setup(self, ret=0):
        dcs_user_home_destination = os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user')
        etc_profile_destination = os.path.join(self.rootfs_extract_dir, 'etc', 'profile')
        
        print("Setting up networking, this part needs sudo privilegies:")
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")

        if self.args.setup_doodle_radio is not None:
            uav_static_ip = "10.223.0." + str(self.batch_counter.counter)
            command = f"sudo python scripts/update_etc_profile.py '{etc_profile_destination}' '{self.batch_counter.counter}' '{uav_static_ip}' '{self.args.setup_doodle_radio}'"
            ret += cmd_exec("sudo cp -r resources/airvolute-doodle-setup " + dcs_user_home_destination)
        else:
            command = f"sudo python scripts/update_etc_profile.py '{etc_profile_destination}' '{self.batch_counter.counter}'"
            
        ret += cmd_exec(command)

    def install_first_boot_setup(self):
        """
        Installs script that would be run on a device after the
        very first boot.
        """
        # Create firstboot check file.
        ret = 0
        ret += cmd_exec("sudo touch " + self.first_boot_file_path)

        # Setup systemd first boot
        service_destination = os.path.join(self.rootfs_extract_dir, 'etc', 'systemd', 'system')

        # Bin destination
        bin_destination = os.path.join(self.rootfs_extract_dir, 'usr', 'local', 'bin')

        # Uhubctl destination
        dcs_user_home_destination = os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user')

        self.networking_setup(ret)
        
        # USB3_CONTROL service
        ret += cmd_exec("sudo cp resources/usb3_control/usb3_control.service " + service_destination)
        ret += cmd_exec("sudo cp resources/usb3_control/usb3_control.sh " + bin_destination)
        ret += cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'usb3_control.sh'))

        # USB_HUB_CONTROL service
        ret += cmd_exec("sudo cp resources/usb_hub_control/usb_hub_control.service " + service_destination)
        ret += cmd_exec("sudo cp resources/usb_hub_control/usb_hub_control.sh " + bin_destination)
        ret += cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'usb_hub_control.sh'))

        # FIRST_BOOT service
        ret += cmd_exec("sudo cp resources/dcs_first_boot.service " + service_destination)
        ret += cmd_exec("sudo cp resources/dcs_first_boot.sh " +   bin_destination)
        ret += cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'dcs_first_boot.sh'))

        # MOUNT_NVME_STORAGE service
        ret += cmd_exec("sudo cp resources/mount_nvme_storage/mount_nvme_storage.service " + service_destination)
        ret += cmd_exec("sudo cp resources/mount_nvme_storage/mount_nvme_storage.sh " +   bin_destination)
        ret += cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'mount_nvme_storage.sh'))

        # Create symlink to FIRST_BOOT service
        symlink_cmd = check_and_create_symlink(
            os.path.join(service_destination, 'multi-user.target.wants/dcs_first_boot.service'),
            os.path.join(service_destination, 'dcs_first_boot.service'))
        print(symlink_cmd)
        if symlink_cmd != 0:
            ret += cmd_exec(symlink_cmd)
        
        # FAN_CONTROL service
        ret += cmd_exec("sudo cp resources/fan_control/fan_control.service " + service_destination)
        ret += cmd_exec("sudo cp resources/fan_control/fan_control.sh " + bin_destination)
        ret += cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'fan_control.sh'))

        # Uhubctl
        ret += cmd_exec("sudo cp resources/uhubctl_2.1.0-1_arm64.deb " + dcs_user_home_destination)

        # Mavlink_sys_id_set
        ret += cmd_exec("sudo cp resources/mavlink_sys_id_set-1.0.0-Linux.deb " + dcs_user_home_destination)
        return ret

    def match_selected_config(self):
        """
        Get selected config based on loaded database from console arguments enterred by user
        """
        # Do not search again
        if self.selected_config_name != None:
            return self.selected_config_name
        
        for config in self.config_db:
            if (self.args.target_device in self.config_db[config]['device'] and
                self.args.jetpack == self.config_db[config]['l4t_version'] and
                self.args.hwrev in self.config_db[config]['board'] and
                self.args.storage in self.config_db[config]['storage'] and
                self.args.rootfs_type == self.config_db[config]['rootfs_type']):
                return config
                
        return None
    
    def print_config(self, config, items):
        for item in items:
            print("%s: %s" % (item, config[item]))

    def print_user_config(self):
        items = ["target_device", "jetpack", "hwrev", "storage", "rootfs_type" ]
        self.print_config(self.args.__dict__, items)

    def list_all_versions(self):
        for config in self.config_db:
            items = ['device', 'l4t_version', 'board', 'storage', 'rootfs_type']
            print('====', config, '====')
            self.print_config(self.config_db[config], items)  
            
            print()

    def load_selected_config(self):
        config = self.match_selected_config()
        if config == None:
            print('WARNING! Unsupported configuration! - enterred:')
            self.print_user_config()
            print()
            print("Please use one configuration from list:")
            self.list_all_versions()
            print("Exitting!")
            exit(3)
       
        self.config_db = self.config_db[config]
        
        # Update selected config according user enterred parameters
        self.config = self.config_db
        self.config['device'] = self.args.target_device
        self.config['board'] = self.args.hwrev
        self.config['storage'] = self.args.storage

        self.selected_config_name = config

    def setup_initrd_flashing(self):
        os.chdir(self.l4t_root_dir)
        # Set variables for initrd flash
        self.flash_script_path = os.path.relpath('tools/kernel_flash/l4t_initrd_flash.sh')
        
        if self.config['device'] == 'xavier_nx':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3668-0001-qspi-emmc"
            self.orin_options = ""
        elif self.config['device'] == 'orin_nx':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3767-0000"
            # Based on docs from tools/kerenel_flash/README_initrd_flash.txt and note for Orin (Workflow 4)
            # sudo ./tools/kernel_flash/l4t_initrd_flash.sh --external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_external.xml -p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml --no-systemimg" --network usb0      <board> external
            self.orin_options = '--network usb0 -p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml --no-systemimg"'
        else:
            print("Unknown device! [%s] exitting" % self.config['device'])
            exit(8)
         
        if self.config['storage'] == 'emmc':
            self.rootdev = "mmcblk0p1"
            self.external_device = ""
        elif self.config['storage'] == 'nvme':
            self.rootdev = "external"
            self.external_device = "--external-device nvme0n1p1 "
            if self.args.ab_partition == True:
                # Setup multiple app partitions
                self.ext_partition_layout = os.path.relpath('tools/kernel_flash/flash_l4t_nvme_rootfs_ab.xml')
            else:
                # Setup no multiple app partitions
                self.ext_partition_layout = os.path.relpath('tools/kernel_flash/flash_l4t_external_custom.xml')
        else:
            print("Unknown storage [%s]! exitting" % self.config['storage'])
            exit(9)
        # Fix default rootdev to external  (or internal) for orin. There is NFS used to flash
        if self.config['device'] == 'orin_nx':
            # "internal" - boot from  on-board device (eMMC/SDCARD)
            # "external" - boot from external device. For more see flash.sh examples
            self.rootdev = "external"

    def generate_images(self):
        self.prepare_status.change_group("images")
        # FYI: right now, generate images all the time, because there is an predisposition of
        # root filesystem being altered each flash (SYS_ID etc)

        self.prepare_status.set_processing_step("generate_images")
        print("-"*80)

        print("Generating images! ...")
        ret = -2

        # Note: --no-flash parameter allows us to only generate images which will be used for flashing new devices
        # flash internal emmc"

        if self.config['storage'] == 'emmc':
            ret = cmd_exec(f"sudo ./{self.flash_script_path} --no-flash --showlogs {self.board_name} {self.rootdev}")
        # Flash external nvme drive
        elif self.config['storage'] == 'nvme':
            # File to check: initrdflashparam.txt - contains last enterred parameters
            env_vars = ""
            opt_app_size_arg = ""
            external_only = "--external-only"
            
            if self.args.ab_partition == True:
                env_vars = "ROOTFS_AB=1"
                if self.args.rootfs_type == "minimal":
                    opt_app_size = 4
                else:
                    opt_app_size = 8
                opt_app_size_arg = f"-S {opt_app_size}GiB"
                external_only = "" # Flash internal and external device

            if self.args.app_size is not None:
                opt_app_size_arg = f"-S {self.args.app_size}GiB"

            if self.config['device'] == 'orin_nx':
                external_only = "" # Don't flash only external device
                
            cmd_exec("pwd")
            ret = cmd_exec(f"sudo {env_vars} ./{self.flash_script_path} {opt_app_size_arg} --no-flash {external_only} {self.external_device} " +
                           f"-c {self.ext_partition_layout} {self.orin_options} --showlogs {self.board_name} {self.rootdev}", print_command=True)
        self.prepare_status.set_status(ret, last_step= True)
        return ret

    def flash(self):
        # Setup flashing
        self.setup_initrd_flashing()
        
        # Generate images
        ret = self.generate_images()
        if ret != 0:

            print("Generating images was not sucessfull! ret = %d" % (ret))
            print("Exitting!")
            exit(7)
        # Flash device
        print("-"*80)
        print("Flash images! ...")
        self.prepare_status.change_group("flash")
        self.prepare_status.set_processing_step("flash_only")
        # Run sudo identification
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        ret = cmd_exec(f"sudo {self.flash_script_path} --flash-only {self.external_device} {self.orin_options} {self.board_name} {self.rootdev}", print_command=True)
        if ret == 0:
            self.batch_counter.increment()
        self.prepare_status.set_status(ret, last_step= True)


    def airvolute_flash(self):
        if self.match_selected_config() == None:
            print('Unsupported configuration!')
            return
        print("matched configuration: " + self.selected_config_name)
        self.download_resources()
        self.prepare_sources_production()
        self.flash()
        quit() 

    def run(self):
        if self.args.command == 'list':
            self.list_all_versions()
            quit()

        if self.args.command == 'flash':
            self.airvolute_flash()
            quit()


if __name__ == "__main__":
    dcs_deploy = DcsDeploy()
    dcs_deploy.run()
