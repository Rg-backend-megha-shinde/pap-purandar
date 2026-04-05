import os
from django import template

register = template.Library()


@register.filter
def display_filename(file_path):
    """
    Extract and display just the filename from a full file path.
    Example: 'documents/2024/file.pdf' -> 'file.pdf'
    """
    if not file_path:
        return ''
    return os.path.basename(str(file_path))


@register.filter
def safe_file_size(file_field):
    """
    Safely get file size, returns 0 if file doesn't exist.
    Prevents FileNotFoundError when file is missing from disk.
    """
    try:
        if file_field and hasattr(file_field, 'size'):
            # Check if file actually exists before accessing size
            if hasattr(file_field, 'path') and file_field.path:
                if os.path.exists(file_field.path):
                    return file_field.size
        return 0
    except (OSError, ValueError, AttributeError):
        return 0
