import tegrity
import os

# .dcs_deploy/flash/xavier_nx_emmc_1.2_51/Linux_for_Tegra/rootfs
rootfs_extract_dir = os.path.join(
       '/home',
       'edo', 
        '.dcs_deploy',
        'flash',
        'xavier_nx_emmc_1.2_51',
        'Linux_for_Tegra',
        'rootfs'
    )

print(rootfs_extract_dir)

with tegrity.qemu.QemuRunner(rootfs_extract_dir) as runner:
        # runner.run_cmd(
        #     ('export', 'USER=dcs_user'), userspec="dcs_user:dcs_user"
        # )

        # runner.run_cmd(
        #     ('export', 'HOME=/home/dcs_user'), userspec="dcs_user:dcs_user"
        # )

        runner.run_cmd(
            ('ls'), userspec="dcs_user:dcs_user"
        )

        # runner.run_cmd(
        #     (
        #         'python',
        #         '/home/dcs_user/ae_install.py',
        #         'install',
        #         'suite'
        #         '--dry-run'
        #     ),
        #     userspec="dcs_user:dcs_user"
        # )
