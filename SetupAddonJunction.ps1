# n.b. can't use a relative path when creating a junction, so form the absolute path manually
$JunctionLocation = "$(Get-Location)\addons\io_mesh_tpm"
New-Item -ItemType Junction -Path $JunctionLocation -Target .\io_mesh_tpm