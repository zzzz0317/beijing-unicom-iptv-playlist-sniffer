import hashlib

def calculate_file_hash(file_path):
    sha512_hash = hashlib.sha512()
    with open(file_path, "rb") as file:
        for chunk in iter(lambda: file.read(4096), b""):
            sha512_hash.update(chunk)
    return sha512_hash.hexdigest()