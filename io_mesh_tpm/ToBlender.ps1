$BlenderVer = "3.3"
$BlenderDir = "D:\Program Files\Blender Foundation\Blender $BlenderVer\$BlenderVer"
$OutputDir = "$BlenderDir\scripts\addons\io_mesh_tpm"
Write-Output "Copying files to '$OutputDir'"

# Won't create the directory if it doesn't exist (want to fail loudly rather than silently)
Copy-Item -Path "*.py" -Destination "$OutputDir"