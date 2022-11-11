#	Copyright (C) 2022 Matt Rowe
#
#	This program is free software: you can redistribute it and/or modify
#	it under the terms of the GNU General Public License as published by
#	the Free Software Foundation, either version 3 of the License, or
#	(at your option) any later version.
#
#	This program is distributed in the hope that it will be useful,
#	but WITHOUT ANY WARRANTY; without even the implied warranty of
#	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#	GNU General Public License for more details.
#
#	You should have received a copy of the GNU General Public License
#	along with this program.  If not, see <https://www.gnu.org/licenses/>.

bl_info = {
	"name": "Trespasser Model Import/Export",
	"author": "Matt Rowe",
	"version": (0, 4, 2),
	"blender": (3, 0, 0),
	"location": "File > Import/Export > Trespasser Model",
	"warning": "Still a somewhat early implementation - open to feedback and bugs.",
	"description": "Support for importing and exporting models and materials to and from TPM files",
	"warning": "",
	"doc_url": "https://www.trescomforum.org/viewtopic.php?f=58&t=11689",
	"category": "Import-Export",
}

shouldUnregister = False

if "bpy" in locals():
	from importlib import reload
	if "tpm_import" in locals():
		tpm_import = reload(tpm_import)
	else:
		from io_mesh_tpm import tpm_import
	
	if "tpm_export" in locals():
		tpm_export = reload(tpm_export)
	else:
		from io_mesh_tpm import tpm_export
	
	if "tpm_utils" in locals():
		tpm_utils = reload(tpm_utils)
	
	shouldUnregister = True
else:
	from io_mesh_tpm import tpm_import
	from io_mesh_tpm import tpm_export

import bpy

def register():
	tpm_import.register()
	tpm_export.register()

def unregister():
	tpm_export.unregister()
	tpm_import.unregister()

if __name__ == "__main__":
	if shouldUnregister:
		unregister()
	register()
	#bpy.ops.import_mesh.tpm('INVOKE_DEFAULT')
	#bpy.ops.export_mesh.tpm('INVOKE_DEFAULT')