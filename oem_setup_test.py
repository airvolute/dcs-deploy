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


rootfs_extract_dir = os.path.join('/home/edo/.dcs_deploy/flash/xavier_nx_nvme_1.2_51/Linux_for_Tegra/rootfs')
print(rootfs_extract_dir)
dev_type_file = os.path.join(rootfs_extract_dir, 'etc', 'dcs_dev_type')
device_type = 't194'

# subprocess.call(
#     [
#         'sudo',
#         'touch',
#         dev_type_file
#     ]
# )
# # sudo sh -c 'echo "t194" >> /home/edo/.dcs_deploy/flash/xavier_nx_nvme_1.2_51/Linux_for_Tegra/rootfs/etc/dcs_dev_type'
# subprocess.call("""sudo sh -c 'echo """ + '"' + device_type + '"' + ' >> ' + dev_type_file + "'")


subprocess.call(
    [
        'sudo',
        'ln',
        '-s',
        '/etc/systemd/system/dcs_first_boot.service',
        '/home/edo/.dcs_deploy/flash/xavier_nx_nvme_1.2_51/Linux_for_Tegra/rootfs/etc/systemd/system/multi-user.target.wants/dcs_first_boot.service'
    ]
)