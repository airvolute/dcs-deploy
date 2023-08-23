#!/usr/bin/env python3

import argparse
import json
import subprocess
import os
import wget
from threading import Thread, Event
import time
from urllib.parse import urlparse


# example: retcode = cmd_exec("sudo tar xpf %s --directory %s" % (self.rootfs_file_path, self.rootfs_extract_dir))
def cmd_exec(command_line:str) -> int:
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

class DcsDeploy:
    def __init__(self):
        self.check_dependencies()
        self.parser = self.create_parser()
        self.args = self.parser.parse_args()
        self.selected_config_name = None
        self.sanitize_args()
        self.load_db()
        if self.args.command != 'list':
            self.load_selected_config()
            self.init_filesystem()

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
        subparser.add_argument('--force', action='store_true',  default='', help=force_help)

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
        
        return parser
    
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

    def save_downloaded_versions(self):
        if os.path.isfile(self.downloaded_config_path):
            with open(self.downloaded_config_path, "r+") as download_dict:
                file_data = json.load(download_dict)
                file_data[self.selected_config_name] = self.config
                download_dict.seek(0)
                json.dump(file_data, download_dict, indent = 4)
        else:
            with open(self.downloaded_config_path, "a") as download_dict:
                config_to_save = {}
                config_to_save[self.selected_config_name] = self.config
                json.dump(config_to_save, download_dict, indent=4)

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
        self.downloaded_config_path = os.path.join(self.dsc_deploy_root, 'downloaded_versions.json')
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
        else:
            print('Removing previous L4T folder ...')

            cmd_exec("sudo rm -r " + self.flash_path)
            
            os.makedirs(self.flash_path)

    def check_dependencies(self):
        dependencies = ["qemu-user-static", "sshpass", "abootimg", "lbzip2"]
        for dependency in dependencies:
            if package_installed(dependency) == False:
                print("please install %s tool. eg: sudo apt-get install %s" % (dependency, dependency))
                print("exitting!")
                exit(1)

    def get_missing_resources(self):
        res = []
        for resouce in self.resource_paths:
            if os.path.isfile(self.resource_paths[resouce]):
                continue
            # return only resource which is possible to download
            if(self.get_resource_url(resouce) != None):
                res += [resouce]
        return res

    def compare_downloaded_source(self):
        """Compares current input of the program with previously downloaded sources. If resouces are not complete, try to fullfill them

        return True, if sources are already present locally.
        return False, if sources need to be downloaded.
        """
        if self.args.force == True:
            return False

        if os.path.exists(self.downloaded_config_path):
            downloaded_configs = json.load(open(self.downloaded_config_path))

            for config in downloaded_configs:
                if config == self.selected_config_name:
                    for missing_resource in self.get_missing_resources():
                        print("missing resource '%s'. Going to download it!" % missing_resource)    
                        ret = self.download_resource(missing_resource, self.resource_paths[missing_resource])
                        if ret < 0:
                            print("can't download resource '" + missing_resource + "'!.")
                            print("exitting!")
                            exit(4)
                    print('Resources for your config are already downloaded!')
                    return True
            
            print('New resources will be downloaded!')
            return False

        else:
            return False
    
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
        try:
            wget.download(
                self.config[resource_name],
                dst_path
            )
        except Exception as e:
            print("Got error while downloading resource", resource_name, "Error: ", str(e))
            return -1
        print()
        return 0
    
    def download_resources(self):
        if self.compare_downloaded_source():
            return
        
        for resource in self.resource_paths:
            self.download_resource(resource, self.resource_paths[resource])    

        self.save_downloaded_versions()

    def prepare_sources_production(self):
        stop_event = Event()

        # Extract Linux For Tegra
        print('Extracting Linux For Tegra ...')
        stop_event.clear()
        l4t_animation_thread = self.run_loading_animation(stop_event)
        
        extract(self.resource_paths["l4t"], self.flash_path)
        
        stop_event.set()
        l4t_animation_thread.join()

        # Extract Root Filesystem
        print('Extracting Root Filesystem ...')
        stop_event.clear()
        print('This part needs sudo privilegies:')

        # Run sudo identification
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")

        rootfs_animation_thread = self.run_loading_animation(stop_event)

        extract(self.resource_paths['rootfs'], self.rootfs_extract_dir)

        stop_event.set()
        rootfs_animation_thread.join()

        if self.config['nvidia_overlay'] != 'none':
            print('Applying Nvidia overlay ...')
            self.prepare_nvidia_overlay()

        # Apply binaries
        print('Applying binaries ...')
        print('This part needs sudo privilegies:')
        # Run sudo identification
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        
        cmd_exec("/usr/bin/sudo " + self.apply_binaries_path)

        print('Applying Airvolute overlay ...')
        self.prepare_airvolute_overlay()

        cmd_exec("/usr/bin/sudo " + self.apply_binaries_path + " -t False")

        print('Creating default user ...')
        cmd_exec("sudo " + self.create_user_script_path + " -u dcs_user -p dronecore -n dcs --accept-license")

        self.install_first_boot_setup()

    def prepare_airvolute_overlay(self):
        extract(self.resource_paths['airvolute_overlay'], self.flash_path)

    def prepare_nvidia_overlay(self):
        extract(self.resource_paths['nvidia_overlay'], self.flash_path)

    def install_first_boot_setup(self):
        """
        Installs script that would be run on a device after the
        very first boot.
        """
        # Create firstboot check file.
        cmd_exec("sudo touch " + self.first_boot_file_path)

        # Setup systemd first boot
        service_destination = os.path.join(self.rootfs_extract_dir, 'etc', 'systemd', 'system')

        # Bin destination
        bin_destination = os.path.join(self.rootfs_extract_dir, 'usr', 'local', 'bin')

        # uhubctl destination
        uhubctl_destination = os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user')
        
        # USB3_CONTROL service
        cmd_exec("sudo cp resources/usb3_control/usb3_control.service " + service_destination)

        cmd_exec("sudo cp resources/usb3_control/usb3_control.sh " + bin_destination)

        cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'usb3_control.sh'))

        # USB_HUB_CONTROL service
        cmd_exec("sudo cp resources/usb_hub_control/usb_hub_control.service " + service_destination)

        cmd_exec("sudo cp resources/usb_hub_control/usb_hub_control.sh " + bin_destination)

        cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'usb_hub_control.sh'))

        # FIRST_BOOT service
        cmd_exec("sudo cp resources/dcs_first_boot.service " + service_destination)

        cmd_exec("sudo cp resources/dcs_first_boot.sh " +   bin_destination)

        cmd_exec("sudo chmod +x " + os.path.join(bin_destination, 'dcs_first_boot.sh'))

        cmd_exec("sudo ln -s /etc/systemd/system/dcs_first_boot.service " + 
                 os.path.join(service_destination, 'multi-user.target.wants/dcs_first_boot.service'))

        # uhubctl
        cmd_exec("sudo cp resources/uhubctl_2.1.0-1_arm64.deb " + uhubctl_destination)

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

    def flash(self):
        flash_script_path = os.path.join(self.l4t_root_dir, 'tools/kernel_flash/l4t_initrd_flash.sh')
        
        cfg_file_name = 'airvolute-dcs' + self.config['board'] + "+p3668-0001-qspi-emmc"

        if (self.config['storage'] == 'emmc' and self.config['device'] == 'xavier_nx'):
            os.chdir(self.l4t_root_dir)

            cmd_exec("sudo bash " + flash_script_path + " " + cfg_file_name + " mmcblk0p1")

        if (self.config['storage'] == 'nvme' and self.config['device'] == 'xavier_nx'):
            external_xml_config_path = os.path.join(self.l4t_root_dir, 'tools/kernel_flash/flash_l4t_external_custom.xml')
            os.chdir(self.l4t_root_dir)

            cmd_exec("sudo bash " + flash_script_path + " --external-only --external-device nvme0n1p1 -c " + external_xml_config_path +
                     " --showlogs " + cfg_file_name + " nvme0n1p1")


    def airvolute_flash(self):
        if self.match_selected_config() == None:
            print('Unsupported configuration!')
            return

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