#!/usr/bin/env python3

import argparse
import json
import subprocess
import os
import wget
import pprint
import tarfile
from threading import Thread
from threading import Event
import time


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

        nvidia_f_help = 'Specify nvidia folder path, use if not standard path is used.'
        subparser.add_argument(
            '--nvidia_f',  default='', help=nvidia_f_help)

        nvidia_f_help = 'Specify download folder path, use if not standard path is used (inside nvidia folder).'
        subparser.add_argument(
            '--download_f',  default='', help=nvidia_f_help)
        
        force_help = 'Files will be deleted and downloaded again.'
        subparser.add_argument(
            '--force', action='store_true',  default='', help=force_help)

        subparser.add_argument('-v', '--verbose', action='store_true',
                        help='Print detailed status information')
        
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
        
        manual_mode = subparsers.add_parser(
            'manual_mode', help='Just output image/pinmux files corresponding to selected configuration')

        self.add_manual_mode_parser(manual_mode)

        flash = subparsers.add_parser(
            'flash', help='Run the entire flash process')
        
        compile_flash = subparsers.add_parser(
            'compile_flash', help='Run compilation with flashing')

        self.add_common_parser(flash)

        image_help = 'Specify which image revision are we going to use (e.g. image100, image101 ...), if not specified latest version will be used.'
        flash.add_argument(
            '--image', default='', help=image_help)

        pinmux_help = 'Specify which pinmux revision of carrier boar are we going to use (e.g. image100, image101 ...).'
        flash.add_argument(
            '--pinmux',  default='', help=pinmux_help)

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
                self.config_db[config]["device"] == self.args.target_device and
                self.config_db[config]['bsp'] == self.args.jetpack and
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
        with open(self.downloaded_config_path, "w") as download_dict:
            json.dump(self.config, download_dict, indent=4)

    def run_loading_animation(self, event):
        t = Thread(target=self.loading_animation, args=(event,))
        t.start()
        return t

    def init_filesystem(self):
        config_relative_path = (
            self.config['device'] + '_' + 
            self.config['storage'] + '_' + 
            self.config['board'] + '_' +
            self.config['bsp']
        )

        self.home = os.path.expanduser('~')
        self.dsc_deploy_root = os.path.join(self.home, '.dcs_deploy')
        self.download_path = os.path.join(self.dsc_deploy_root, 'download', config_relative_path)
        self.flash_path = os.path.join(self.dsc_deploy_root, 'flash', config_relative_path)
        self.rootfs_file_path = os.path.join(self.download_path, 'rootfs.tbz2')
        self.l4t_file_path = os.path.join(self.download_path, 'l4t.tbz2')
        self.overlay_file_path = os.path.join(self.download_path, 'overlay.tbz2')
        self.image_file_path = os.path.join(self.download_path, 'system.img')
        self.pinmux_file_path = os.path.join(self.download_path, 'pinmuxes.tar.xz')
        self.rootfs_extract_dir = os.path.join(self.flash_path, 'Linux_for_Tegra', 'rootfs')
        self.l4t_root_dir = os.path.join(self.flash_path, 'Linux_for_Tegra')
        self.downloaded_config_path = os.path.join(self.dsc_deploy_root, 'downloaded_versions.json')

        # Handle dcs-deploy root dir
        if not os.path.isdir(self.dsc_deploy_root):
            os.mkdir(self.dsc_deploy_root)

        # Handle dcs-deploy download dir
        if not os.path.isdir(self.download_path):
            os.mkdir(self.download_path)

        # Handle dcs-deploy flash dir
        if not os.path.isdir(self.flash_path):
            os.mkdir(self.flash_path)

    def compare_downloaded_source(self):
        """Compares current input of the program with previously 
        downloaded sources.

        return True, if sources are already present locally.
        returnk False, if sources need to be downloaded.
        """
        # downloaded_sources = open(self.downloaded_config_path)
        if os.path.exists(self.downloaded_config_path):
            downloaded_config = json.load(open(self.downloaded_config_path))
            
            if all((downloaded_config.get(k) == v for k, v in self.config.items())):
                print('Resources for your config are already downloaded!')
                return True
            else:
                print('New resources will be downloaded!')
                return False 
        else:
            return False
    
    def download_resources(self):
        # pp = pprint.PrettyPrinter(indent=4)
        # pp.pprint(self.config)
        if self.compare_downloaded_source():
            return

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

        if self.config['overlay'] != 'none':
            print('Downloading overlay:')
            wget.download(
                self.config['overlay'],
                self.overlay_file_path
            )
            print()
        
        print('Downloading pinmux:')
        wget.download(
            self.config['pinmux'],
            self.pinmux_file_path
        )
        print()

        print('Downloading image:')
        wget.download(
            self.config['image'],
            self.image_file_path
        )
        print()

        self.save_downloaded_versions()

    def prepare_sources(self):
        stop_event = Event()

        # Extract Linux For Tegra
        print('Extracting Linux For Tegra ...')
        stop_event.clear()
        tar = tarfile.open(self.l4t_file_path)
        l4t_animation_thread = self.run_loading_animation(stop_event)
        tar.extractall(path=self.flash_path)
        stop_event.set()
        l4t_animation_thread.join()

        # Extract Sample Root Filesystem
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

    def check_compatibility(self):
        """
        Check compatibility based on user input config.
        """
        for config in self.config_db:
            if (
                self.config_db[config]["device"] == self.args.target_device and
                self.config_db[config]['bsp'] == self.args.jetpack and
                self.config_db[config]['board'] == self.args.hwrev and
                self.config_db[config]['storage'] == self.args.storage
            ):
                return True
                
        return False

    def list_all_versions(self):
        for config in self.config_db:
            print('====', config, '====')
            print('Device:', self.config_db[config]["device"])
            print('BSP:', self.config_db[config]["bsp"])
            print('Board:', self.config_db[config]["board"])
            print('Storage:', self.config_db[config]["storage"])
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
                self.config_db[config]['bsp'] == JETPACK and
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
                self.config_db[config]["device"] == self.args.target_device and
                self.config_db[config]['bsp'] == self.args.jetpack and
                self.config_db[config]['board'] == self.args.hwrev and
                self.config_db[config]['storage'] == self.args.storage
            ):
                self.config = self.config_db[config]

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
        self.prepare_sources()
        self.flash()
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