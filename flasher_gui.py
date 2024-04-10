import tkinter as tk
from tkinter import ttk
from tkinter import filedialog
from tkinter import messagebox
from tkinter import scrolledtext
import json
import subprocess
import os
import threading
import signal
import sys
import time


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('DCS Deploy Configurator')
        self.geometry('415x265')  # Adjusted geometry to fit new options
        self.process = None
        # Load configurations from JSON file
        self.configurations = self.load_configurations('local/config_db.json')
        # Extract options for dropdowns
        self.extract_options()

        # Define the labels and input fields
        self.create_widgets()

    def load_configurations(self, filepath):
        with open(filepath, 'r') as file:
            configurations = json.load(file)
        return configurations

    def extract_options(self):
        self.devices = set()
        self.storages = set()
        self.boards = set()
        self.versions = set()
        self.rootfs_types = set()

        for config in self.configurations.values():
            self.devices.add(config['device'])
            if isinstance(config['storage'], list):
                self.storages.update(config['storage'])
            else:
                self.storages.add(config['storage'])
            if isinstance(config['board'], list):
                self.boards.update(config['board'])
            else:
                self.boards.add(config['board'])
            self.versions.add(config['l4t_version'])
            self.rootfs_types.add(config['rootfs_type'])

        self.device_options = sorted(list(self.devices))
        self.storage_options = sorted(list(self.storages))
        self.board_options = sorted(list(self.boards), key=lambda x: float(x) if x.replace('.', '', 1).isdigit() else x)

        numeric_versions = {v for v in self.versions if v.replace('.', '', 1).isdigit()}
        non_numeric_versions = self.versions - numeric_versions

        self.version_options = sorted(numeric_versions, key=float) + sorted(non_numeric_versions)
        self.rootfs_type_options = sorted(list(self.rootfs_types))


    def create_widgets(self):
        tk.Label(self, text="Device:").grid(row=0, column=0, sticky='w')
        self.device_var = tk.StringVar()
        self.device_dropdown = ttk.Combobox(self, textvariable=self.device_var, values=self.device_options, state="readonly")
        self.device_dropdown.grid(row=0, column=1)
        self.device_dropdown.bind('<<ComboboxSelected>>', self.update_options_based_on_device)

        self.create_dynamic_dropdown("Storage", 1)
        self.create_dynamic_dropdown("Board", 2)
        self.create_dynamic_dropdown("L4T Version", 3)
        self.create_dynamic_dropdown("Rootfs Type", 4)

        # App Size
        tk.Label(self, text="App Size:").grid(row=5, column=0, sticky='w')
        self.app_size_entry = tk.Entry(self)
        self.app_size_entry.grid(row=5, column=1)

        # Rootfs
        tk.Label(self, text="Rootfs:").grid(row=6, column=0, sticky='w')
        self.rootfs_entry = tk.Entry(self)
        self.rootfs_entry.grid(row=6, column=1)
        self.browse_button = tk.Button(self, text="Browse", command=self.browse_file)
        self.browse_button.grid(row=6, column=2)

        # Batch Counter
        self.batch_counter_var = tk.BooleanVar()
        self.batch_counter_check = tk.Checkbutton(self, text="Set Batch Counter", variable=self.batch_counter_var, command=self.toggle_batch_counter)
        self.batch_counter_check.grid(row=7, column=0, sticky='w')
        self.batch_counter_combo = ttk.Combobox(self, values=[i for i in range(1, 255)], state='disabled')
        self.batch_counter_combo.grid(row=7, column=1)

        # Setup Doodle Radio
        tk.Label(self, text="Setup Doodle Radio IP:").grid(row=8, column=0, sticky='w')
        self.setup_doodle_radio_entry = tk.Entry(self)
        self.setup_doodle_radio_entry.grid(row=8, column=1)

        self.deploy_button = tk.Button(self, text="Deploy", command=self.deploy)
        self.deploy_button.grid(row=9, column=1)

        # Status Box (Read-Only Text Box)
        self.status_var = tk.StringVar()  # Variable to hold the status message text
        self.status_box = tk.Entry(self, textvariable=self.status_var, state='readonly', width=50)
        self.status_box.grid(row=10, column=0, columnspan=3, sticky='ew', padx=5, pady=5)

    def create_dynamic_dropdown(self, label, row):
        tk.Label(self, text=f"{label}:").grid(row=row, column=0, sticky='w')
        var = tk.StringVar()
        setattr(self, f"{label.lower().replace(' ', '_')}_var", var)
        dropdown = ttk.Combobox(self, textvariable=var, state="readonly")
        dropdown.grid(row=row, column=1)
        setattr(self, f"{label.lower().replace(' ', '_')}_dropdown", dropdown)

    def toggle_batch_counter(self):
        if self.batch_counter_var.get():
            self.batch_counter_combo['state'] = 'readonly'
        else:
            self.batch_counter_combo.set('')
            self.batch_counter_combo['state'] = 'disabled'

    def update_options_based_on_device(self, event):
        selected_device = self.device_var.get()
        filtered_configs = [config for config in self.configurations.values() if config['device'] == selected_device]

        self.update_dropdown_options('storage', filtered_configs)
        self.update_dropdown_options('board', filtered_configs)
        self.update_dropdown_options('l4t_version', filtered_configs)
        self.update_dropdown_options('rootfs_type', filtered_configs)

    def update_dropdown_options(self, attribute, configs):
        options = set()
        for config in configs:
            if isinstance(config[attribute], list):
                options.update(config[attribute])
            else:
                options.add(config[attribute])

        # Separate numeric and non-numeric options for sorting
        numeric_options = {opt for opt in options if str(opt).replace('.', '', 1).isdigit()}
        non_numeric_options = options - numeric_options

        sorted_options = sorted(numeric_options, key=lambda x: float(x)) + sorted(non_numeric_options)

        dropdown = getattr(self, f"{attribute}_dropdown")
        dropdown['values'] = sorted_options
        dropdown.set('')


    def browse_file(self):
        file_path = filedialog.askopenfilename()
        self.rootfs_entry.delete(0, tk.END)
        self.rootfs_entry.insert(0, file_path)

    def update_status(self, message):
        """Utility function to update the status box."""
        self.status_var.set(message)  # Update the text variable associated with the status box

    def deploy(self):
        self.update_status("Started deploying...")
        device = self.device_var.get()
        storage = self.storage_var.get()
        board = self.board_var.get()
        l4t_version = self.l4t_version_var.get()
        rootfs_type = self.rootfs_type_var.get()
        app_size = self.app_size_entry.get()
        rootfs = self.rootfs_entry.get()
        batch_counter = self.batch_counter_combo.get() if self.batch_counter_var.get() else ""
        setup_doodle_radio = self.setup_doodle_radio_entry.get()

        # Construct the command
        command = f"python3 dcs_deploy.py flash {device} {l4t_version} {board} {storage} {rootfs_type}"

        # Append optional arguments if provided
        if app_size:
            command += f" --app_size {app_size}"
        if rootfs:
            command += f" --rootfs {rootfs}"
        if batch_counter:
            command += f" --batch_counter {batch_counter}"
        if setup_doodle_radio:
            command += f" --setup_doodle_radio {setup_doodle_radio}"

        command += f"; echo 'Press enter to exit'; read"
        print(f"Executing: {command}")

        # Execute the command
        self.deployment_thread = threading.Thread(target=self.execute_command, args=(command,), daemon=True)
        self.deployment_thread.start()

        config_identifier = f"{device}_{storage}_{board}_{l4t_version}_{rootfs_type}"
        threading.Thread(target=self.check_flash_status, args=(config_identifier,), daemon=True).start()

    def execute_command(self, command, callback=None):
        """Execute a command allowing interaction with the terminal and call callback if provided."""
        try:
            process = subprocess.Popen(['gnome-terminal', '--', 'bash', '-c', command])
            process.wait()
        except Exception as e:
            print(f"Error executing command: {e}")

    def check_flash_status(self, config_identifier):
        """Check the status of the flash process."""
        home_dir = os.path.expanduser('~')
        with open(os.path.join(home_dir, '.dcs_deploy/flash', config_identifier, 'prepare_status.json'), 'r') as file:
            data = json.load(file)
            while True:
                if data['flash']['status']:
                    self.update_status("Deployment successful!")
                    break
                time.sleep(1)


if __name__ == "__main__":
    app = App()
    app.mainloop()
