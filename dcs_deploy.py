#!/usr/bin/env python3

import argparse
import json
import subprocess
import os
import wget
import tarfile
from threading import Thread, Event
import time
import shutil
import git
import tegrity


class DcsDeploy:
    def __init__(self):
        self.parser = self.create_parser()
        self.args = self.parser.parse_args()
        self.sanitize_args()
        self.load_db()
        if self.args.command != 'list':
            self.load_selected_config()
            self.init_filesystem()

    def add_common_parser(self, subparser):
        target_device_help = 'REQUIRED. Which type of device are we setting up. Options: [xavier_nx, orin_nx]'
        subparser.add_argument(
            'target_device', help=target_device_help)

        jetpack_help = 'REQUIRED. Which jetpack are we going to use. Options: [46, 502].'
        subparser.add_argument(
            'jetpack', help=jetpack_help)

        hwrev_help = 'REQUIRED. Which hardware revision of carrier board are we going to use. Options: [1.0, 1.2].'
        subparser.add_argument(
            'hwrev', help=hwrev_help)
        
        storage_help = 'REQUIRED. Which storage medium are we going to use. Options: [emmc, nvme].'
        subparser.add_argument(
            'storage', help=storage_help)
        
        force_help = 'Files will be deleted, downloaded and extracted again.'
        subparser.add_argument(
            '--force', action='store_true',  default='', help=force_help)
        
    def add_flash_parser(self, subparser):
        target_device_help = 'REQUIRED. Which type of device are we setting up (e.g. xaviernx ...).'
        subparser.add_argument(
            'target_device', help=target_device_help)

        jetpack_help = 'REQUIRED. Which jetpack are we going to use (e.g. jp46, jp502 ...).'
        subparser.add_argument(
            'jetpack', help=jetpack_help)

        hwrev_help = 'REQUIRED. Which hardware revision of carrier board are we going to use (e.g. rev4, rev5 ...).'
        subparser.add_argument(
            'hwrev', help=hwrev_help)
        
        storage_help = 'REQUIRED. Which storage medium are we going to use (internal - emmc, external - nvme).'
        subparser.add_argument(
            'storage', help=storage_help)

        create_rootfs_help = 'Developer only! Creates root filesystem for future use.'
        subparser.add_argument(
            '--create_rootfs', action='store_true',  default='', help=create_rootfs_help)
        
        force_help = 'Files will be deleted, downloaded and extracted again.'
        subparser.add_argument(
            '--force', action='store_true',  default='', help=force_help)
        
    def add_manual_mode_parser(self, subparser):
        target_device_help = 'REQUIRED. Which type of device are we setting up (e.g. xaviernx ...).'
        subparser.add_argument(
            'target_device', help=target_device_help)

        jetpack_help = 'REQUIRED. Which jetpack are we going to use (e.g. jp46, jp502 ...).'
        subparser.add_argument(
            'jetpack', help=jetpack_help)

        hwrev_help = 'REQUIRED. Which hardware revision of carrier board are we going to use (e.g. rev4, rev5 ...).'
        subparser.add_argument(
            'hwrev', help=hwrev_help)
        
        storage_help = 'REQUIRED. Which storage medium are we going to use (internal - emmc, external - nvme).'
        subparser.add_argument(
            'storage', help=storage_help)

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
        
        compile_flash = subparsers.add_parser(
            'compile_flash', help='Run compilation with flashing')

        self.add_flash_parser(flash)
        self.add_common_parser(compile_flash)
        
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
        # TODO: Load this from AirVolute's FTP
        db_file = open('local/test_db.json')

        self.config_db = json.load(db_file)

    def get_files_from_args(self):
        # TODO: this method might be irrelevant, inspect later
        """Returns filenames of image and pinmux according to config.

        Returns: 
        tuple:(image, pinmux)  
        """
        for config in self.config_db:
            if (
                self.config_db[config]['device'] == self.args.target_device and
                self.config_db[config]['l4t_version'] == self.args.jetpack and
                self.config_db[config]['board'] == self.args.hwrev and
                self.config_db[config]['storage'] == self.args.storage
            ):

                return self.config_db[config]['image'], self.config_db[config]['pinmux']

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
                file_data[self.current_config_name] = self.config
                download_dict.seek(0)
                json.dump(file_data, download_dict, indent = 4)
        else:
            with open(self.downloaded_config_path, "a") as download_dict:
                config_to_save = {}
                config_to_save[self.current_config_name] = self.config
                json.dump(config_to_save, download_dict, indent=4)

    def run_loading_animation(self, event):
        t = Thread(target=self.loading_animation, args=(event,))
        t.start()
        return t

    def init_filesystem(self):
        config_relative_path = (
            self.config['device'] + '_' + 
            self.config['storage'] + '_' + 
            self.config['board'] + '_' +
            self.config['l4t_version']
        )

        self.home = os.path.expanduser('~')
        self.dsc_deploy_root = os.path.join(self.home, '.dcs_deploy')
        self.download_path = os.path.join(self.dsc_deploy_root, 'download', config_relative_path)
        self.flash_path = os.path.join(self.dsc_deploy_root, 'flash', config_relative_path)
        self.rootfs_file_path = os.path.join(self.download_path, 'rootfs.tbz2')
        self.l4t_file_path = os.path.join(self.download_path, 'l4t.tbz2')
        self.nvidia_overlay_file_path = os.path.join(self.download_path, 'nvidia_overlay.tbz2')
        self.airvolute_overlay_file_path = os.path.join(self.download_path, 'airvolute_overlay.tbz2')
        self.image_file_path = os.path.join(self.download_path, 'system.img')
        self.pinmux_file_path = os.path.join(self.download_path, 'pinmuxes.tar.xz')
        self.rootfs_extract_dir = os.path.join(self.flash_path, 'Linux_for_Tegra', 'rootfs')
        self.l4t_root_dir = os.path.join(self.flash_path, 'Linux_for_Tegra')
        self.downloaded_config_path = os.path.join(self.dsc_deploy_root, 'downloaded_versions.json')
        self.resource_file_check_path = os.path.join(self.flash_path, 'check')
        self.pinmux_l4t_dir = os.path.join(self.l4t_root_dir, 'bootloader', 't186ref', 'BCT')
        self.apply_binaries_path = os.path.join(self.l4t_root_dir, 'apply_binaries.sh')
        self.create_user_script_path = os.path.join(self.l4t_root_dir, 'tools', 'l4t_create_default_user.sh')

        if self.config['device'] == 'xavier_nx': 
            self.device_type = 't194'
        if self.config['device'] == 'orin_nx':
            # TODO: set correct ref number
            self.device_type = 'txxx'

        # Handle dcs-deploy root dir
        if not os.path.isdir(self.dsc_deploy_root):
            os.mkdir(self.dsc_deploy_root)

        # Handle dcs-deploy download dir
        if not os.path.isdir(self.download_path):
            os.makedirs(self.download_path)

        # Handle dcs-deploy flash dir
        if not os.path.isdir(self.flash_path):
            os.makedirs(self.flash_path)

    def compare_downloaded_source(self):
        """Compares current input of the program with previously 
        downloaded sources.

        return True, if sources are already present locally.
        return False, if sources need to be downloaded.
        """
        if self.args.force == True:
            return False

        # downloaded_sources = open(self.downloaded_config_path)
        if os.path.exists(self.downloaded_config_path):
            downloaded_configs = json.load(open(self.downloaded_config_path))

            for config in downloaded_configs:
                if config == self.current_config_name:
                    print('Resources for your config are already downloaded!')
                    return True
            
            print('New resources will be downloaded!')
            return False

        else:
            return False
        
    def save_extracted_resources(self):
        with open(self.resource_file_check_path, "w") as resource_file:
            for (root, dirs, files) in os.walk(self.flash_path):
                for name in files:
                    resource_file.write(str(os.path.join(root, name))+"\n")
    
    def check_extracted_resources(self):
        """Checks if resources were extracted before AND
        if the resources are valid (no missing files)
        
        return True if resources are extracted AND valid
        return False if resources are NOT extracted OR are invalid
        """
        if os.path.exists(self.resource_file_check_path):
            resource_file = open(self.resource_file_check_path, 'r')
            for (root, dirs, files) in os.walk(self.flash_path):
                for name in files:
                    line = resource_file.readline()
                    if not line:
                        break
                    if str(os.path.join(root, name))+"\n" != line:
                        print('Invalid resources')
                        resource_file.close()
                        return False
                    
            resource_file.close()
            return True
        else:
            return False
    
    def download_resources(self):
        if self.compare_downloaded_source():
            return

        if not self.args.create_rootfs:
            print('Downloading rootfs:')
            wget.download(
                self.config['rootfs'],
                self.rootfs_file_path
            )
            print()

        print('Downloading Linux For Tegra:')
        wget.download(
            self.config['l4t'],
            self.l4t_file_path
        )
        print()

        if self.config['nvidia_overlay'] != 'none':
            print('Downloading Nvidia overlay:')
            wget.download(
                self.config['nvidia_overlay'],
                self.nvidia_overlay_file_path
            )
            print()

        print('Downloading Airvolute overlay:')
        wget.download(
            self.config['airvolute_overlay'],
            self.airvolute_overlay_file_path
        )
        print()

        self.save_downloaded_versions()

    def prepare_sources_production(self):
        if self.args.force == False:
            if self.check_extracted_resources():
                print('Resources already extracted, proceeding to next step!')
                return
        
        stop_event = Event()

        # Extract Linux For Tegra
        print('Extracting Linux For Tegra ...')
        stop_event.clear()
        tar = tarfile.open(self.l4t_file_path)
        l4t_animation_thread = self.run_loading_animation(stop_event)
        tar.extractall(path=self.flash_path)
        stop_event.set()
        l4t_animation_thread.join()

        # Extract Root Filesystem
        print('Extracting Root Filesystem ...')
        stop_event.clear()
        print('This part needs sudo privilegies:')
        # Run sudo identification
        subprocess.call(["/usr/bin/sudo", "/usr/bin/id"], stdout=subprocess.DEVNULL)
        rootfs_animation_thread = self.run_loading_animation(stop_event)
        subprocess.call(
            [
                'sudo',
                'tar', 
                'xpf', 
                self.rootfs_file_path,
                '--directory', 
                self.rootfs_extract_dir
            ]
        )
        stop_event.set()
        rootfs_animation_thread.join()

        # TODO: We might not want to apply binaries when we have already our filesystem ready!
        # Apply binaries
        # print('Applying binaries ...')
        # print('This part needs sudo privilegies:')
        # # Run sudo identification
        # subprocess.call(["/usr/bin/sudo", "/usr/bin/id"], stdout=subprocess.DEVNULL)
        # subprocess.call(['/usr/bin/sudo', self.apply_binaries_path])

        if self.config['nvidia_overlay'] != 'none':
            print('Applying Nvidia overlay ...')
            self.prepare_nvidia_overlay()

        self.save_extracted_resources()

    def prepare_sources_development(self):
        if self.args.force == False:
            if self.check_extracted_resources():
                print('Resources already extracted, proceeding to next step!')
                return
        
        stop_event = Event()

        # Extract Linux For Tegra
        print('Extracting Linux For Tegra ...')
        stop_event.clear()
        tar = tarfile.open(self.l4t_file_path)
        l4t_animation_thread = self.run_loading_animation(stop_event)
        tar.extractall(path=self.flash_path)
        stop_event.set()
        l4t_animation_thread.join()

        if self.config['nvidia_overlay'] != 'none':
            print('Applying Nvidia overlay ...')
            self.prepare_nvidia_overlay()

        print('Applying Airvolute overlay ...')
        self.prepare_airvolute_overlay()

        # Build Root Filesystem
        self.prepare_minimal_sample_rootfs()

        self.save_extracted_resources()
        self.clone_dcs_setup()

    def prepare_airvolute_overlay(self):
        tar = tarfile.open(self.airvolute_overlay_file_path)
        tar.extractall(self.flash_path)

    def prepare_minimal_sample_rootfs(self):
        self.build_fs_cript_path = os.path.join(
            self.l4t_root_dir, 'tools', 'samplefs', 'nv_build_samplefs.sh'
        )
        
        self.sample_minimal_rootfs_path = os.path.join(
            self.l4t_root_dir, 'tools', 'samplefs', 'sample_fs.tbz2'
        )

        self.apt_sources_file_path = os.path.join(
            self.rootfs_extract_dir,
            'etc',
            'apt',
            'sources.list.d',
            'nvidia-l4t-apt-source.list'
        )

        print('Building rootfs ...')
        print('This part needs sudo privilegies:')
        # Run sudo identification
        subprocess.call(["/usr/bin/sudo", "/usr/bin/id"], stdout=subprocess.DEVNULL)
        # Build minimal sample rootfs
        # TODO: look into CTRL-C while this process is happenning (it won't shut down)
        subprocess.call(
            [
                'sudo',
                self.build_fs_cript_path, 
                '--abi', 
                'aarch64',
                '--distro', 
                'ubuntu',
                '--flavor',
                'minimal',
                '--version',
                'focal'
            ]
        )

        # Extract rootfs to correct dir
        print('Extracting rootfs ...')
        subprocess.call(
            [
                'sudo',
                'tar', 
                'xpf', 
                self.sample_minimal_rootfs_path,
                '--directory', 
                self.rootfs_extract_dir
            ]
        )

        # Apply binaries
        print('Applying binaries ...')
        subprocess.call(['/usr/bin/sudo', self.apply_binaries_path])

        # TODO: Do I need to run sudo ident before each sudo command?
        # See if this throws sudo identification prompt
        print('Creating default user ...')
        subprocess.call(
            [
                'sudo',
                self.create_user_script_path,
                '-u',
                'dcs_user',
                '-p',
                'dronecore',
                '-n',
                'dcs',
                '--accept-license'
            ]
        )

        # Set correct apt sources
        device_type_sed_str = 's/<SOC>/' +  self.device_type + '/g'
        subprocess.call(
            [
                'sudo',
                'sed',
                '-i',
                device_type_sed_str,
                self.apt_sources_file_path
            ]
        )

    def clone_dcs_setup(self):
        """
        This method clones dcs_setup package inside chroot home
        """
        print('Running dcs_setup ...')
        clone_path = os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user', 'dcs-setup')

        # TODO: be aware that this needs to be put on some public server
        # This works only if you are ssh-key synchronized with 
        # gitlab.airvolute.com from the machine you are trying this script from
        repo = git.Repo.clone_from(
            'git@gitlab.airvolute.com:sw/linux/app/dcs-setup.git',
            clone_path
        )

        repo.git.checkout('ros2_airvolute_dev_NG')

    def prepare_nvidia_overlay(self):
        tar = tarfile.open(self.nvidia_overlay_file_path)
        tar.extractall(self.flash_path)

    def check_compatibility(self):
        """
        Check compatibility based on user input config.
        """
        for config in self.config_db:
            if (
                self.config_db[config]['device'] == self.args.target_device and
                self.config_db[config]['l4t_version'] == self.args.jetpack and
                self.config_db[config]['board'] == self.args.hwrev and
                self.config_db[config]['storage'] == self.args.storage
            ):
                return True
                
        return False

    def list_all_versions(self):
        for config in self.config_db:
            print('====', config, '====')
            print('Device:', self.config_db[config]['device'])
            print('L4T version:', self.config_db[config]['l4t_version'])
            print('Board:', self.config_db[config]['board'])
            print('Storage:', self.config_db[config]['storage'])
            print('====================')
            print()

    def manual_mode(self):
        if not self.check_compatibility():
            print('Unsupported configuration provided!')
            return
        
        DEVICE = self.args.target_device
        JETPACK = self.args.jetpack
        HWREV = self.args.hwrev
        STORAGE = self.args.storage

        for config in self.config_db:
            if (
                self.config_db[config]["device"] == DEVICE and
                self.config_db[config]['l4t_version'] == JETPACK and
                self.config_db[config]['board'] == HWREV and
                self.config_db[config]['storage'] == STORAGE
            ):
                print('IMAGE to download: ', self.config_db[config]['image'])
                print('PINMUX to download: ', self.config_db[config]['pinmux'])

    def load_selected_config(self):
        if not self.check_compatibility():
            print('Unsupported configuration!')
            
            return
        
        for config in self.config_db:
            if (
                self.config_db[config]['device'] == self.args.target_device and
                self.config_db[config]['l4t_version'] == self.args.jetpack and
                self.config_db[config]['board'] == self.args.hwrev and
                self.config_db[config]['storage'] == self.args.storage
            ):
                self.config = self.config_db[config]
                self.current_config_name = config

    def flash(self):
        if (self.config['storage'] == 'emmc' and
            self.config['device'] == 'xavier_nx'):
            flash_script_path = os.path.join(self.l4t_root_dir, 'flash.sh')
            subprocess.call(
            [
                'sudo',
                'bash',
                flash_script_path,
                '--no-flash',
                'jetson-xavier-nx-devkit-emmc', 
                'mmcblk0p1'
            ]
        )   

    def airvolute_flash(self):
        # ======================= EDO REFACTOR ================================
        if not self.check_compatibility():
            print('Unsupported configuration!')
            return

        self.download_resources()
        if self.args.create_rootfs:
            self.prepare_sources_development()
        else:
            self.prepare_sources_production()
        # self.flash()
        quit() 

    def run(self):
        if self.args.command == 'manual_mode':
            self.manual_mode()
            quit()

        if self.args.command == 'list':
            self.list_all_versions()
            quit()

        if self.args.command == 'flash':
            self.airvolute_flash()
            quit()


if __name__ == "__main__":
    dcs_deploy = DcsDeploy()
    dcs_deploy.run()