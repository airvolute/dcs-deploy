#!/usr/bin/env python3

import argparse
import json

class DcsDeploy:
    def __init__(self):
        self.parser = self.create_parser()
        self.args = self.parser.parse_args()
        self.sanitize_args()
        self.load_db()

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

    def get_files_from_args(self):
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


    def load_db(self):
        # TODO: Load this from AirVolute's FTP
        db_file = open('test_db.json')

        self.config_db = json.load(db_file)

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

    def run(self):
        if self.args.command == 'manual_mode':
            self.manual_mode()
            quit()

        if self.args.command == 'list':
            self.list_all_versions()
            quit()


if __name__ == "__main__":
    dcs_deploy = DcsDeploy()
    dcs_deploy.run()