#	Copyright (C) 2023 Matt Rowe
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
	"name": "Trespasser Model Import/Export (.tpm)",
	"author": "Matt Rowe",
	"version": (1, 0, 0),
	"blender": (4, 0, 0),
	"location": "File > Import/Export > Trespasser Model",
	"description": "Support for importing and exporting models and materials to and from TPM files",
	"doc_url": "https://www.trescomforum.org/viewtopic.php?f=58&t=11689",
	"tracker_url": "https://www.trescomforum.org/viewtopic.php?f=58&t=11689",
	"category": "Import-Export",
}

import bpy

tpmPackages = ["tpm_import", "tpm_export", "tpm_utils", "tpm_types"]
register, unregister = bpy.utils.register_submodule_factory(__name__, tpmPackages)

if __name__ == "__main__":
	register()