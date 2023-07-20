
  

# Dependencies
## APT

```  
sudo apt install qemu-user-static sshpass abootimg lbzip2  
```    
## Python
```
pip install gitpython
```

```
pip install wget  
```

# Basic usage
- **Put Xavier NX into force recovery mode**

- **cd into dcs-deploy repo**
```
cd /path/to/dcs-deploy
```
- **run dcs_deploy.py**:
```
python3 dcs_deploy.py flash xavier_nx 51 1.2 nvme
```
or
```
python3 dcs_deploy.py flash xavier_nx 51 1.2 emmc
```

# Flashing the device again with existing config
If you run the script with `flash` flag, it will re-initialize the Linux for Tegra folder each time. If you just want to re-use the folder and flash the same config to multiple devices, use nvidia flashing script:
 
1. Change directory to to `kernel_flash` dir

```
cd ~/.dcs_deploy/flash/<config_name>/Linux_for_tegra/tools/kernel_flash
```

2. Launch `l4t_initrd_flash.sh` script with appropriate parameters
```
# nvme
sudo ./l4t_initrd_flash.sh --flash-only --external-only --external-device nvme0n1p1 -c flash_l4t_external_custom.xml --showlogs airvolute-dcs1.2+p3668-0001-qspi-emmc nvme0n1p1
# emmc
sudo ./l4t_initrd_flash.sh --flash-only airvolute-dcs1.2+p3668-0001-qspi-emmc mmcblk0p1
```
