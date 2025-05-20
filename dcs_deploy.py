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
import yaml
from typing import Dict, List, Optional, Union, Tuple, Callable
from pathlib import Path
import termios
import tty
import select

dcs_deploy_version = "3.0.0"


# example: retcode = cmd_exec("sudo tar xpf %s --directory %s" % (self.rootfs_file_path, self.rootfs_extract_dir))
# NOTE: return value changes when capture_output is set!
def cmd_exec(command_line: str, print_command: bool = False, capture_output: bool = False) -> Union[int, Tuple[int, Optional[str]], Optional[str]]:
    """
    Executes a shell command.

    Args:
        command_line: Command to run as a string.
        print_command: Print the command before executing.
        capture_output: If True, captures and returns stdout.

    Returns:
        - int: exit code only, if capture_output=False
        - tuple: (exit code, stdout output as string), if capture_output=True
    """
    if print_command:
        print("calling:", command_line)

    try:
        result = subprocess.run( command_line, shell=True, capture_output=capture_output, text=True)
        if capture_output:
            return result.returncode, result.stdout, result.stderr
        else: # for backward compatibility use single return code
            return result.returncode

    except Exception as e:
        print(f"Command '{command_line}' execution failed! Error: {e}")
        exit(5)

# Usage:
# call_bash_function("tools.func", "update_num_sectors", "partition_layout.xml", "123456")
def call_bash_function(script_file: str, function_name: str, use_sudo: bool, *args) -> int:
    args_joined = " ".join(args)
    sudo=""
    if use_sudo:
        sudo="sudo"
    full_command = f'{sudo} bash -c "source {script_file} && {function_name} {args_joined}"'
    return cmd_exec(full_command, print_command=True)

def is_key_pressed() -> Optional[str]:
    """Non-blocking key press detection"""
    dr, _, _ = select.select([_sys.stdin], [], [], 0)
    if dr:
        return _sys.stdin.read(1)
    return None

def wait_with_check(
    wait_time: float,
    check_func: Callable[[], int], #eg. test() -> int (0) -
    interval: Optional[float] = 0.1,
    esc_callback: Optional[Callable[[], None]] = lambda: exit(1),
    valid_ret_val: Optional[List[int]] = None,
):
    """
    Waits for `wait_time` seconds, checking device state every `interval`.
    Exits if ESC is pressed, calling `esc_callback` if defined.
    
    Args:
        wait_time (float): Total wait time in seconds.
        check_func (Callable): Function called each interval; should return int.
        interval (float): Time between checks.
        esc_callback (Callable): Function to call if ESC is pressed.
        valid_ret_val (int, optional): If provided, check_func return must match.
    """
    print(f"Waiting for up to {wait_time} seconds. Press ESC to exit.")
    start = time.time()
    if valid_ret_val == None:
        valid_ret_val = [0]

    # Save terminal settings
    fd = _sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    tty.setcbreak(fd)
    cnt = 0
    try:
        while (elapsed := time.time() - start) < wait_time:
            key = is_key_pressed()
            if key == '\x1b':  # ESC
                print("\nESC pressed. Exiting ...")
                if esc_callback:
                    esc_callback()
                return 1

            ret = check_func()
            if valid_ret_val is not None and ret in valid_ret_val:
                print("Valid state detected ...")
                return 0

            time.sleep(interval)
            cnt +=1
            if (cnt %10 == 0):
                print(".", end="",  flush=True)
    finally:
        # Restore terminal settings
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)

    print("Waiting finished.")
    return 2

def is_jetson_orin_or_xavier_in_rcm(print_msg=False) -> bool:
    # USB device IDs for Jetson Xavier and Orin in RCM mode
    # update from Linux_for_Tegra/tools/kernel_flash/l4t_initrd_flash.sh
    known_rcm_ids = {
        "0955:7018",  # TX2i
        "0955:7418",  # TX2 4GB
        "0955:7c18",  # TX2, TX2 NX
        "0955:7019",  # AGX Xavier
        "0955:7819",  # AGXi
        "0955:7919",  # AGXi
        "0955:7023",  # AGX Orin
        "0955:7223",  # AGX Orin 32GB
        "0955:7323",  # Orin NX 16GB (p3767-0000)
        "0955:7423",  # Orin NX 8GB (p3767-0001)
        "0955:7523",  # Orin Nano 8GB (p3767-0003)
        "0955:7623",  # Orin Nano 4GB (p3767-0004)
        "0955:7e19",  # NX
    }

    retcode, output, _ = cmd_exec("lsusb", capture_output=True)
    if retcode != 0 or output is None:
        print("ERROR: Could not run lsusb.")
        return False

    for line in output.strip().splitlines():
        for dev_id in known_rcm_ids:
            if dev_id in line:
                if print_msg: print(f"Found device in RCM mode: {line.strip()}")
                return True

    if print_msg: print("No Jetson Xavier/Orin found in RCM mode.")
    return False

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
        self.last_step = False
        self.load()

        
    def load(self):
        if os.path.isfile(self.status_file_name):
            with open(self.status_file_name, "r") as status_file:
                self.status = json.load(status_file)
        else:
            self.status = {}
        self._init_identifier()
        self._init_group_status()
        self._init_valid_retval()
    
    def _init_valid_retval(self):
        
        if "valid_retval" in self.status:
            self.valid_retval = self.status["valid_retval"]
        else:
            self.valid_retval = {}
        self.status["valid_retval"] = self.valid_retval

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
        #print("input from removing identifier:", identifier)
        if remove_list == []:
            return identifier
        # remove not matching identifiers
        cleaned_identifier = identifier[:] # copy identifiers into new list
        for remove in remove_list:
            if remove in cleaned_identifier:
                cleaned_identifier.remove(remove)
        #print("output from removing identifier:", cleaned_identifier)
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
    
    # True when states are equal
    def compare_states(self, group, prefix, expected_state_list):
        all_states = self.status[group]["states"]
        found_suffixes = [key[len(prefix):] for key in all_states if key.startswith(prefix)]
        return set(found_suffixes) == set(expected_state_list), {"new": set(expected_state_list) - set(found_suffixes), "missing": set(found_suffixes) - set(expected_state_list)}

    def get_group(self, group = None):
        if group == None:
            return self.group
        if not group in self.status:
            return None
        return group

    def change_group(self, group):
        self.group = group
        if not group in self.status:
            self._init_group_status()

    def set_last_step(self):
        self.last_step = True
    
    def get_last_step(self):
        return self.last_step
    
    def set_processing_step(self, processing_step_name:str):
        print("-"*35 + f" {self.group} - {processing_step_name} " + "-"*35)
        self.last_processing_step = processing_step_name
        self.status[self.group]["last_processing_step"] = processing_step_name
        self.status[self.group]["states"][processing_step_name] = -1
        self.status[self.group]["status"] = False
        self.save()

    def set_status(self, status:int, processing_step_name:str = None, last_step = False, valid_retval:List = []):
        if processing_step_name == None:
            processing_step_name = self.last_processing_step
        states = self.status[self.group]["states"]
        states[processing_step_name] = status
        if len(valid_retval):
            self.valid_retval[processing_step_name] = valid_retval
        if self.last_step == True or last_step == True:
            self.last_step = False
            # check all status codes
            self.check_status()
        self.save()
    
    def check_status(self, group = None):
        if group == None:
            group = self.group
        states = self.status[group]["states"]
        self.status[group]["status"] = True
        for key in states:
            valid_retval = [0] if key not in self.valid_retval else self.valid_retval[key]
            if states[key] not in valid_retval:
                self.status[group]["status"] = False
                break
    
    def get_status(self, group = None):
        #check if configuration was deleled. If yes, reload default configuration
        if not os.path.isfile(self.status_file_name):
            self.load()

        if group == None:
            group = self.group
        return self.status[group]["status"]


class OverlayFunction:
    def __init__(self, name: str, fn_type:str, overlay_name: str, cmd: str, args: List[str], env:str,  options: List):
        self.name = name
        self.overlay_name = overlay_name
        self.cmd = cmd
        self.args = args
        self.type = fn_type
        self.env = env
        self.options = options
        self.app_dir=os.getcwd() # at beginning current directory is set to app

    def resolve(self, keymap: Dict[str, str], general_args, overlay_base_dir : Path) -> str:
        print(overlay_base_dir)
        resolved_args = []
        for arg in self.args:
            if arg.startswith("<") and arg.endswith(">"):
                key = arg.strip("<>")
                if key not in keymap:
                    raise ValueError(f"[{self.name}] Missing value for key: <{key}> in overlay '{self.overlay_name}'")
                resolved_args.append(keymap[key])
            else:
                resolved_args.append(arg)
        
        return f"{self.app_dir}/{overlay_base_dir}/{self.overlay_name}/{self.cmd} {general_args} {' '.join(resolved_args)}"


class FunctionOverlayRegistry:
    def __init__(self, overlays_base_path, overlay_args):
        self.keymap = {}
        self._fucnt_overlays: List[str] = []
        self._registry: Dict[str, List[OverlayFunction]] = {}
        self.overlays_base_path : Path = Path(overlays_base_path)
        self.register_yaml: str = "register.yaml"
        self.overlay_args = overlay_args
        #override if needed
        self.valid_fn_names = {'flash-gen-prepare', 'flash-gen-prepare-is-needed', 'img-gen-internal', 'img-gen-internal-prepare', 'img-gen-external', 'img-gen-cleanup', 'get-img-type'}


    def register_overlay(self, overlay_name: str):
        if overlay_name in self._fucnt_overlays:
            raise ValueError(f"Overlay '{overlay_name}' already registered")
        
        
        overlay_register_file_path = self.overlays_base_path / overlay_name / self.register_yaml
        if not overlay_register_file_path.exists():
            print(f"Overlay '{overlay_name}' do not register functions")
            return 1

        
        with open(overlay_register_file_path, 'r') as f:
            data = yaml.safe_load(f)

        #
        fn_list =  data.get('functions', {}).items()
        for fn_name, fn_data in fn_list:
            if fn_name not in self.valid_fn_names:
                raise ValueError(f"Function '{fn_name}' is not allowed")

            cmd = fn_data.get('cmd', "")
            args = fn_data.get('args', [])
            env = fn_data.get('get-env', "")
            fn_type = fn_data.get('type',"")
            options = fn_data.get('options',[])

            fn = OverlayFunction(fn_name, fn_type, overlay_name, cmd, args, env, options)
            self._registry.setdefault(fn_name, []).append(fn)

        self._fucnt_overlays.append(overlay_name)
        print(f"Overlay {overlay_name} register functions:")
        print(fn_list)
        return 0

    def is_registred(self, overlay_name:str):
        if overlay_name in self._fucnt_overlays:
            return True
        return False

    def set_special_vars(self, keymap: Dict[str, str]):
        """Set known values for placeholders like BOARD_CONFIG_NAME"""
        self.keymap = keymap
    
    def add_special_var(self, var: Dict[str, str] ):
        self.keymap = {**self.keymap, **var }

    def get(self, fn_name: str) -> List[Dict]:
        out=[]
        for fn in self._registry[fn_name]:
            if fn.type == "lt4-initrd-params":
                out.append(
                    {
                        "overlay": fn.overlay_name,
                        "cmd": fn.resolve(self.keymap, self.overlay_args,  self.overlays_base_path),
                        "env":fn.env
                    })
            elif fn.type == "cmd":
                out.append(
                    {
                        "overlay": fn.overlay_name,
                        "cmd": fn.resolve(self.keymap, self.overlay_args, self.overlays_base_path),
                    })
            elif fn.type == "option":
                out.append(fn.options)
        return out

class FunctionOverlaysFlashGen(FunctionOverlayRegistry):
    def __init__(self, overlays_base_path, overlay_args, processing_status: ProcessingStatus):
        super().__init__(overlays_base_path, overlay_args)
        self.processing_status = processing_status
        self.valid_functions={}
        self.valid_functions["lt4_initrd_params"] = ["img-gen-internal", "img-gen-external"]
        self.valid_functions["cmd"] = ["img-gen-cleanup", "img-gen-internal-prepare", "flash-gen-prepare-is-needed", "flash-gen-prepare"]
        self.valid_functions["option"] = ["get-img-type"]
        self.setup_valid_fn_names()
        self.call_cnt={}

    def setup_valid_fn_names(self):
        self.valid_fn_names = {
            fn_name
            for fn_list in self.valid_functions.values()
            for fn_name in fn_list
        }

    def _verify_overlay_fn_type(self, fn: OverlayFunction, required_fn_type: str):
            if fn.type != required_fn_type:
                self.processing_status.set_status(-1, last_step=True)
                raise ValueError(f"Error occured when verifying registred overlay function - {fn.name} - overlay must be {fn.type} type only!")
    
    def inc_call_cnt(self, fn_name, fn_type):
        keyword=f"{fn_name}.{fn_type}"
        self.call_cnt[keyword] = (self.call_cnt[keyword] +  1) if keyword in self.call_cnt else 0
        return self.call_cnt[keyword]
        
    
    def resolve_lt4_initrd_params(self, fn_name, overlay_name = None) -> Dict:
        fn_type = "lt4-initrd-params"
        out_msg=""
        env=""
        if fn_name not in self._registry:
            print(f"Calling {fn_name} not registered in function overlays!")
            return {"args":out_msg, "env": env}
         
        overlay_fncts = self._registry[fn_name]
        # test if registred for odmfuse
        if len(overlay_fncts) == 0:
            return None
        
        is_last_step_set = self.processing_status.get_last_step()

        for fn in overlay_fncts:
            # if specified only one function is called
            if overlay_name != None:
                if overlay_name != fn.overlay_name:
                    continue
            self.processing_status.set_processing_step(f"fn_overlay@{fn_name}.{fn_type}_{self.inc_call_cnt(fn_name, fn_type)}")
            self._verify_overlay_fn_type(fn, fn_type)
            multi_ret = cmd_exec(fn.resolve(self.keymap, self.overlay_args,  self.overlays_base_path), capture_output=True, print_command=True)
            print(f"overlay function '{fn.overlay_name}.{fn.name}.{fn.type}' returned:{multi_ret}")
            ret, out_msg_partial, stderr_msg = multi_ret
            if ret != 0:
                self.processing_status.set_status(-2, last_step=True)
                raise ValueError(f"Error occured when callig overlay function '{fn.overlay_name}' - {stderr_msg} - {ret}")
            out_msg += f"{out_msg_partial} "
            if fn.env != None:
                env += f"{fn.env} "
            self.processing_status.set_status(ret, last_step = is_last_step_set)
        return {"args":out_msg, "env": env}
    
    def resolve_cmd(self, fn_name, overlay_name = None) -> Dict:
        fn_type = "cmd"
        if fn_name not in self._registry:
            print(f"Calling {fn_name} not registered in function overlays!")
            return None
        overlay_fncts = self._registry[fn_name]

        is_last_step_set = self.processing_status.get_last_step()

        out_ret=0
        for fn in overlay_fncts:
            # if specified only one function is called
            if overlay_name != None:
                if overlay_name != fn.overlay_name:
                    continue
            self.processing_status.set_processing_step(f"fn_overlay@{fn_name}.{fn_type}_{self.inc_call_cnt(fn_name, fn_type)}")
            self._verify_overlay_fn_type(fn, fn_type)
            ret = cmd_exec(fn.resolve(self.keymap, self.overlay_args,  self.overlays_base_path), print_command=True)
            print(f"overlay function '{fn.overlay_name}.{fn.name}.{fn.type}' returned:{ret}")
            if fn_name == "flash-gen-prepare-is-needed" and ret > 1: # just 0, or 1 are valid, others are errors, then exit app:
                self.processing_status.set_status(ret, last_step=True, valid_retval = [0, 1])
                raise ValueError(f"Error occured when callig overlay function '{fn.overlay_name}'. Please check previous messages.")
            out_ret += ret
            self.processing_status.set_status(ret, last_step = is_last_step_set, valid_retval = [0, 1] if fn_name == "flash-gen-prepare-is-needed" else [])
        return ret
    
    def resolve_options(self, fn_name, overlay_name = None) -> str:
        fn_type = "option"
        out = []
        if fn_name not in self._registry:
            print(f"Calling {fn_name} not registered in function overlays!")
            return out

        overlay_fncts = self._registry[fn_name]

        is_last_step_set = self.processing_status.get_last_step()
        
        for fn in overlay_fncts:
            # if specified only one function is called
            if overlay_name != None:
                if overlay_name != fn.overlay_name:
                    continue
            self.processing_status.set_processing_step(f"fn_overlay@{fn_name}.{fn_type}_{self.inc_call_cnt(fn_name, fn_type)}")
            self._verify_overlay_fn_type(fn, fn_type)
            out.append(" ".join(fn.options))
            self.processing_status.set_status(0, last_step = is_last_step_set)
        return out
    
    def exec_function(self, fn_name:str, overlay_name:str):
        if fn_name in  self.valid_functions["lt4_initrd_params"]:
            return self.resolve_lt4_initrd_params(fn_name, overlay_name)
        elif fn_name in self.valid_functions["option"]:
            return self.resolve_options(fn_name, overlay_name)
        elif fn_name in self.valid_functions["cmd"]:
            return self.resolve_cmd(fn_name, overlay_name)
        else:
            raise(ValueError(f"Uknown function name! ({fn_name})"))
            
    
class DcsDeploy:
    def __init__(self):
        self.check_dependencies()
        self.parser = self.create_parser()
        self.args = self.parser.parse_args()
        self.process_optional_args()
        self.sanitize_args()
        self.selected_config_name = None
        self.load_db()
        self.local_overlay_dir = os.path.join('.', 'local', 'overlays')
        self.dsc_deploy_app_dir = os.path.abspath(os.path.join('.'))
        if self.args.command != 'list':
            self.load_selected_config()
            self.init_filesystem()
            self.check_optional_arguments()


    def add_common_parser(self, subparser):
        target_device_help = 'REQUIRED. Which type of device are we setting up. Options: [orin_nx, xavier_nx]'
        subparser.add_argument('target_device', help=target_device_help)

        jetpack_help = 'REQUIRED. Which jetpack are we going to use. Options: [512, 51].'
        subparser.add_argument('jetpack', help=jetpack_help)

        hwrev_help = 'REQUIRED. Which hardware revision of carrier board are we going to use. Options: [1.2, 2.0].'
        subparser.add_argument('hwrev', help=hwrev_help)

        board_expander_help = 'REQUIRED. Which board expander are we going to use. Options: [none, default].'
        subparser.add_argument('board_expansion', help=board_expander_help)

        storage_help = 'REQUIRED. Which storage medium are we going to use. Options: [emmc, nvme].'
        subparser.add_argument('storage', help=storage_help)

        rootfs_type_help = 'REQUIRED. Which rootfs type are we going to use. Options: [minimal, full, airvolute].'
        subparser.add_argument('rootfs_type', help=rootfs_type_help)
        
        force_help = 'Files will be deleted, downloaded and extracted again.'
        subparser.add_argument('--force', action='store_true', help=force_help)

        regen_help = 'Regenerate files. Extract resources and apply them again'
        subparser.add_argument('--regen', action='store_true', help=regen_help)

        ab_partition_help = 'Prepare ab partion for system update. Only available for nvme devices'
        subparser.add_argument('--ab_partition', action='store_true', help=ab_partition_help)

        opt_app_size_help = 'Set APP partition size in GB. Use when you get "No space left on device" error while flashing custom rootfs'
        subparser.add_argument('--app_size', help=opt_app_size_help)

        opt_nvme_disk_size_help = 'Set NVME disk size in bytes necessary for preparing partition layout. Use disk tools eg.'\
                                  '`fdisk -l /dev/<your disc> to read number. Default: 128035676160 (128GiB)'
        subparser.add_argument('--nvme_disk_size', help=opt_nvme_disk_size_help, type=int, default=128035676160)

        rootfs_help = 'Path to customized root filesystem. Keep in mind that this needs to be a valid tbz2 archive.' 
        subparser.add_argument('--rootfs', help=rootfs_help)

    def create_parser(self):
        """
        Create an ArgumentParser and all its options
        """
        parser = argparse.ArgumentParser()
        subparsers = parser.add_subparsers(dest='command', help='Command')

        list = subparsers.add_parser(
            'list', help='list available versions')

        list_local_overlays_help = 'List existing local overlays'

        list.add_argument('--local-overlays', action='store_true', help=list_local_overlays_help)

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
        # unify specific parameters into list
        update_to_list_fields = ['device', 'board', 'board_expansion', 'storage']
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
        #return os.path.dirname(path)

    def cleanup_old_download_dir(self):
        old_download_dir = self.config['device'] + '_' + self.config['storage'] + '_' + self.config['board'] + '_' + self.config['board_expansion'] + '_'
        
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
            self.config['board_expansion'] + '_' +
            self.config['l4t_version'] + '_' +
            self.config['rootfs_type']
        )

        self.home = os.path.expanduser('~')
        self.dsc_deploy_root = os.path.join(self.home, '.dcs_deploy')
        self.download_path = os.path.join(self.dsc_deploy_root, 'download')
        self.flash_path = os.path.join(self.dsc_deploy_root, 'flash', config_relative_path)
        self.rootfs_extract_dir = os.path.realpath(os.path.join(self.flash_path, 'Linux_for_Tegra', 'rootfs'))
        self.l4t_root_dir = os.path.realpath(os.path.join(self.flash_path, 'Linux_for_Tegra'))
        self.op_tee_tools_path = os.path.realpath(os.path.join(self.l4t_root_dir, 'source', 'public', 'nvidia-jetson-optee-source.tbz2'))
        self.op_tee_tools_dir = os.path.realpath(os.path.join(self.l4t_root_dir, 'source', 'public'))
        self.apply_binaries_path = os.path.join(self.l4t_root_dir, 'apply_binaries.sh')
        self.create_user_script_path = os.path.join(self.l4t_root_dir, 'tools', 'l4t_create_default_user.sh')

        # generate download resource paths
        resource_keys = ["rootfs", "l4t", "nvidia_overlay", "airvolute_overlay", "nv_ota_tools", "public_sources" ]
        self.resource_paths = {}

        for res_name in resource_keys:
            #print(" %s key: %s" % (res_name, self.config[res_name]))
            if res_name == "rootfs" and self.args.rootfs is not None:
                if os.path.exists(self.args.rootfs):
                    self.resource_paths[res_name] = self.args.rootfs
                else:
                    print(f"Error: The specified rootfs path does not exist: {self.args.rootfs}")
                    exit(1)
                self.resource_paths[res_name] = self.args.rootfs
                continue
            self.resource_paths[res_name] = self.get_download_file_path(self.get_resource_url(res_name))

        if not os.path.isdir(self.download_path):
            os.makedirs(self.download_path)

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
            print("cleanup_flash_dir...")
            cmd_exec(f"sudo rm -rf {self.flash_path} && sync")
            print("creating: " + self.flash_path)
            os.makedirs(self.flash_path)

    def check_dependencies(self):
        l4t_tool = ["abootimg", "binfmt-support", "binutils", "cpp", "device-tree-compiler", "dosfstools", "lbzip2",
                     "libxml2-utils", "nfs-kernel-server", "python3", "python3-yaml", "qemu-user-static", "sshpass",
                     "udev", "uuid-runtime", "whois", "openssl", "cpio", "lz4"]
        l4t_other_dependencies = ["python-is-python3"]
        dcs_deploy_dependencies = ["qemu-user-static", "sshpass", "abootimg", "lbzip2", "jq", "coreutils", "findutils" ]
        disk_enc_dependencies = ["cryptsetup"]
        op_tee_dependencies = ["python3-cryptography", "python3-pycryptodome"]
        
        dependencies = l4t_tool
        # append dcs_deploy_dependencies which are unique
        for dependency in dcs_deploy_dependencies + l4t_other_dependencies + disk_enc_dependencies + op_tee_dependencies:
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
            # return only resource which is possible to download
            if(self.get_resource_url(resouce) != None):
                res += [resouce]
        return res

    def download_resources(self):
        for missing_resource in self.get_missing_resources(force_all_missing = self.args.force):
            if missing_resource == "rootfs" and self.args.rootfs is not None:
                print("rootfs will not be downloaded, because you want to use custom rootfs.")
                continue
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
        is_same, status = self.prepare_status.compare_states("prepare", "install_local_overlay@", self.get_local_overlays())
        if self.prepare_status.get_status() == True and self.prepare_status.is_identifier_same_as_prev(["--regen", "--force"]) and is_same:
            print("registering local overlays!")
            self.register_local_overlays()
            print("Binaries already prepared!. Skipping!")
            return 0
        else:
            if not is_same:
                print(f"local overlays was changed!- {status}")
                print("Sources must be regenerated!")
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
        
        if self.get_resource_url('public_sources') != None:
            print(f'Extracting Nvidia OP-TEE tools to {self.op_tee_tools_dir}...')
            ret = self.extract_resource('public_sources')
            ret = extract(self.op_tee_tools_path, self.op_tee_tools_dir)

        # Regenerate ssh access in rootfs
        print("Purging ssh keys, this part needs sudo privilegies:")
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        ret += cmd_exec("sudo resources/purge_ssh_keys.sh " + 
                 os.path.join(self.rootfs_extract_dir, 'home', 'dcs_user','.ssh'))


        print('Installing overlays ...')
        ret += self.install_overlays(self.register_local_overlays(), is_last_install_step = True)
        if(ret):
            print(f"Errors were found when callling prepare_sources_production - {ret}")
            exit(1)

    def prepare_airvolute_overlay(self):
        return self.extract_resource('airvolute_overlay')

    def prepare_nvidia_overlay(self):
        return self.extract_resource('nvidia_overlay')

    def match_selected_config(self):
        """
        Get selected config based on loaded database from console arguments enterred by user
        """
        # do not search again
        if self.selected_config_name != None:
            return self.selected_config_name
        
        for config in self.config_db:
            if (self.args.target_device in self.config_db[config]['device'] and
                self.args.jetpack == self.config_db[config]['l4t_version'] and
                self.args.hwrev in self.config_db[config]['board'] and
                self.args.board_expansion in self.config_db[config]['board_expansion'] and
                self.args.storage in self.config_db[config]['storage'] and
                self.args.rootfs_type == self.config_db[config]['rootfs_type']):
                return config
                
        return None
    
    def get_local_overlays(self, src="config"):
        print("overlay dir:", self.local_overlay_dir)
        allowed_src=["config", "directory"]
        if src not in allowed_src:
            raise ValueError(f"Wrong src={src}")

        if hasattr(self, "config") and "local_overlays" in self.config:
            print("Selecting overlays list from configuration['local_overlays']")
            cfg_overlays_list = self.config["local_overlays"]
        if src == "directory":
            print("Selecting overlays list from local/overlays directory!")
            cfg_overlays_list = os.listdir(self.local_overlay_dir)
            cfg_overlays_list.remove("lib")

        print("cfg_overlays_list: " + str(cfg_overlays_list))
        return cfg_overlays_list

    def get_overlay_path(self,overlay_name):
        return os.path.join(self.local_overlay_dir, overlay_name)

    def register_local_overlays(self):
        all_cfg_overlays_list = self.get_local_overlays()

        registred_local_overlays = []
        # prepare function overlays
        self.functionOnverlays = FunctionOverlaysFlashGen(self.local_overlay_dir, self.get_base_overlay_params(), self.prepare_status)

        for item in all_cfg_overlays_list:
            if isinstance(item, dict):
                overlay_name = next(iter(item)) #return key when config is used eg. item = {"secureboot": {"config": "custom.yaml"}} -> "secureboot"
            else:
                overlay_name = item

            if not os.path.exists(self.get_overlay_path(overlay_name)):
                print(f"Overlay {overlay_name} does not exist! Quitting!")
                quit()

            registred_local_overlays.append(item)
            self.functionOnverlays.register_overlay(overlay_name) #function overlays support only directories

        print("registred local overlays:" + str(registred_local_overlays))
        return registred_local_overlays

    def install_overlays(self, overlay_list, is_last_install_step=False):
        overlays = overlay_list

        total = len(overlay_list)
        step_idx = 0
        for overlay in overlays:
            step_idx += 1

            if isinstance(overlay, dict):
                overlay, args = next(iter(overlay.items()))
            else:
                overlay = overlay
                args = {}

            print(f"[{step_idx}/{total}] installing overlay {overlay}")
            self.prepare_status.set_processing_step(f"install_local_overlay@{overlay}")

            if os.path.isdir(self.get_overlay_path(overlay)):
                ret = self.install_overlay_dir(overlay, args)
            else:  # file_or_dir == "files"
                ret = self.install_overlay_file(overlay, args)

            is_last = step_idx == total and is_last_install_step
            self.prepare_status.set_status(ret, last_step=is_last)

            with_error = "." if not ret else " with error!"
            print(f"installing overlay {overlay} finished{with_error} ret:({ret})")

            if ret:
                if os.path.isdir(self.get_overlay_path(overlay)):
                    return 10
                else:
                    return 11
        return 0


    def get_base_overlay_params(self):
        return " ".join((
                self.rootfs_extract_dir, 
                self.args.target_device, 
                self.args.jetpack, 
                self.args.hwrev, 
                self.args.board_expansion, 
                self.args.storage, 
                self.args.rootfs_type))

    def install_overlay_file(self, overlay_name, custom_args=None):
        if custom_args is None:
            custom_args = {}

        overlay_script_name = os.path.join(self.local_overlay_dir, overlay_name)

        custom_args_str = " ".join(f"{k}={v}" for k, v in custom_args.items())

        cmd = (f"sudo {overlay_script_name} {self.get_base_overlay_params()} {custom_args_str}")
        ret = cmd_exec(cmd, print_command=True)
        return ret
    
    def install_overlay_dir(self, overlay_name, custom_args=None):
        if custom_args is None:
            custom_args = {}

        overlay_script_name = os.path.join(self.local_overlay_dir, overlay_name, "apply_" + overlay_name + ".sh")

        custom_args_str = " ".join(f"{k}={v}" for k, v in custom_args.items())

        cmd = (f"sudo {overlay_script_name} {self.get_base_overlay_params()} {custom_args_str}")
        ret = cmd_exec(cmd, print_command=True)
        return ret

    def print_config(self, config, items):
        for item in items:
            print("%s: %s" % (item, config[item]))

    def print_user_config(self):
        items = ["target_device", "jetpack", "hwrev", "board_expansion", "storage", "rootfs_type" ]
        #print("==== user configuration ====")
        self.print_config(self.args.__dict__, items)

    def list_all_versions(self):
        for config in self.config_db:
            items = ['device', 'l4t_version', 'board', 'board_expansion', 'storage', 'rootfs_type']
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
        
        # update selected config according user enterred parameters
        self.config = self.config_db
        self.config['device'] = self.args.target_device
        self.config['board'] = self.args.hwrev
        self.config['board_expansion'] = self.args.board_expansion
        self.config['storage'] = self.args.storage

        self.selected_config_name = config
    
    # default size 128GiB
    def get_ext_partition_layout_file(self, ab_partition, rfs_enc, nvme_disk_size_B=128035676160):
        src_part_layout_file_name = ""
        path_prefix = "tools/kernel_flash/flash_l4t_nvme"
        
        rootfs_prefix = "_rootfs" if ab_partition or rfs_enc else ""
        ab = "_ab" if ab_partition == True else ""
        enc = "_enc" if rfs_enc == True else ""
        src_part_layout_file_base_name=f"{path_prefix}{rootfs_prefix}{ab}{enc}"
        src_part_layout_file_name =  os.path.abspath(f"{src_part_layout_file_base_name}.xml")
        print(f"selecting source partition file: {src_part_layout_file_name}")
        # update partition number of sectors and generate new xml <file>_custom.xml
        ret = call_bash_function(f"{self.dsc_deploy_app_dir}/scripts/common.func", "part_xml_update_num_sectors", True, src_part_layout_file_name, str(nvme_disk_size_B//512))
        if ret != 0:
            raise  Exception(f'part_xml_update_num_sectors returned {ret}')
        out_part_layout_file_name=f"{src_part_layout_file_base_name}_custom.xml"
        return os.path.relpath(out_part_layout_file_name)


    def setup_initrd_flashing(self):
        os.chdir(self.l4t_root_dir)
        #set variables for initrd flash
        self.flash_script_path = os.path.relpath('tools/kernel_flash/l4t_initrd_flash.sh')
        self.board_system_vars=""
        self.rfs_enc = False
        self.gen_external_only = False
        self.env_vars = ""
        self.opt_app_size_arg = ""
        
        self.flashing_network=""
        if self.config['storage'] == 'nvme':
            self.flashing_network = "--network usb0"

        self.internal_flash_options = ""
        if self.config['device'] in ['orin_nx', 'orin_nx_8gb', 'orin_nano_8gb', 'orin_nano_4gb']:
            # based on docu from tools/kerenel_flash/README_initrd_flash.txt and note for Orin (Workflow 4)
            # sudo ./tools/kernel_flash/l4t_initrd_flash.sh --external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_external.xml -p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml --no-systemimg" --network usb0      <board> external
            self.internal_flash_options = f'-p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml --no-systemimg"'
        # TODO test flashing XAVIER NX with emmc and nvme separately - maybe this part is not necessary!!!
        #elif self.config['device'] == "xavier_nx":
        #    self.internal_flash_options = f'-p "-c bootloader/t186ref/cfg/flash_t194_uefi_qspi_p3668.xml"'

        if self.config['device'] == 'xavier_nx':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3668-0001-qspi-emmc"
        elif self.config['device'] == 'orin_nx':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3767-0000"
        elif self.config['device'] == 'orin_nx_8gb':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3767-0001"
        elif self.config['device'] == 'orin_nano_8gb':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3767-0003"
        elif self.config['device'] == 'orin_nano_4gb':
            self.board_name = 'airvolute-dcs' + self.config['board'] + "+p3767-0004"
            #self.board_system_vars="ADDITIONAL_DTB_OVERLAY_OPT=BootOrderNvme.dtbo SKIP_EEPROM_CHECK=1 BOARDSKU=0004 BOARDID=3767 FAB=300 BOARDREV=H.0 CHIPID=0x23 CHIP_SKU=00:00:00:D6"
        else:
            print("Unknown device! [%s] exitting" % self.config['device'])
            exit(8)
        
        self.functionOnverlays.add_special_var({"BOARD_CONFIG_NAME":self.board_name})

        if self.config['storage'] == 'emmc':
            self.rootdev = "mmcblk0p1"
            self.external_device = ""
        elif self.config['storage'] == 'nvme':
            self.rootdev = "external"
            self.external_device = "--external-device nvme0n1p1 "
            self.prepare_status.set_last_step() # prepare phase
            fn_overlay_options = self.exec_fn_overlay("get-img-type")
            print(f"Fn Overlay get-img-type returned:{fn_overlay_options}")
            if "rfsenc" in fn_overlay_options:
                print("Found rfsenc config in fn. overlay - get-img-type")
                self.rfs_enc = True
            self.ext_partition_layout = self.get_ext_partition_layout_file(self.args.ab_partition, self.rfs_enc, self.args.nvme_disk_size)
            print(f"Selected ext_partition_layout: {self.ext_partition_layout}")

        if self.args.ab_partition == True:
            self.env_vars += " ROOTFS_AB=1"
            if self.args.rootfs_type == "minimal":
                opt_app_size = 4
            else:
                opt_app_size = 8
            self.opt_app_size_arg = f"-S {opt_app_size}GiB"
            #self.rootdev = "external" # set UUID device in kernel commandline: rootfs=PARTUUID=<external-uuid>

        if self.args.app_size is not None:
            self.opt_app_size_arg = f"-S {self.args.app_size}GiB"
        else:
            print("Unknown storage [%s]! exitting" % self.config['storage'])
            exit(9)
        # fix default rootdev to external  (or internal) for orin. There is NFS used to flash
        if self.config['device'] in ['orin_nx', 'orin_nx_8gb', 'orin_nano_8gb', 'orin_nano_4gb']:
            self.rootdev = "external" #specify "internal" - boot from  on-board device (eMMC/SDCARD), "external" - boot from external device. For more see flash.sh examples

    def group_regeneration_needed(self, group = None):
        # check commandline parameter if they are same as previous and images are already generated skip generation
        if self.prepare_status.is_identifier_same_as_prev(["--regen", "--force"]) and self.prepare_status.get_status(group) == True:
            print(f"Generation in group {self.prepare_status.get_group(group)} is ready!")
            return 0
        return 1

    def request_recovery_mode(self,message:str=""):
        print("Please put device into recovery mode")
        self.prepare_status.set_processing_step("check-device-rcm-mode")
        rcm_mode = is_jetson_orin_or_xavier_in_rcm(print_msg=True)
        if rcm_mode == False:
            ret = wait_with_check(10, is_jetson_orin_or_xavier_in_rcm, valid_ret_val=[int(True)])
            if ret == 0:
                self.prepare_status.set_status(int(rcm_mode), valid_retval=[1])
                return
            print( message + " Please put device into recovery mode and start script again!")
            self.prepare_status.set_status(int(rcm_mode), valid_retval=[1], last_step= True)
            exit(1)
        self.prepare_status.set_status(int(rcm_mode), valid_retval=[1])

    def call_fn_overlay_img_gen_interal_prepare(self):
        # for rfs enc, eks image should be prepared before generating images
        ret = self.exec_fn_overlay("img-gen-internal-prepare")

        if ret != None and ret != 0:
            print(f"ERROR! - Fn Overlay img-gen-internal-prepare returned:{ret}")
            exit(ret)
            # call cleanup if necessary for function overlay
        ret = self.exec_fn_overlay("img-gen-cleanup")
        if ret != None:
            print(f"Fn Overlay img-gen-cleanup returned:{ret}")

    def generate_images(self):
        self.prepare_status.change_group("images-phase-0" if self.rfs_enc else "gen-images")
        print("-"*80)
        print("Generating images! ...")
        ret = -2

        # Note: --no-flash parameter allows us to only generate images which will be used for flashing new devices
        # flash internal emmc"
        if self.config['storage'] == 'emmc':
            if self.group_regeneration_needed() == 0:
                print("Images already generated in group! Skipping generating images!")
                return 0
            self.prepare_status.set_processing_step("generate_images-emmc")
            ret = cmd_exec(f"sudo ./{self.flash_script_path} --no-flash --showlogs {self.board_name} {self.rootdev}")
            self.prepare_status.set_status(ret, last_step = True)
            return ret
        # flash external nvme drive
        if self.rfs_enc == False and self.group_regeneration_needed() == 0:
            print("Images for internal storage already generated in group! Skipping generating images!")
            return 0
    
        #file to check: initrdflashparam.txt - contains last enterred parameters
        self.env_vars += f" {self.board_system_vars}"
        
        #external_only = True # flash only external device
        #self.gen_external_only = False

            
        append=""
        if not self.gen_external_only:
            append = "--append"
            if self.group_regeneration_needed():
                print("Generating internal device images! ...")
                print("-"*80)
                # get command specific options from funct overlay img-gen-internal-prepare
                self.call_fn_overlay_img_gen_interal_prepare()
            
                # get command specific options for l4t_initrd_flash from funct overlay img-gen-internal
                overlay_params = self.exec_fn_overlay("img-gen-internal")
                print(f"Fn Overlay img-gen-internal parameters:{overlay_params}")

                self.prepare_status.set_processing_step("generate_images-internal")
                #./${flash_script_path} -u ./rsa.pem -v ./sbk.key $uefi_keys_opt --no-flash --network usb0 -p "-c bootloader/t186ref/cfg/flash_t234_qspi.xml" --showlogs ${board_config_name} internal
                ret = cmd_exec(f"sudo {self.env_vars} {overlay_params['env']} ./{self.flash_script_path} --no-flash {self.flashing_network} {overlay_params['args']} {self.internal_flash_options} --showlogs {self.board_name} internal", print_command=True)
                print(f"cmd_exec returned:{ret}")
                self.prepare_status.set_status(ret)
                
                if self.rfs_enc == True:
                    # this is last step in case we are creating encrypted image (img-gen-internal-prepare exist)
                    self.prepare_status.set_last_step()
                # ret = cmd_exec("sudo cp bootloader/eks_t234_sigheader.img.encrypt ./tools/kernel_flash/images/internal/")
                # call cleanup if necessary for function overlay
                overlay_flash_cleanup_ret = self.exec_fn_overlay("img-gen-cleanup")
                if overlay_flash_cleanup_ret != None:
                    print(f"Fn Overlay img-gen-cleanup returned:{overlay_flash_cleanup_ret}")
                if ret != 0:
                    print(f"Error occured while generating image!({ret}) Exitting!")
                    exit(1)           
            
        print("-"*80)
        print("Going to generate external device images! ...")

        if self.rfs_enc == True:
            # create new generation phase - for rootfs enc  - device must be connected while generating RFS image  (ECID number is necessary for generation)
            self.prepare_status.change_group("images-phase-1")
            
            
            self.request_recovery_mode("RFS enc mode needs regenerate image!")
        # in non secure image generation, images can be generated once and no regeneration is needed
        elif self.group_regeneration_needed() == 0:
            print("Images for external storage already generated in group! Skipping generating images!")
            return 0

        # get command specific options from funct overlay img-gen-external
        overlay_params = self.exec_fn_overlay("img-gen-external")
        print(f"Fn Overlay img-gen-internal parameters:{overlay_params}")

        self.prepare_status.set_processing_step("generate_images-external")
        #sudo ROOTFS_ENC=1 ./${flash_script_path} -u ${OUT_dir}/rsa.pem -v ${OUT_dir}/sbk.key  -i ${OUT_dir}/sym2_t234.key -S ${partition_size} --no-flash --network usb0 --showlogs
        #  --external-device ${nvme_device} -c ./tools/kernel_flash/flash_l4t_t234_nvme_rootfs_enc.xml --external-only --append  ${board_config_name} external
        ret = cmd_exec(f"sudo {self.env_vars} {overlay_params['env']} ./{self.flash_script_path} {self.opt_app_size_arg} --no-flash {self.flashing_network} {overlay_params['args']} --showlogs " + 
                        f"{self.external_device} -c {self.ext_partition_layout} --external-only {append} {self.board_name} {self.rootdev}", print_command=True)
        print(f"cmd_exec returned:{ret}")
        self.prepare_status.set_status(ret, last_step = True if self.rfs_enc == False else False)
        
        if self.rfs_enc:
            self.prepare_status.set_last_step()
        # call cleanup if necessary for function overlay
        overlay_flash_cleanup_ret = self.exec_fn_overlay("img-gen-cleanup")
        if overlay_flash_cleanup_ret != None:
            print(f"Fn Overlay img-gen-cleanup returned:{overlay_flash_cleanup_ret}")
        print("*"*80)
        if ret != 0:
            print(f"Error occured while generating image!({ret}) Exitting!")
            exit(1)
        return ret
    
    def exec_fn_overlay(self, fn_name, overlay_name=None):
        try:
            ret = self.functionOnverlays.exec_function(fn_name, overlay_name)
        except Exception as e:
            print(f"Calling overlay was not successfull: {e}")
            print("Exitting!")
            exit(2)
        return ret

    def flash_gen_prepare_odmfuse(self):
        if self.functionOnverlays.is_registred("odmfuse") == False:
            return 0
        # used for eg. odmfuse
        self.prepare_status.change_group("flash-gen-prepare-odmfuse")
        # pre - flash ops eg. odmfuse

        self.request_recovery_mode()
        
        # odmfuse-test if needed
        self.prepare_status.set_last_step()
        ret = self.exec_fn_overlay("flash-gen-prepare-is-needed", "odmfuse")
        if ret != None and ret >= 1:
            # fuse device with odmfuse
            print("[INFO] Device is not fused!")
            print("#"*35 + "!! WARNING !!" + "#"*35)
            print("Going to fuse Jetson device!!")
            print("!! DO NOT REMOVE POWER WHILE FUSING DEVICE !!")
            exit(0)
            self.prepare_status.set_last_step()
            ret = self.exec_fn_overlay("flash-gen-prepare", "odmfuse")
            if ret == 0:
                print("#"*35 + "!! FUSING DONE () !!" + "#"*35)
            else:
                print("#"*35 + f"!! FUSING WAS NOT SUCESSFULL ({ret}) !!" + "#"*35)
                exit(1)

    def flash(self):
        # setup flashing
        self.setup_initrd_flashing()
        self.flash_gen_prepare_odmfuse()
        # generate images
        ret = self.generate_images()
        if ret != 0:
            print("Generating images was not sucessfull! ret = %d" % (ret))
            print("Exitting!")
            exit(7)
        # flash device
        print("-"*80)
        print("Flash images! ...")
        self.prepare_status.change_group("flash")
        self.prepare_status.set_processing_step("flash_only")

        # Run sudo identification if not enterred
        cmd_exec("/usr/bin/sudo /usr/bin/id > /dev/null")
        ret = cmd_exec(f"sudo {self.flash_script_path} --flash-only {self.external_device} {self.flashing_network} {self.board_name} {self.rootdev}", print_command=True)
        self.prepare_status.set_status(ret, last_step= True)

    def airvolute_flash(self):
        if self.match_selected_config() == None:
            print('Unsupported configuration!')
            return
        print("matched configuration: " + self.selected_config_name)

        self.download_resources()
        self.prepare_sources_production()
        #return #now just return
        self.flash()
        quit() 

    def run(self):
        if self.args.command == 'list':
            if self.args.local_overlays == True:
                self.get_local_overlays("directory")
                quit()
            self.list_all_versions()
            quit()

        if self.args.command == 'flash':
            self.airvolute_flash()
            quit()


if __name__ == "__main__":
    dcs_deploy = DcsDeploy()
    dcs_deploy.run()
