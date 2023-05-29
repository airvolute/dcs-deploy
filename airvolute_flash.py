#!/usr/bin/env python3

import xml.etree.ElementTree as ET
import numpy as np
import wget
import os
import tarfile
import argparse
from color import Color
from lxml import etree
import re
import subprocess
import shutil
import click
from git import Repo

URL_PATH_BASE = 'https://airvolute.com/download/Jetson_system/beta'

def add_common_parser(subparser):
    target_device_help = 'REQUIRED. Which type of device are we setting up (e.g. xaviernx ...).'
    subparser.add_argument(
        'target_device', help=target_device_help)

    jetpack_help = 'REQUIRED. Which jetpack are we going to use (e.g. jp46, jp502 ...).'
    subparser.add_argument(
        'jetpack', help=jetpack_help)

    hwrev_help = 'REQUIRED. Which hardware revision of carrier board are we going to use (e.g. rev4, rev5 ...).'
    subparser.add_argument(
        'hwrev', help=hwrev_help)

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

def create_parser():
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

    add_common_parser(flash)

    image_help = 'Specify which image revision are we going to use (e.g. image100, image101 ...), if not specified latest version will be used.'
    flash.add_argument(
        '--image', default='', help=image_help)

    pinmux_help = 'Specify which pinmux revision of carrier boar are we going to use (e.g. image100, image101 ...).'
    flash.add_argument(
        '--pinmux',  default='', help=pinmux_help)

    add_common_parser(compile_flash)


    return parser


def sanitize_args(parser, args):
    """
    Check if the supplied arguments are valid and perform some fixes
    """
    if args.command is None:
        print("No command specified!")
        parser.print_usage()
        quit()

def airvolute_sources(args):
    print('###############################################################################')
    print()
    print('Setting up versions')
    print()
    print('###############################################################################')
    print()

    DEVICE = args.target_device
    JETPACK = args.jetpack
    HWREV = args.hwrev
    L_NVIDIA_F = args.nvidia_f
    L_FOLDER_D = args.download_f
    FORCE = False

    if L_NVIDIA_F == '':
        L_NVIDIA_F = '/home/' + \
            os.getenv('USER', default=None)+'/nvidia/nvidia_sdk'
    if L_FOLDER_D == '':
        L_FOLDER_D = '/home/' + \
            os.getenv('USER', default=None)+'/nvidia/airvolute_download'
    if args.force == True:
        FORCE = True

    filename = get_sources_versions()

    tree = ET.parse(filename)
    root = tree.getroot()
    devices_list = []
    devices_list_names = []
    jp_list = []
    xml_path = []

    for x in root.findall('Device'):
        devices_list.append(x)
        devices_list_names.append(x.text.strip())

    # Check if device is compatible
    for elem in devices_list:
        if DEVICE in elem.text.strip():
            print('Device: ' + DEVICE)
            xml_path.append(elem)
            break

    if len(xml_path) != 1:
        print('Device: ' + DEVICE + ' not found!')
        print('Supported devices: ' + ' '.join(devices_list_names))
        quit()

    # Check if jetpack is compatible
    for elem in xml_path[0].findall('JP'):
        if JETPACK in elem.text.strip():
            print('Jetpack: ' + JETPACK)
            xml_path.append(elem)
            break

    if len(xml_path) != 2:
        print('Jetpack: ' + JETPACK + ' not found!')

        jp_list = []
        for x in xml_path[0].findall('JP'):
            jp_list.append(x.text.strip())
        print('Supported jetpacks: ' + ' '.join(jp_list))
        quit()

    # Get repo url and branch

    N_SOURCES_URL = ''
    N_GIT_BRANCH = ''

    if len(xml_path[1].findall('GitRepo')) == 1:
        pass
    else:
        print('Not well filled xml, multiple GitRepo')
        return

    for x in xml_path[1].findall('GitRepo'):
        xml_path.append(x)
        N_SOURCES_URL = x.text.strip()

    if len(xml_path[2].findall('GitBranch')) == 1:
        pass
    else:
        print('Not well filled xml, multiple GitBranch')
        return

    for x in xml_path[2].findall('GitBranch'):
        N_GIT_BRANCH = x.text.strip()


    print()
    print('###############################################################################')
    print()
    print('Setting nvidia flashing folder')
    print()
    print('###############################################################################')
    print()


    C_PINMUX_NAME = ''
    L_DEVICE_JP_F = ''

    SDK_MANAGER_JP = ''
    SDK_MANAGER_DEVICE = ''

    if DEVICE == 'xaviernx':
        if JETPACK == 'jp46':
            L_DEVICE_JP_F = 'JetPack_4.6_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
            SDK_MANAGER_JP = '4.6'
            SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        elif JETPACK == 'jp502':
            L_DEVICE_JP_F = 'JetPack_5.0.2_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
            SDK_MANAGER_JP = '5.0.2'
            SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        else:
            quit()
    else:
        quit()

    #URL_PATH = URL_PATH_BASE + '/' + DEVICE + '/' + JETPACK + '/' + HWREV + '/'
    L_NVIDIA_F = L_NVIDIA_F + '/' + L_DEVICE_JP_F

    print('Using nvidia sdkmanager folder: ' + L_NVIDIA_F)

    arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip']
    #print(arg_flash)

    if not os.path.isdir(L_NVIDIA_F):
        print('Non existing, please use nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
        if click.confirm('Do you want to continue?', default=True):
            arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip']
            print(arg_flash)
            p = subprocess.call(arg_flash, stdout=subprocess.PIPE)
            input("Press Enter to continue after installing from sdkmanager finisher...")
            if not os.path.isdir(L_NVIDIA_F):
                print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
                quit()

        else:
            print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
            quit()

    print()
    print('###############################################################################')
    print()
    print('Downloading required versions')
    print()
    print('###############################################################################')
    print()


    # Download files urls
    print(N_SOURCES_URL)
    print(N_GIT_BRANCH)

    print('Using this folder to download: ' + L_FOLDER_D)

    if not os.path.isdir(L_FOLDER_D):
        os.mkdir(L_FOLDER_D)

    os.chdir(L_FOLDER_D)
    
    if not os.path.isdir(L_FOLDER_D + '/' + N_GIT_BRANCH):
        print('Cloning ' + N_SOURCES_URL) 
        Repo.clone_from(N_SOURCES_URL, L_FOLDER_D + '/' + N_GIT_BRANCH, branch=N_GIT_BRANCH)
    elif FORCE:
        print('Deleting ' + L_FOLDER_D + '/' + N_GIT_BRANCH) 
        shutil.rmtree(L_FOLDER_D + '/' + N_GIT_BRANCH)
        print('Cloning ' + N_SOURCES_URL) 
        Repo.clone_from(N_SOURCES_URL, L_FOLDER_D + '/' + N_GIT_BRANCH, branch=N_GIT_BRANCH)

    if os.path.exists(L_NVIDIA_F + '/sources'):
        shutil.rmtree(L_NVIDIA_F + '/sources')
    
    os.popen('cp -r ' + L_FOLDER_D + '/' + N_GIT_BRANCH + ' ' + L_NVIDIA_F + '/sources')



def airvolute_flash(args):
    print('###############################################################################')
    print()
    print('Setting up versions')
    print()
    print('###############################################################################')
    print()

    DEVICE = args.target_device
    JETPACK = args.jetpack
    HWREV = args.hwrev
    IMAGE = args.image
    PINMUX = args.pinmux
    L_NVIDIA_F = args.nvidia_f
    L_FOLDER_D = args.download_f
    FORCE = False

    if L_NVIDIA_F == '':
        L_NVIDIA_F = '/home/' + \
            os.getenv('USER', default=None)+'/nvidia/nvidia_sdk'
    if L_FOLDER_D == '':
        L_FOLDER_D = '/home/' + \
            os.getenv('USER', default=None)+'/nvidia/airvolute_download'
    if IMAGE == '':
        USING_LATEST_IMG = True
    else:
        USING_LATEST_IMG = False
    if PINMUX == '':
        USING_LATEST_PINMUX = True
    else:
        USING_LATEST_PINMUX = False

    if args.force == True:
        FORCE = True

    filename = get_versions()

    tree = ET.parse(filename)
    root = tree.getroot()
    devices_list = []
    devices_list_names = []
    jp_list = []
    xml_path = []

    for x in root.findall('Device'):
        devices_list.append(x)
        devices_list_names.append(x.text.strip())

    # Check if device is compatible
    for elem in devices_list:
        if DEVICE in elem.text.strip():
            print('Device: ' + DEVICE)
            xml_path.append(elem)
            break

    if len(xml_path) != 1:
        print('Device: ' + DEVICE + ' not found!')
        print('Supported devices: ' + ' '.join(devices_list_names))
        quit()

    # Check if jetpack is compatible
    for elem in xml_path[0].findall('JP'):
        if JETPACK in elem.text.strip():
            print('Jetpack: ' + JETPACK)
            xml_path.append(elem)
            break

    if len(xml_path) != 2:
        print('Jetpack: ' + JETPACK + ' not found!')

        jp_list = []
        for x in xml_path[0].findall('JP'):
            jp_list.append(x.text.strip())
        print('Supported jetpacks: ' + ' '.join(jp_list))
        quit()

    # Check if hwrev is compatible
    for elem in xml_path[1].findall('HWRev'):
        if HWREV in elem.text.strip():
            print('HWRev: ' + HWREV)
            xml_path.append(elem)
            break

    if len(xml_path) != 3:
        print('HWRev: ' + HWREV + ' not found!')
        print('Supported HWRevs: ' + ' '.join(xml_path[1].findall('HWRev')))
        quit()

    # Check if image is compatible
    elem_image_list = []
    elem_image = []

    for elem in xml_path[2].findall('Image'):
        elem_image.append([elem.text.strip(), elem])
        elem_image_list.append(elem.text.strip())

    elem_image.sort(key=lambda x: x[0], reverse=True)

    # Get versions to be flashed
    IMAGE_VER = ''
    PINMUX_VER = ''

    if USING_LATEST_IMG:
        xml_path.append(elem_image[0][1])
        IMAGE_VER = elem_image[0][1].text.strip()
    else:
        if any(IMAGE in subl for subl in elem_image):
            IMAGE_VER = IMAGE
            xml_path.append(elem_image[list(np.array(elem_image, dtype=object)[:, 0]).index(IMAGE_VER)][1])
        else:    
            print('Image version ' + IMAGE + ' not available.')
        if IMAGE_VER == '':
            print('Available image versions: ' +
                  ' '.join(np.array(elem_image, dtype=object)[:, 0]))
            print('Please specify version or use latest, check help with -h option.')
            quit()

    print('Image: ' + IMAGE_VER)
    # Get pinmuxes to be flashed
    #list(np.array(elem_image, dtype=object)[:, 0]).index(IMAGE_VER)
    elem_pinmuxes_list = []
    elem_pinmuxes = []
    for elem in xml_path[3].findall('Pinmux'):
        elem_pinmuxes.append([elem.text.strip(), elem])
        elem_pinmuxes_list.append(elem.text.strip())

    elem_pinmuxes.sort(key=lambda x: x[0], reverse=True)

    if USING_LATEST_PINMUX:
        xml_path.append(elem_pinmuxes[0][1])
        PINMUX_VER = elem_pinmuxes[0][1].text.strip()
    else:
        if any(PINMUX in subl for subl in elem_pinmuxes):
            PINMUX_VER = PINMUX
            xml_path.append(elem_pinmuxes[list(np.array(elem_pinmuxes, dtype=object)[:, 0]).index(PINMUX_VER)][1])
        else:    
            print('Pinmux version ' + PINMUX + ' not available.')
        if PINMUX_VER == '':
            print('Available pinmux versions: ' +
                  ' '.join(np.array(elem_pinmuxes, dtype=object)[:, 0]))
            print('Please specify version or use latest, check help with -h option.')
            quit()

    print('Pinmux: ' + PINMUX_VER)

    # Create image path and pinmux path

    print()
    print('###############################################################################')
    print()
    print('Setting nvidia flashing folder')
    print()
    print('###############################################################################')
    print()

    C_IMAGE_NAME = ''
    C_PINMUX_NAME = ''
    L_DEVICE_JP_F = ''

    SDK_MANAGER_JP = ''
    SDK_MANAGER_DEVICE = ''

    if DEVICE == 'xaviernx':
        if JETPACK == 'jp46':
            L_DEVICE_JP_F = 'JetPack_4.6_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
            SDK_MANAGER_JP = '4.6'
            SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        elif JETPACK == 'jp502':
            L_DEVICE_JP_F = 'JetPack_5.0.2_Linux_JETSON_XAVIER_NX_TARGETS/Linux_for_Tegra'
            SDK_MANAGER_JP = '5.0.2'
            SDK_MANAGER_DEVICE = 'JETSON_XAVIER_NX_TARGETS'
        else:
            quit()
    else:
        quit()

    URL_PATH = URL_PATH_BASE + '/' + DEVICE + '/' + JETPACK + '/' + HWREV + '/'
    C_IMAGE_NAME = IMAGE_VER
    C_PINMUX_NAME = PINMUX_VER
    L_NVIDIA_F = L_NVIDIA_F + '/' + L_DEVICE_JP_F

    print('Using nvidia sdkmanager folder: ' + L_NVIDIA_F)

    arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip']
    #print(arg_flash)

    if not os.path.isdir(L_NVIDIA_F):
        print('Non existing, please use nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
        if click.confirm('Do you want to continue?', default=True):
            arg_flash = ['gnome-terminal','-e', 'sdkmanager --cli install  --logintype devzone --product Jetson  --targetos Linux --version ' + SDK_MANAGER_JP + ' --target ' + SDK_MANAGER_DEVICE + ' --deselect "Jetson SDK Components" --flash skip']
            #print(arg_flash)
            p = subprocess.call(arg_flash, stdout=subprocess.PIPE)
            input("Press Enter to continue after installing from sdkmanager finisher...")
            if not os.path.isdir(L_NVIDIA_F):
                print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
                quit()

        else:
            print('Non existing, please use manual nvidia sdkmanager to initialize this folder' + L_NVIDIA_F)
            quit()

    print()
    print('###############################################################################')
    print()
    print('Downloading required versions')
    print()
    print('###############################################################################')
    print()


    # Download files urls
    C_IMAGE_NAME_URL = URL_PATH + C_IMAGE_NAME
    C_PINMUX_NAME_URL = URL_PATH + C_PINMUX_NAME

    print('Using this folder to download: ' + L_FOLDER_D)

    if not os.path.isdir(L_FOLDER_D):
        os.mkdir(L_FOLDER_D)

    os.chdir(L_FOLDER_D)

    # Download overlays
    if DEVICE=='xaviernx' and JETPACK=='jp46':

        OVERLAY_URL_ = 'https://developer.nvidia.com/xnx-16gb-r3261-overlaytbz2'
        OVERLAY_NAME_ = 'xnx-16gb-r32.x-overlay.tbz2'

        print('Downloading: ' + OVERLAY_URL_)

        if FORCE:
            if os.path.exists(OVERLAY_NAME_):
                print('Overlay already present deleting!')
                os.remove(C_IMAGE_NAME)
                wget.download(
                    OVERLAY_URL_, OVERLAY_NAME_)
                print()
            else:
                wget.download(
                    OVERLAY_URL_, OVERLAY_NAME_)
                print()
        else:
            if os.path.exists(OVERLAY_NAME_):
                print('Overlay already present skipping download!')
            else:
                wget.download(
                    OVERLAY_URL_, OVERLAY_NAME_)
                print()
    else:
        print('No overlays to apply.')

    # Download image

    print('Downloading: ' + C_IMAGE_NAME_URL)

    if FORCE:
        if os.path.exists(C_IMAGE_NAME):
            print('Image already present deleting!')
            os.remove(C_IMAGE_NAME)
            wget.download(
                C_IMAGE_NAME_URL, C_IMAGE_NAME)
            print()
        else:
            wget.download(
                C_IMAGE_NAME_URL, C_IMAGE_NAME)
            print()
    else:
        if os.path.exists(C_IMAGE_NAME):
            print('Image already present skipping download!')
        else:
            wget.download(
                C_IMAGE_NAME_URL, C_IMAGE_NAME)
            print()

    # Download pinmuxes
    print('Downloading: ' + C_PINMUX_NAME_URL)

    if FORCE:
        if os.path.exists(C_PINMUX_NAME):
            print('Pinmux already present deleting!')
            os.remove(C_PINMUX_NAME)
            wget.download(
                C_PINMUX_NAME_URL, C_PINMUX_NAME)
            print()
        else:
            wget.download(
                C_PINMUX_NAME_URL, C_PINMUX_NAME)
            print()
    else:
        if os.path.exists(C_PINMUX_NAME):
            print('Pinmux already present skipping download!')
        else:
            wget.download(
                C_PINMUX_NAME_URL, C_PINMUX_NAME)
            print()    

    if os.path.exists('pinmuxes'):
        shutil.rmtree('pinmuxes')

    with tarfile.open(C_PINMUX_NAME) as f:
        f.extractall('pinmuxes')

    # Apply pinmuxes
    muxes_to_copy = os.listdir(L_FOLDER_D + '/pinmuxes')

    for file in muxes_to_copy:
        os.popen('cp ' + L_FOLDER_D + '/pinmuxes/' +
                 file + ' ' + L_NVIDIA_F + '/bootloader/t186ref/' + file)
        print(file + ' has been applied as ' + L_NVIDIA_F + '/bootloader/t186ref/' + file)

    # Apply image

    os.popen('cp ' + L_FOLDER_D + '/' + C_IMAGE_NAME + ' ' + L_NVIDIA_F + '/bootloader/system.img')
    print(C_IMAGE_NAME + ' has been applied as ' + L_NVIDIA_F + '/bootloader/system.img')

    # Apply overlay
    if DEVICE=='xaviernx' and JETPACK=='jp46':
        if os.path.exists(OVERLAY_NAME_.rsplit('.', 1)[0]):
            shutil.rmtree(OVERLAY_NAME_.rsplit('.', 1)[0])

        with tarfile.open(OVERLAY_NAME_) as f:
            f.extractall(OVERLAY_NAME_.rsplit('.', 1)[0])

    files_to_copy = list()
    for currentpath, folders, files in os.walk(L_FOLDER_D + '/' + OVERLAY_NAME_.rsplit('.', 1)[0] + '/Linux_for_Tegra/bootloader'):
        for file in files:
            files_to_copy.append(os.path.join(currentpath, file).split('Linux_for_Tegra', 1)[1])

    for file in files_to_copy:
        os.popen('cp --remove-destination ' + L_FOLDER_D + '/' + OVERLAY_NAME_.rsplit('.', 1)[0] + '/Linux_for_Tegra' +
                 file + ' ' + L_NVIDIA_F + file)
        print(L_FOLDER_D + '/' + file + ' has been applied as ' + L_NVIDIA_F + file)

    # start flash
    print()
    print('###############################################################################')
    print()
    print('Starting flashing process')
    print()
    print('###############################################################################')
    print()

    os.chdir(L_NVIDIA_F)

    arg_flash = ["sudo ./flash.sh jetson-xavier-nx-devkit-emmc mmcblk0p1",
                 "jetson-xavier-nx-devkit-emmc", "mmcblk0p1"]
    p = subprocess.Popen(arg_flash, stdout=subprocess.PIPE, shell=True)
    for line in iter(p.stdout.readline, b''):
        print((re.sub('''.*?''', '', line.decode("utf-8"))).rstrip())
    p.stdout.close()
    p.wait()


def get_versions():

    XML_URL = URL_PATH_BASE + '/versions.xml'
    print('Downloading: ' + XML_URL)

    if os.path.exists("local/versions.xml"):
        os.remove("local/versions.xml")

    wget.download(XML_URL, "local/versions.xml")
    print()
    return "local/versions.xml"

def get_sources_versions():

    #XML_URL = URL_PATH_BASE + '/versions_sources.xml'
    #print('Downloading: ' + XML_URL)
#
    #if os.path.exists("local/versions_sources.xml"):
    #    os.remove("local/versions_sources.xml")
#
    #wget.download(XML_URL, "local/versions_sources.xml")
    print()
    return "local/versions_sources.xml"


def list_all_versions(args):

    filename = get_versions()
    tree = ET.parse(filename)
    root = tree.getroot()
    test = ET.tostring(root, encoding='utf8', method='xml')
    test = re.sub('<.*?>', '', test.decode("utf-8"))
    print("".join([s for s in test.strip().splitlines(True) if s.strip()]))


def main():
    parser = create_parser()
    args = parser.parse_args()
    sanitize_args(parser, args)

    if args.command == 'list':
        list_all_versions(args)
        quit()
    elif args.command == 'flash':
        airvolute_flash(args)
    elif args.command == 'compile_flash':
        airvolute_sources(args)

if __name__ == "__main__":
    main()
