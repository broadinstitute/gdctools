import shutil
import os

from ..meta import tcga_id, diced_file_path, diced_file_path_partial
from ..common import safeMakeDirs
# Copy from mirror to dice dir

def process(file_dict, mirror_path, dice_path):
    _tcga_id = tcga_id(file_dict)
    filepath = diced_file_path(dice_path, file_dict)
    filepath_partial = diced_file_path_partial(dice_path, file_dict)
    safeMakeDirs(dice_path)

    # copy to new name in
    shutil.copy(mirror_path, filepath_partial)
    os.rename(filepath_partial, filepath)
