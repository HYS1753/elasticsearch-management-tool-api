def format_bytes(size_in_bytes: int) -> str:
    GB = 1024 ** 3
    MB = 1024 ** 2

    if size_in_bytes >= GB:
        value = size_in_bytes / GB
        return f"{value:.2f} GB"
    else:
        value = size_in_bytes / MB
        return f"{value:.2f} MB"