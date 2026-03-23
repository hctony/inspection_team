from PyInstaller.utils.hooks import collect_data_files, collect_submodules

# Include all UI submodules
hiddenimports = collect_submodules("dmtsnapsync.ui")

# Include package data (assets)
datas = collect_data_files("dmtsnapsync", includes=["assets/*"])
