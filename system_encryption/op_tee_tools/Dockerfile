# Use an official Python image as the base
FROM python:3.12-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the script and dependencies into the container
COPY gen_ekb.py /app/
COPY requirements.txt /app/

# Install required Python packages
RUN pip install --no-cache-dir -r requirements.txt

# Set the default command to run the script
ENTRYPOINT ["/usr/local/bin/python3", "gen_ekb.py", "-chip", "t234", "-oem_k1_key", "oem_k1.key", "-fv", "fv_ekb_t234", "-in_sym_key", "sym_t234.key", "-in_sym_key2", "sym2_t234.key", "-out", "eks_t234.img"]