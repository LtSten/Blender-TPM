$BlenderVer = "3.6"
$BlenderDir = "$env:APPDATA\Blender Foundation\Blender\$BlenderVer"
$OutputDir = "$BlenderDir\scripts\addons\io_mesh_tpm"
Write-Output "Copying files to '$OutputDir'"

# Won't create the directory if it doesn't exist (want to fail loudly rather than silently)
Copy-Item -Path ".\io_mesh_tpm\*.py" -Destination "$OutputDir"