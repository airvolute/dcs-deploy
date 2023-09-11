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
        self.load()
        self.prev_identifier = self.status["identifier"]
        if default_identifier == None:
            self.status["identifier"] = _sys.argv[1:]
            print("identifier: %s" % str(self.status["identifier"]))
        else:
            self.status["identifier"] = default_identifier
        
    def load(self):
        if os.path.isfile(self.status_file_name):
            with open(self.status_file_name, "r") as status_file:
                self.status = json.load(status_file)
            #check if old status is loaded without groups. If yes, regenerate status
            if not "last_processing_step" in self.status:
                return
        self.status = {
            "identifier" : [],
        }
        self._init_group_status()
    
    def _init_group_status(self, group = None):
        if group == None:
            group = self.group
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

    def is_identifier_same_as_prev(self):
        identifier = self.status["identifier"]
        if len(identifier) != len(self.prev_identifier):
            return False
        if len(set(identifier).difference(set(self.prev_identifier))) != 0:
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
            # check all status codes
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
        if group == None:
            group = self.group
        return self.status[group]["status"]
   
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
        #return os.path.dirname(path)

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

        # generate download resource paths
        resource_keys = ["rootfs", "l4t","nvidia_overlay", "airvolute_overlay"]
        self.resource_paths = {}

        for res_name in resource_keys:
            #print(" %s key: %s" % (res_name, self.config[res_name]))
            self.resource_paths[res_name] = self.get_download_file_path(self.get_resource_url(res_name))

        # remove old download directories
        self.cleanup_old_download_dir()

        if self.config['device'] == 'xavier_nx': 
            self.device_type = 't194'

        # Handle dcs-deploy root dir
        if not os.path.isdir(self.dsc_deploy_root):
            os.mkdir(self.dsc_deploy_root)

        # create dcs-deploy download dir
        for key in self.resource_paths:
            if self.resource_paths[key] == "":
                continue
            if not os.path.isdir(os.path.dirname(self.resource_paths[key])):
                os.makedirs(os.path.dirname(self.resource_paths[key]))

        # Handle dcs-deploy flash dir
        if not os.path.isdir(self.flash_path):
            os.makedirs(self.flash_path)
        elif self.args.force == True or self.args.regen == True:
            print('Removing previous L4T folder ...')
            self.cleanup_flash_dir()

        self.prepare_status = ProcessingStatus(os.path.join(self.flash_path, "prepare_status.json"), initial_group="prepare")
    
    def cleanup_flash_dir(self):
            cmd_exec("sudo rm -r " + self.flash_path)
            os.makedirs(self.flash_path)

    def check_dependencies(self):
        dependencies = ["qemu-user-static", "sshpass", "abootimg", "lbzip2"]
        for dependency in dependencies:
            if package_installed(dependency) == False:
                print("please install %s tool. eg: sudo apt-get install %s" % (dependency, dependency))
                print("exitting!")
                exit(1)

    def get_missing_resources(self, force_all_missing = False):
        res = []
        for resouce in self.resource_paths:
            if os.path.isfile(self.resource_paths[resouce]) and force_all_missing == False:
                continue
            # return only resource which is possible to download
            if(self.get_resource_url(resouce) != None):
                res += [resouce]
        return res

    def download_resources(self):
        for missing_resource in self.get_missing_resources(force_all_missing = self.args.force):
            print("missing resource '%s'. Going to download it!" % missing_resource)
            ret = self.download_resource(missing_resource, self.resource_paths[missing_resource])
            if ret < 0:
                print("can't download resource '" + missing_resource + "'!.")
                print("exitting!")
                exit(4)
            # regenerate
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
        # remove any existing temporary files
        cmd_exec("rm -f " + dst_path + "*.tmp")

        #check if file already exist
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
        

    def prepare_sources_production(self):
        if self.prepare_status.get_status() == True:
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

        self.prepare_status.set_processing_step("install_first_boot_setup")
        ret = self.install_first_boot_setup()
        self.prepare_status.set_status(ret, last_step = True)

    def prepare_airvolute_overlay(self):
        return self.extract_resource('airvolute_overlay')

    def prepare_nvidia_overlay(self):
        return self.extract_resource('nvidia_overlay')

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

        # uhubctl destination
        uhubctl_destination = os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user')
        
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

        ret += cmd_exec("sudo ln -s /etc/systemd/system/dcs_first_boot.service " + 
                 os.path.join(service_destination, 'multi-user.target.wants/dcs_first_boot.service'))

        # uhubctl
        ret += cmd_exec("sudo cp resources/uhubctl_2.1.0-1_arm64.deb " + uhubctl_destination)
        return ret

    def match_selected_config(self):
        """
        Get selected config based on loaded database from console arguments enterred by user
        """
        # do not search again
        if self.selected_config_name != None:
            return self.selected_config_name
        
        for config in self.config_db:
            if (self.config_db[config]['device'] == self.args.target_device and
                self.config_db[config]['l4t_version'] == self.args.jetpack and
                self.config_db[config]['board'] == self.args.hwrev and
                self.config_db[config]['storage'] == self.args.storage and
                self.config_db[config]['rootfs_type'] == self.args.rootfs_type):
                return config
                
        return None
    
    def print_config(self, config, items):
        for item in items:
            print("%s: %s" % (item, config[item]))

    def print_user_config(self):
        items = ["target_device", "jetpack", "hwrev", "storage", "rootfs_type" ]
        #print("==== user configuration ====")
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
       
        self.config = self.config_db[config]
        self.selected_config_name = config

    def setup_initrd_flashing(self):
        os.chdir(self.l4t_root_dir)
        #set variables for initrd flash
        self.flash_script_path = os.path.join(self.l4t_root_dir, 'tools/kernel_flash/l4t_initrd_flash.sh')
        
        if self.config['device'] == 'xavier_nx':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3668-0001-qspi-emmc"
        elif self.config['device'] == 'orin_nx':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3767-0000"
        else:
            print("Unknown device! [%s] exitting" % self.config['device'])
            exit(8)
         
        if self.config['storage'] == 'emmc':
            self.rootdev = "mmcblk0p1"
        elif self.config['storage'] == 'nvme':
            self.rootdev = "nvme0n1p1"
            if self.args.ab_partition == True:
                # setup multiple app partitions
                self.ext_partition_layout = os.path.join(self.l4t_root_dir, 'tools/kernel_flash/flash_l4t_nvme_rootfs_ab.xml')
            else:
                # setup no multiple app partitions
                self.ext_partition_layout = os.path.join(self.l4t_root_dir, 'tools/kernel_flash/flash_l4t_external_custom.xml')
        else:
            print("Unknown storage [%s]! exitting" % self.config['storage'])
            exit(9)

    def generate_images(self):
        self.prepare_status.change_group("images")
        # check commandline parameter if they are same as previous and images are already generated skip generation
        if self.prepare_status.is_identifier_same_as_prev() and self.prepare_status.get_status() == True:
            print("Images already generated! Skipping generating images!")
            return 0

        self.prepare_status.set_processing_step("generate_images")
        print("-"*80)
        print("Generating images! ...")
        ret = -2

        # Note: --no-flash parameter allows us to only generate images which will be used for flashing new devices
        # flash internal emmc"
        if self.config['storage'] == 'emmc':
            ret = cmd_exec(f"sudo {self.flash_script_path} --no-flash --showlogs {self.board_name} {self.rootdev}")
        # flash external nvme drive
        elif self.config['storage'] == 'nvme':
            #file to check: initrdflashparam.txt - contains last enterred parameters
            env_vars = ""
            opt_app_size = ""
            external_only = "--external-only" # flash only external device
            if self.args.ab_partition == True:
                env_vars = "ROOTFS_AB=1"
                opt_app_size = "-S 4GiB "
                external_only = "" # flash internal and external device
                #self.rootdev = "external" # set UUID device in kernel commandline: rootfs=PARTUUID=<external-uuid>
            ret = cmd_exec(f"sudo {env_vars} {self.flash_script_path} {opt_app_size} --no-flash {external_only} --external-device nvme0n1p1 " +
                           f"-c {self.ext_partition_layout} --showlogs {self.board_name} {self.rootdev}", print_command=True)
        self.prepare_status.set_status(ret, last_step= True)
        return ret

    def flash(self):
        # setup flashing
        self.setup_initrd_flashing()
        
        # generate images
        ret = self.generate_images()
        if ret != 0:
            print("Generating images was not sucessfull! ret = %d", ret)
            print("Exitting!")
            exit(7)
        # flash device
        print("-"*80)
        print("Flash images! ...")
        self.prepare_status.change_group("flash")
        self.prepare_status.set_processing_step("flash_only")
        ret = cmd_exec(f"sudo {self.flash_script_path} --flash-only {self.board_name} {self.rootdev}", print_command=True)
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