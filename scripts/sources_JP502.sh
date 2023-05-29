#!/bin/bash

#---SETUP PATHS---
set -e

echo -e "\e[7mSetting exports...\e[0m"

export REV_FOLDER='suite_rev5'
export DEVICE_FOLDER='JetPack_5.0.2_Linux_JETSON_XAVIER_NX_TARGETS' 
export JETPACK=$HOME/nvidia/nvidia_sdk/$DEVICE_FOLDER/Linux_for_Tegra
export TEGRA_KERNEL_OUT=$JETPACK/sources/kernel_out
export CROSS_COMPILE_AARCH64_PATH=$HOME/l4t-gcc
export CROSS_COMPILE_AARCH64=$HOME/l4t-gcc/bin/aarch64-buildroot-linux-gnu-
export CROSS_COMPILE=$HOME/l4t-gcc/bin/aarch64-buildroot-linux-gnu-
export INSTALL_MOD_STRIP=--strip-debug

echo -e "\e[7mRunning build...\e[0m"

if [ -d "$TEGRA_KERNEL_OUT" ]; then
    echo "$TEGRA_KERNEL_OUT exists."
    ./nvbuild.sh -o $PWD/kernel_out
else 
   mkdir $TEGRA_KERNEL_OUT
  ./nvbuild.sh -o $PWD/kernel_out
fi

echo -e  "\e[7mCopying dnvgpu.ko\e[0m "
cd
cd $JETPACK/rootfs/usr/lib/modules/5.10.104-tegra/kernel/drivers/gpu/nvgpu
if [ -f "nvgpu.ko" ]; then
    sudo rm nvgpu.ko
fi
sudo cp $TEGRA_KERNEL_OUT/drivers/gpu/nvgpu/nvgpu.ko $JETPACK/rootfs/usr/lib/modules/5.10.104-tegra/kernel/drivers/gpu/nvgpu
cd

cd 
echo -e  "\e[7mCopy extconf...\e[0m "
echo ""
cd 
cd $JETPACK/bootloader
if [ -f "extlinux.conf" ]; then
     rm extlinux.conf
fi
cp $JETPACK/sources/resources/extlinux.conf $JETPACK/bootloader/extlinux.conf
cd


#copy compiled files to working dir
echo -e  "\e[7mCopying dtb files and kernel image from kernel output to Linux_for_tegra directory  ...\e[0m "
cd
cd $JETPACK/kernel 
if [ -f "Image" ]; then
    rm Image
fi

if [ -d "dtb" ]; then
    rm -r dtb
fi

mkdir -p dtb
cd
sudo cp $TEGRA_KERNEL_OUT/arch/arm64/boot/Image nvidia/nvidia_sdk/$DEVICE_FOLDER/Linux_for_Tegra/kernel
sudo cp -a $TEGRA_KERNEL_OUT/arch/arm64/boot/dts/nvidia/. nvidia/nvidia_sdk/$DEVICE_FOLDER/Linux_for_Tegra/kernel/dtb/

echo -e  "\e[7mIf ANY OTHER NECESSARY FILES NEEDS TO BE COPIED (driver modules etc.), COPY THEM NOW ! .. then press a key ..\e[0m "
  while [ true ] ; do
  read -t 3 -n 1
  if [ $? = 0 ] ; then
  break;
  fi
done

#go back to kernel sources
cd $JETPACK

if [ -d "images" ]; then
    rm -r images
else
    mkdir images
fi

cd $JETPACK/sources/kernel/kernel-5.10

echo -e  "\e[7mInstalling modules ...\e[0m "
echo ""
#sudo make ARCH=arm64 O=$TEGRA_KERNEL_OUT modules_install CROSS_COMPILE=$CROSS_COMPILE INSTALL_MOD_PATH=$JETPACK/rootfs
make ARCH=arm64 O=$TEGRA_KERNEL_OUT modules_install CROSS_COMPILE=$CROSS_COMPILE INSTALL_MOD_PATH=$JETPACK/images
cd $JETPACK/images

tar --owner root --group root -cjf kernel_supplements.tbz2 lib/modules
mv kernel_supplements.tbz2 $JETPACK/kernel/

cd

echo -e  "\e[7mCopy pinmuxes...\e[0m "
echo ""
cd $JETPACK/bootloader/t186ref/BCT/

rm tegra19x-mb1-pinmux-p3668-a01.cfg
rm tegra19x-mb1-padvoltage-p3668-a01.cfg

cd
cp $JETPACK/sources/resources/$REV_FOLDER/tegra19x-mb1-pinmux-p3668-a01.cfg $JETPACK/bootloader/t186ref/BCT
cp $JETPACK/sources/resources/$REV_FOLDER/tegra19x-mb1-padvoltage-p3668-a01.cfg $JETPACK/bootloader/t186ref/BCT
cd 


echo -e  "\e[7mAplying binaries ...\e[0m "
echo ""
cd $JETPACK
sudo ./apply_binaries.sh -t False
echo -e  "\e[7mDONE\e[0m "

exit 0
done
