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
        self.init_filesystem()
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
        self.home = os.path.expanduser('~')
        self.dsc_deploy_root = os.path.join(self.home, '.dcs_deploy')
        self.download_path = os.path.join(self.dsc_deploy_root, 'download')
        self.flash_path = os.path.join(self.dsc_deploy_root, 'flash')
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

        returns true, if sources are already present locally.
        returns false, if sources need to be downloaded.
        """
        # downloaded_sources = open(self.downloaded_config_path)
        downloaded_config = json.load(open(self.downloaded_config_path))
        
        if all((downloaded_config.get(k) == v for k, v in self.config.items())):
            print('Resources for your config are already downloaded!')
            return True
        else:
            print('New resources will be downloaded!')
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

        self.load_selected_config()
        self.download_resources()
        # self.prepare_sources()
        self.flash()
        quit()
        # L_DEVICE_JP_F = 'JetPack_5.0.2_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
        
        # print('sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip')

        # Fill JetPack version info
        if self.config_db[self.config]["bsp"] == '46':
            SDK_MANAGER_JP = '4.6'
        elif self.config_db[self.config]["bsp"] == '502':
            SDK_MANAGER_JP = '5.0.2'
        elif self.config_db[self.config]["bsp"] == '51':
            SDK_MANAGER_JP = '5.1'

        # Fill device info
        if self.config_db[self.config]["device"] == 'xavier_nx':
            SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        elif self.config_db[self.config]["device"] == 'xavier_nx':
            SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
            
        # arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip --license accept']
        # TODO: Maybe terminator should be dependency? :D 
        arg_flash = ['terminator', '-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip --license accept']
        subprocess.call(arg_flash, stdout=subprocess.PIPE)
        input("Press Enter to continue after installing from sdkmanager finishes...")
        # if not os.path.isdir(L_NVIDIA_F):
        #     print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
        #     quit()

        #  =================== MARTIN IMPLEMENTATION ==========================
        # print('###############################################################################')
        # print()
        # print('Setting up versions')
        # print()
        # print('###############################################################################')
        # print()

        # DEVICE = args.target_device
        # JETPACK = args.jetpack
        # HWREV = args.hwrev
        # IMAGE = args.image
        # PINMUX = args.pinmux
        # L_NVIDIA_F = args.nvidia_f
        # L_FOLDER_D = args.download_f
        # FORCE = False

        # if L_NVIDIA_F == '':
        #     L_NVIDIA_F = '/home/' + \
        #         os.getenv('USER', default=None)+'/nvidia/nvidia_sdk'
        # if L_FOLDER_D == '':
        #     L_FOLDER_D = '/home/' + \
        #         os.getenv('USER', default=None)+'/nvidia/airvolute_download'
        # if IMAGE == '':
        #     USING_LATEST_IMG = True
        # else:
        #     USING_LATEST_IMG = False
        # if PINMUX == '':
        #     USING_LATEST_PINMUX = True
        # else:
        #     USING_LATEST_PINMUX = False

        # if args.force == True:
        #     FORCE = True

        # filename = get_versions()

        # tree = ET.parse(filename)
        # root = tree.getroot()
        # devices_list = []
        # devices_list_names = []
        # jp_list = []
        # xml_path = []

        # for x in root.findall('Device'):
        #     devices_list.append(x)
        #     devices_list_names.append(x.text.strip())

        # # Check if device is compatible
        # for elem in devices_list:
        #     if DEVICE in elem.text.strip():
        #         print('Device: ' + DEVICE)
        #         xml_path.append(elem)
        #         break

        # if len(xml_path) != 1:
        #     print('Device: ' + DEVICE + ' not found!')
        #     print('Supported devices: ' + ' '.join(devices_list_names))
        #     quit()

        # # Check if jetpack is compatible
        # for elem in xml_path[0].findall('JP'):
        #     if JETPACK in elem.text.strip():
        #         print('Jetpack: ' + JETPACK)
        #         xml_path.append(elem)
        #         break

        # if len(xml_path) != 2:
        #     print('Jetpack: ' + JETPACK + ' not found!')

        #     jp_list = []
        #     for x in xml_path[0].findall('JP'):
        #         jp_list.append(x.text.strip())
        #     print('Supported jetpacks: ' + ' '.join(jp_list))
        #     quit()

        # # Check if hwrev is compatible
        # for elem in xml_path[1].findall('HWRev'):
        #     if HWREV in elem.text.strip():
        #         print('HWRev: ' + HWREV)
        #         xml_path.append(elem)
        #         break

        # if len(xml_path) != 3:
        #     print('HWRev: ' + HWREV + ' not found!')
        #     print('Supported HWRevs: ' + ' '.join(xml_path[1].findall('HWRev')))
        #     quit()

        # # Check if image is compatible
        # elem_image_list = []
        # elem_image = []

        # for elem in xml_path[2].findall('Image'):
        #     elem_image.append([elem.text.strip(), elem])
        #     elem_image_list.append(elem.text.strip())

        # elem_image.sort(key=lambda x: x[0], reverse=True)

        # # Get versions to be flashed
        # IMAGE_VER = ''
        # PINMUX_VER = ''

        # if USING_LATEST_IMG:
        #     xml_path.append(elem_image[0][1])
        #     IMAGE_VER = elem_image[0][1].text.strip()
        # else:
        #     if any(IMAGE in subl for subl in elem_image):
        #         IMAGE_VER = IMAGE
        #         xml_path.append(elem_image[list(np.array(elem_image, dtype=object)[:, 0]).index(IMAGE_VER)][1])
        #     else:    
        #         print('Image version ' + IMAGE + ' not available.')
        #     if IMAGE_VER == '':
        #         print('Available image versions: ' +
        #             ' '.join(np.array(elem_image, dtype=object)[:, 0]))
        #         print('Please specify version or use latest, check help with -h option.')
        #         quit()

        # print('Image: ' + IMAGE_VER)
        # # Get pinmuxes to be flashed
        # #list(np.array(elem_image, dtype=object)[:, 0]).index(IMAGE_VER)
        # elem_pinmuxes_list = []
        # elem_pinmuxes = []
        # for elem in xml_path[3].findall('Pinmux'):
        #     elem_pinmuxes.append([elem.text.strip(), elem])
        #     elem_pinmuxes_list.append(elem.text.strip())

        # elem_pinmuxes.sort(key=lambda x: x[0], reverse=True)

        # if USING_LATEST_PINMUX:
        #     xml_path.append(elem_pinmuxes[0][1])
        #     PINMUX_VER = elem_pinmuxes[0][1].text.strip()
        # else:
        #     if any(PINMUX in subl for subl in elem_pinmuxes):
        #         PINMUX_VER = PINMUX
        #         xml_path.append(elem_pinmuxes[list(np.array(elem_pinmuxes, dtype=object)[:, 0]).index(PINMUX_VER)][1])
        #     else:    
        #         print('Pinmux version ' + PINMUX + ' not available.')
        #     if PINMUX_VER == '':
        #         print('Available pinmux versions: ' +
        #             ' '.join(np.array(elem_pinmuxes, dtype=object)[:, 0]))
        #         print('Please specify version or use latest, check help with -h option.')
        #         quit()

        # print('Pinmux: ' + PINMUX_VER)

        # # Create image path and pinmux path

        # print()
        # print('###############################################################################')
        # print()
        # print('Setting nvidia flashing folder')
        # print()
        # print('###############################################################################')
        # print()

        # C_IMAGE_NAME = ''
        # C_PINMUX_NAME = ''
        # L_DEVICE_JP_F = ''

        # SDK_MANAGER_JP = ''
        # SDK_MANAGER_DEVICE = ''

        # if DEVICE == 'xaviernx':
        #     if JETPACK == 'jp46':
        #         L_DEVICE_JP_F = 'JetPack_4.6_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
        #         SDK_MANAGER_JP = '4.6'
        #         SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        #     elif JETPACK == 'jp502':
        #         L_DEVICE_JP_F = 'JetPack_5.0.2_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
        #         SDK_MANAGER_JP = '5.0.2'
        #         SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        #     else:
        #         quit()
        # else:
        #     quit()

        # URL_PATH = URL_PATH_BASE + '/' + DEVICE + '/' + JETPACK + '/' + HWREV + '/'
        # C_IMAGE_NAME = IMAGE_VER
        # C_PINMUX_NAME = PINMUX_VER
        # L_NVIDIA_F = L_NVIDIA_F + '/' + L_DEVICE_JP_F

        # print('Using nvidia sdkmanager folder: ' + L_NVIDIA_F)

        # arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip']
        # #print(arg_flash)

        # if not os.path.isdir(L_NVIDIA_F):
        #     print('Non existing, please use nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
        #     if click.confirm('Do you want to continue?', default=True):
        #         arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip']
        #         #print(arg_flash)
        #         p = subprocess.call(arg_flash, stdout=subprocess.PIPE)
        #         input("Press Enter to continue after installing from sdkmanager finisher...")
        #         if not os.path.isdir(L_NVIDIA_F):
        #             print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
        #             quit()

        #     else:
        #         print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
        #         quit()

        # print()
        # print('###############################################################################')
        # print()
        # print('Downloading required versions')
        # print()
        # print('###############################################################################')
        # print()


        # # Download files urls
        # C_IMAGE_NAME_URL = URL_PATH + C_IMAGE_NAME
        # C_PINMUX_NAME_URL = URL_PATH + C_PINMUX_NAME

        # print('Using this folder to download: ' + L_FOLDER_D)

        # if not os.path.isdir(L_FOLDER_D):
        #     os.mkdir(L_FOLDER_D)

        # os.chdir(L_FOLDER_D)

        # # Download overlays
        # if DEVICE=='xaviernx' and JETPACK=='jp46':

        #     OVERLAY_URL_ = 'https://developer.nvidia.com/xnx-16gb-r3261-overlaytbz2'
        #     OVERLAY_NAME_ = 'xnx-16gb-r32.x-overlay.tbz2'

        #     print('Downloading: ' + OVERLAY_URL_)

        #     if FORCE:
        #         if os.path.exists(OVERLAY_NAME_):
        #             print('Overlay already present deleting!')
        #             os.remove(C_IMAGE_NAME)
        #             wget.download(
        #                 OVERLAY_URL_, OVERLAY_NAME_)
        #             print()
        #         else:
        #             wget.download(
        #                 OVERLAY_URL_, OVERLAY_NAME_)
        #             print()
        #     else:
        #         if os.path.exists(OVERLAY_NAME_):
        #             print('Overlay already present skipping download!')
        #         else:
        #             wget.download(
        #                 OVERLAY_URL_, OVERLAY_NAME_)
        #             print()
        # else:
        #     print('No overlays to apply.')

        # # Download image

        # print('Downloading: ' + C_IMAGE_NAME_URL)

        # if FORCE:
        #     if os.path.exists(C_IMAGE_NAME):
        #         print('Image already present deleting!')
        #         os.remove(C_IMAGE_NAME)
        #         wget.download(
        #             C_IMAGE_NAME_URL, C_IMAGE_NAME)
        #         print()
        #     else:
        #         wget.download(
        #             C_IMAGE_NAME_URL, C_IMAGE_NAME)
        #         print()
        # else:
        #     if os.path.exists(C_IMAGE_NAME):
        #         print('Image already present skipping download!')
        #     else:
        #         wget.download(
        #             C_IMAGE_NAME_URL, C_IMAGE_NAME)
        #         print()

        # # Download pinmuxes
        # print('Downloading: ' + C_PINMUX_NAME_URL)

        # if FORCE:
        #     if os.path.exists(C_PINMUX_NAME):
        #         print('Pinmux already present deleting!')
        #         os.remove(C_PINMUX_NAME)
        #         wget.download(
        #             C_PINMUX_NAME_URL, C_PINMUX_NAME)
        #         print()
        #     else:
        #         wget.download(
        #             C_PINMUX_NAME_URL, C_PINMUX_NAME)
        #         print()
        # else:
        #     if os.path.exists(C_PINMUX_NAME):
        #         print('Pinmux already present skipping download!')
        #     else:
        #         wget.download(
        #             C_PINMUX_NAME_URL, C_PINMUX_NAME)
        #         print()    

        # if os.path.exists('pinmuxes'):
        #     shutil.rmtree('pinmuxes')

        # with tarfile.open(C_PINMUX_NAME) as f:
        #     f.extractall('pinmuxes')

        # # Apply pinmuxes
        # muxes_to_copy = os.listdir(L_FOLDER_D + '/pinmuxes')

        # for file in muxes_to_copy:
        #     os.popen('cp ' + L_FOLDER_D + '/pinmuxes/' +
        #             file + ' ' + L_NVIDIA_F + '/bootloader/t186ref/' + file)
        #     print(file + ' has been applied as ' + L_NVIDIA_F + '/bootloader/t186ref/' + file)

        # # Apply image

        # os.popen('cp ' + L_FOLDER_D + '/' + C_IMAGE_NAME + ' ' + L_NVIDIA_F + '/bootloader/system.img')
        # print(C_IMAGE_NAME + ' has been applied as ' + L_NVIDIA_F + '/bootloader/system.img')

        # # Apply overlay
        # if DEVICE=='xaviernx' and JETPACK=='jp46':
        #     if os.path.exists(OVERLAY_NAME_.rsplit('.', 1)[0]):
        #         shutil.rmtree(OVERLAY_NAME_.rsplit('.', 1)[0])

        #     with tarfile.open(OVERLAY_NAME_) as f:
        #         f.extractall(OVERLAY_NAME_.rsplit('.', 1)[0])

        # files_to_copy = list()
        # for currentpath, folders, files in os.walk(L_FOLDER_D + '/' + OVERLAY_NAME_.rsplit('.', 1)[0] + '/Linux_for_Tegra/bootloader'):
        #     for file in files:
        #         files_to_copy.append(os.path.join(currentpath, file).split('Linux_for_Tegra', 1)[1])

        # for file in files_to_copy:
        #     os.popen('cp --remove-destination ' + L_FOLDER_D + '/' + OVERLAY_NAME_.rsplit('.', 1)[0] + '/Linux_for_Tegra' +
        #             file + ' ' + L_NVIDIA_F + file)
        #     print(L_FOLDER_D + '/' + file + ' has been applied as ' + L_NVIDIA_F + file)

        # # start flash
        # print()
        # print('###############################################################################')
        # print()
        # print('Starting flashing process')
        # print()
        # print('###############################################################################')
        # print()

        # os.chdir(L_NVIDIA_F)

        # arg_flash = ["sudo ./flash.sh jetson-xavier-nx-devkit-emmc mmcblk0p1",
        #             "jetson-xavier-nx-devkit-emmc", "mmcblk0p1"]
        # p = subprocess.Popen(arg_flash, stdout=subprocess.PIPE, shell=True)
        # for line in iter(p.stdout.readline, b''):
        #     print((re.sub('''.*?''', '', line.decode("utf-8"))).rstrip())
        # p.stdout.close()
        # p.wait()    

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