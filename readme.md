`dcs-deploy` packages serves as a tool for flashing Nvidia Jetson family devices supporting airvolute hardware. It is developed for Python 3 only.

# Dependencies
**! DISLAIMER - INSTALL THOSE INSIDE HOST PC !**

**! THIS IS BETA VERSION FOR JP 6.2 SOME ADDITIONAL CONSIDERATIONS MAY APPLY PLEASE REVIEW SECTION KNOWN LIMITATIONS BEFORE USING JP 6.2 [here](#known-limitation---jetpack-62---beta)!**

### APT

```  
sudo apt install qemu-user-static sshpass abootimg lbzip2 jq coreutils findutils
```    
### Python
```
pip install wget  
```

# Basic usage
1. **Put Jetson into force recovery mode**
    - Short FC pin with ground on DCS boards (See [Control](https://docs.airvolute.com/autopilots/dcs2/.pilot-boards/dcs2.pilot-v-1.0/connectors-and-pinouts#control) section for your specific board. This example is for DCS 2.0 pilot board.)
    - You can check if the device is really in force recovery mode with `lsusb` command. There should be Nvidia entry in the query.
    - Next, connect the device to the host pc using [dev micro usb connector](https://docs.airvolute.com/autopilots/dcs2/.pilot-boards/dcs2.pilot-v-1.0/connectors-and-pinouts#top-side-onboard-connectors) - again example for DCS 2.0 board.

2. **cd into dcs-deploy repo**
    ```
    cd /path/to/dcs-deploy
    ```

3. **Run dcs_deploy.py**
For example:
    JetPack 5.1.2, ORIN NX, NVME, Airvolute DCS 2.0 board (with default expander), full rootfs from Nvidia:
    ```
    python3 dcs_deploy.py flash orin_nx 512 2.0 default nvme full
    ```
    
    JetPack 6.2, ORIN NX, NVME, Airvolute DCS 2.0 board (with default expander), full rootfs from Nvidia:
    ```
    python3 dcs_deploy.py flash orin_nx 62 2.0 default nvme full
    ```

    Note: Please refer to the section Known limitations - JetPack 6.2 - beta [here](#known-limitation---jetpack-62---beta)

    You can list supported configs with:
    ```
    python3 dcs_deploy.py list
    ```
4. **After a successful flash, the Jetson will boot and can be logged in using SSH with default credentials:**
    - login: `dcs_user`
    - password: `dronecore`

If you shut the Jetson down after flash and then boot it again, make sure you remove cable/jumper that enables Force recovery mode.

# Flashing the device again with existing config
If you run the script with `flash` flag, it will re-initialize the Linux for Tegra folder each time. If you just want to re-use the folder and flash the same config to multiple devices, use nvidia flashing script:
 
1. **Change directory to to `kernel_flash` dir**

    ```
    cd ~/.dcs_deploy/flash/<config_name>/Linux_for_tegra/tools/kernel_flash
    ```

2. **Launch `l4t_initrd_flash.sh` script with appropriate parameters**
    ```
    # nvme
    sudo ./l4t_initrd_flash.sh --flash-only --external-only --external-device nvme0n1p1 -c flash_l4t_external_custom.xml --showlogs airvolute-dcs1.2+p3668-0001-qspi-emmc nvme0n1p1
    # emmc
    sudo ./l4t_initrd_flash.sh --flash-only airvolute-dcs1.2+p3668-0001-qspi-emmc mmcblk0p1
    ```

# Features
## Custom root filesystem
You can use your own root filesystem (rootfs) by providing path to it using `--rootfs` flag. The script will use it as is, without any modifications. Using custom rootfs is useful if you want to create backup of your system or you just don't want to install all the software you typically use on the device each time after flashing.

### Preparing your own rootfs image
Please run following commands **on the Jetson device**:
```
$ mkdir ~/rootfs_merged
$ cd rootfs_merged
$ sudo tar jxpf ../linux-sample-root-filesystem-r3521aarch64tbz2_original
$ cd ~
$ sudo rsync -axHAWX --numeric-ids --info=progress2 --exclude={"/dev/","/proc/","/sys/","/tmp/","/run/","/mnt/","/media/*","/lost+found","/home/dcs_user/rootfs_merged","/home/dcs_user/.ssh"} / rootfs_merged
$ sudo tar -cf rootfs_merged.tar -C rootfs_merged .
$ pbzip2 -k rootfs_merged.tar # output rootfs_merged.tar.bz2
```

- `linux-sample-root-filesystem-r3521aarch64tbz2_original` is the root filesystem provided by Nvidia. You can find this on Nvidia website or it is downloaded with dcs-deploy tool. Find it in `download` dir (see [Filesystem](#filesystem) section). So, you need to download this file and place it in the home directory of the Jetson.
- `rootfs_merged` is the directory, where the root filesystem will be merged.
- `pbzip2` is the compression tool, which is used to compress the tarball. You might need to install it using:
```
sudo apt install pbzip2
```

Then you can copy `rootfs_merged.tar.bz2` to your host pc and use point to it with `--rootfs` flag.

- Warning - we advise using `--app_size` parameter when using custom rootfs. If you do not set it adequately, `APP` partition may be too small for your custom rootfs. `app_size` should be bigger than your custom rootfs.

## Flashing to specific UUID, multiple nvme drives
If you want to use multiple nvme drives, this is not an issue. Just make sure **you plug out secondary NVME during flashing process.** After the flashing is successful, you can plug in the secondary NVME. The device will then always boot from the primary NVME (the one that was plugged in during the flashing process).

## Effectiveness
Keep in mind, that we tried to make this tool as much effective as possible. So, following rules apply:
- When flashing process is ran with the same parameters, the script will not re-generate the images and will not extract downloaded resources again. This is generally ok, but keep in mind that if you alter any files in flash config folder, these changes won't transfer into the next flashing process. If you want to alter anything in the rootfs, you need to alter these files in the rootfs archive and then save it under different name in your PC.
- When any of the steps fail, the script exits and saves the progress. On next run, the script tries to re-run the failed step and continue the whole process from there.
- When you use different rootfs paths each time, the whole flash config folder is re-initialized. That means extracting downloaded resources and generating flash images from scratch. This adds up some time to the process, but it does not break anything.

## Purging SSH keys
If you accidentally (or intentionally) left public keys in the rootfs, those are automatically purged. Otherwise each device you flash would be accessible from your host PC which we find harmful. If you feel you want to do this, please find it inside `dcs-deploy.py` file and comment it out.

## Basic first boot settings
There were some issues specific to our platform and to the Jetsons in general, so we decided to fix them after the flashing or to be more specific - after the first boot. The `resources/dcs_first_boot.service` file is a service that is run at only at the first boot. It runs never again. The service runs `resources/dcs_first_boot.sh` script on the Jetson device and does following:
- Regenerates SSH keys.
- Sets up fan speed to maximum at all times.
- Sets up basic permissions and UDEV rules so it is in line with Linux standards.
- Sets up USB hubs.

# Principles
### Basics
The `dcs-deploy.py` script can be used instead of Nvidia SDK manager regarding Airvolute hardware. The main advantages are that this package is lightweight and can be used across different Linux distros or Ubuntu versions (SDK manager is strictly tied between Ubuntu and JetPack version). The script does 3 steps in general:
1. Download Nvidia and custom Airvolute files.
2. Prepare filesystem, which is ready for flashing.
3. Flash the device supporting Airvolute boards.
`dcs-deploy` package leverages many of Nvidia provided scripts.

### Filesystem
Preparing the filesystem is crucial for successful device flashing, despite the carrier board manufacturer. The script prepares/extracts:
1. `Linux For Tegra` folder provided by Nvidia.
2. `Airvolute overlay`, which satisfies carrier board support (HW) for Jetson devices, that are supported at the moment.
3. `Airvolute root filesystem`, which is in fact used as a subfolder inside `Linux For Tegra` folder. At this time, this is just a barebones minimal clean filesystem generated by Nvidia tools. We expect to populate this filesystem with custom Airvolute software in the near future.

As a root of this filesystem, `.dcs_deploy` folder is created inside **host pc HOME** directory. The structure of the folder:
```
.dcs_deploy/
├─ download/
│  ├─ <source webpage hostname>/<path to resource without "download/downloads">
│  ├─ .../
├─ flash/
│  ├─ config_1/
│  ├─ config_2/
│  ├─ .../
├─ downloaded_versions.json

```

- `config` is the name of the downloaded/extracted configuration consisting of device type, flashing memory type, airvolute carrier board version and jetpack version. Example `xavier_nx_emmc_1.2_51`.
- `downloaded_versions.json` consists of configs, that are already downloaded, so if the script is re-ran, those file are not downloaded again and again.
- `download` contains downloaded archives needed for flashing
- `flash` contains extracted folders that are needed for flashing. Those are folders from `download` dir + some nvidia and airvolute scripts applied, so the flashing environment is fully ready.

### Local overlays
To add features easily to the device without need of the creation of a new rootfs it is possible to utilize local overlays. These overlays are processed during the run of the `dcs_deploy`. 

The local overlays are stored in the `local/overlays` directory. Each overlay is a either a directory or a file containing the following structure:
```
# Directory
overlay_name/
├─ resources/
├─ apply_overlay_name.sh 

# File
overlay_name.sh
```

The logic of the overlay is stored in the `apply_overlay_name.sh` file or a `overlay_name.sh` for script overlay. This file is executed during the run of the `dcs_deploy` script. Usually, the overlay modify the rootfs that will be flashed in some way, but the logic can be anything that is needed. Each overlay is called with the same arguments as the `dcs_deploy` script. 

Overlay can be added to the flashing configuration by adding the overlay name to the `local_overlays` list in the `config_db.json` file. The order of the overlays in the list is the order in which the overlays are applied.

The `local_overlays` example:
```
 "local_overlays": ["dcs_first_boot", "hardware_support_layer", "save_version.sh"]
```

Third party overlays can be created and can be added to the `local/overlays` directory and added to the `config_db.json`. This is the easiest way to add new features to the device without the need to create a new rootfs. This is especially useful for the development of new features or for the testing of new features.

##### Arguments
The overlays are called with the same positional arguments as the `dcs_deploy` script. Additionally, user can pass custom named arguments to the local overlay. To pass the custom arguments you need to adhere to this syntax and update the `config_db.json` file like this:

```     
"local_overlays": [{"custom_arguments_showcase.sh": {"custom_arg1": "value1", "custom_arg2": "value2"}},  "dcs_first_boot", "hardware_support_layer", "save_version.sh"],
```

To try this out you can add ` [{"custom_arguments_showcase.sh": {"custom_arg1": "value1", "custom_arg2": "value2"}}` to the `local_overlays` list in the `config_db.json` file to some configuration. The `custom_arguments_showcase.sh` will print out all the arguments passed to it in local overlay install phase.



#### Local overlays by Airvolute
- `dcs_first_boot` - sets some basic settings on the device, regenerate SSH keys, enable services from `hardware_support_layer`. This service is run only once, at the first boot of the device.
- `hardware_support_layer` - a set of services, udevs and other tools that are run at the first boot of the device. These services are responsible for setting up the hardware to work properly with the Airvolute DroneCore boards. All the software and configuration files installed by this layer can be reviewed in the logs folder on the device (`/home/dcs_user/Airvolute/logs/dcs-deploy/dcs_deploy_data.json`).
- `save_version.sh` - saves the version of the flashed configuration to the `/home/dcs_user/Airvolute/logs/dcs-deploy/dcs_deploy_version.json` file. This file is used to store the information about the flashed configuration. This information can be used to check the version of the flashed configuration on the device.

### Hardware Supporting Layer (systemctls, udev rules and more)
This layer consist of two local overlays `dcs_first_boot` and `hardware_support_layer`. `hardware_support_layer` is a set of services, udevs and other tools that are run at the first boot of the device. 


#### Some important services from `hardware_support_layer`:

- `ethernet_switch_control`, `usb_hub_control`, and `usb3_control` are additional services that activate or reinitialize some hardware modules to ensure stable functionality during power cycles. By default, users do not need to modify these services in any way.
- `boost_clocks_and_fan` is another extra service that boosts clocks and activates the fan to 100%. If this behavior is undesired, it can be disabled with the command `sudo systemctl disable fan_control`.
- On DCS 1.0 and 1.2, `ethernet_switch_control` will reset the USB hub. This is not an issue, but if undesired, it can be disabled similarly to fan_control.

### Cube (Autopilot) Connection
- Currently, the connection to the Cube is not set up by default.
- We recommend using the tool `mavlink-router` - https://github.com/mavlink-router/mavlink-router.
  - When using `mavlink-router`, you can specify a connection to the Cube and then define endpoints to which the router should route Mavlink messages (your GCS IP and port).
  - This configuration is defined in the `main.conf` file (default location at `/etc/mavlink-router/main.conf`).
  - Example content of the `main.conf` file to enable GCS forwarding:

```
[General]
DebugLogLevel = info
TcpServerPort = 0
# Leave to TCP if using SITL
# Main connection to AutoPilot
[UartEndpoint cube]
Device = /dev/ttyTHS0
Baud = 921600

# Note that this is for communication through dev micro USB. 
# if you want to use any other interface, change address accordingly. 
[UdpEndpoint GCS]
Mode = Normal
Address = 192.168.55.100
Port = 14550
``` 

### Known limitations
- When the script is re-ran, flash config folder is deleted and the files are extracted again.
- The database of configs is held inside this repository, which is not ideal.
- Download folder is not checked, only `downloaded_versions.json` file is, so if the download folder has been altered script will throw an error.
- Errors that might occur during deployment process are not handled very well at the moment. 

### Troubleshooting
#### 1. Verifying 1st boot configuration
To verify, that the full deployment is sucesfull and that the first boot configuration is done you can run these commands on target:

During 1st boot (right after the flashing is completed):
```
$ journalctl -u dcs_first_boot
```
Expected outcome (at the end, you can also check each command's output):
```
dcs systemd[1]: dcs_first_boot.service: Succeeded.
```

After 1st boot.
```
sudo uhubctl
```
Expected outcome:
`List of usb hub port with port 6 disabled.`

**If the output is not as expected, please reboot the device and run after 1st boot command. If the issue with usbhub is persistent please reflash the device.**

#### 2. Device is not booting
- Check if the correct hardware revision of DCS was selected.
- If the device is not booting from NVME, please try to reflash the device using EMMC internal memory and flash again NVME configuration. (only Xavier NX)


#### 3. Flashing issues
On new host kernels, USB flashing problems can happen eg.: `ERROR: might be timeout in USB write.` see listing 1). New kernels have enabled USB autosuspend functionality which causes flashing errors. Use following commands to stop usb autosuspend:
```
$ sudo su
# echo -1 > /sys/module/usbcore/parameters/autosuspend
```

- Listing 1)
```
1)

 Entering RCM boot

[   0.0378 ] mb1_t234_prod_aligned_sigheader.bin.encrypt filename is from --mb1_bin
[   0.0378 ] psc_bl1_t234_prod_aligned_sigheader.bin.encrypt filename is from --psc_bl1_bin
[   0.0378 ] rcm boot with presigned binaries
[   0.0384 ] tegrarcm_v2 --instance 6-2.4 --new_session --chip 0x23 0 --uid --download bct_br br_bct_BR.bct --download mb1 mb1_t234_prod_aligned_sigheader.bin.encrypt --download psc_bl1 psc_bl1_t234_prod_aligned_sigheader.bin.encrypt --download bct_mb1 mb1_bct_MB1_sigheader.bct.encrypt
[   0.0389 ] BR_CID: 0x80012344705DD190400000000F0201C0
[   0.1299 ] Sending bct_br
[   0.1454 ] ERROR: might be timeout in USB write.
```

### Known limitation - JetPack 6.2 - beta
Airvolute BSP for JetPack 6.2 is currently in beta. The flashing process is not fully tested and some features may not work as expected. Please report any issues to Airvolute support or open issues. Regardless of this beta release can be used to asses the new features of JetPack 6.2 and prepare their applications for the new JetPack version.

User can always downgrade to stable JetPack 5.1.2 version by flashing the device with appropriate configuration. Beware the downgrading takes just under 60 minutes.
#### Downgrade procedure from JP 6.2 to JP 5.1.2
At the moment it is not possible to downgrade direcrly from JP 6.2 to JP 5.1.2, because all the UEFI, QSPI and rootfs must be compatible and there seems to be some leftovers from JP 6.2 flash.

The procedure to sucesfully downgrade is as follows:
1. Start flash with JP 5.1.2 configuration.
2. Wait for the flash to finish. You don't have to connect device to the host PC, we just need to create the flashing environment with images.
3. Locate the `Linux_for_tegra` folder in the path `~/.dcs_deploy/flash/<config_name>/Linux_for_tegra`. (for example $HOME/.dcs_deploy/flash/orin_nx_nvme_2.0_default_512_full/Linux_for_Tegra)
4. Run the following commands for Orin NX (Orin NX should be in recovery mode and power cycle is assumed between commands) and DCS 2.0:
```
1. Wait until finished.
sudo ./flash.sh -c bootloader/t186ref/cfg/flash_t234_qspi.xml airvolute-dcs2.0+p3767-0000 internal

or 

sudo ./flash.sh -c bootloader/t186ref/cfg/flash_t234_qspi.xml airvolute-dcs1.2+p3767-0000 internal


2. Wait until finished (even error is ok).
sudo ./tools/kernel_flash/l4t_initrd_flash.sh --erase-all --external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_external.xml --showlogs --network usb0 airvolute-dcs2.0+p3767-0000 nvme0n1p1

or 

sudo ./tools/kernel_flash/l4t_initrd_flash.sh --erase-all --external-device nvme0n1p1 -c tools/kernel_flash/flash_l4t_external.xml --showlogs --network usb0 airvolute-dcs1.2+p3767-0000 nvme0n1p1
```
1. After the 2nd flash is finished, you might need to reflash the device with the JP 5.1.2 configuration one more time using standard `dcs-deploy` command. If were using the same configuration to downgrade to JP 5.1.2, you need to use `--regen` flag to be sure, that the images are the ones from the configuration. After this flash you can use the device and `dcs-deploy` as usual.

#### CSI interface
The following cameras are currently supported:
- IMX219 (CSI0)
- IMX477 (CSI0)
- OV9281 (CSI0)
- OV64B40 Airvolute Hadron Expander (CSI2/3)
- TC358743 HDMI capture chip (CSI2/3)

To use any of these cameras, you must apply the corresponding Device Tree Overlay by running `sudo python /opt/nvidia/jetson-io/jetson-io.py`.

In the menu, navigate to: **Configure Airvolute DCS2 Adapter Board → Configure for Compatible Hardware**

From the list, select the camera you wish to use.

Confirm your selection and reboot for the changes to take effect.

#### I2C & SPI devices
##### TC74 Temperature sensor
On both DCS1.2 and DCS2.0 boards is a temperature sensor connected on I2C-1 bus. It's temperature can be read from this path `/sys/class/hwmon/hwmon0/temp1_input` the value is in millicelsius [m°C] (returned value of 47000 = 47°C).


##### BMI088 IMU (Accelerometer & Gyroscope)

The DCS2.0 board includes a BMI088 IMU, which combines a 3-axis accelerometer and a 3-axis gyroscope.
These sensors can be accessed via the Industrial I/O (IIO) subsystem under the following paths:

- Accelerometer: `/sys/bus/iio/devices/iio:device0`
- Gyroscope: `/sys/bus/iio/devices/iio:device1`

The max sampling rate are:
- Accelerometer: up to 1600 Hz
- Gyroscope: up to 2000 Hz

#### Known issues:

- Super modes are currently not supported out of the box. The main limitation for Orin NX and DCS 2.0 or DCS 1.2 lies in the power board adapter not able to consitently provide the power needed which may result in overheating and shutting down the device.
  - If you want to use super modes, please contact Airvolute support for more information.

The new revision of the power board together with adapter board for DCS 2.0 is scheduled by the end of Q2 2025. 
