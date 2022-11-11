import bpy
from io_mesh_tpm import tpm_utils
from pathlib import Path


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class IMPORT_OT_tpm(Operator, ImportHelper):
	"""Import meshes and materials from a TPM"""
	bl_idname = "import_mesh.tpm"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Import TPM"

	# ImportHelper mixin class uses this
	filename_ext = ".tpm"

	filter_glob: StringProperty(
		default="*.tpm",
		options={'HIDDEN'},
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	
	importToActiveCollection : BoolProperty(
		default=False,
		name="Import to Active Collection"
	)
	
	texturePathOverride : StringProperty(
		name = "Texture path override",
		description="Choose a path to look for textures in when loading materials. If this is blank, it defaults to the directory of the selected TPM.",
		subtype='DIR_PATH'
	)
	
	stripDirectoriesFromTextureNames : BoolProperty(
		default=True,
		name="Ignore texture directories",
		description="If enabled, any parent directories preceding the filename in TPM textures will be ignored"
	)
	
	overwriteExistingMaterials : BoolProperty(
		default=False,
		name="Overwrite existing materials",
		description="If enabled, any materials required by the TPM will be recreated rather than reused"
	)
	
	def execute(self, context):
		f = open(self.filepath, 'r', encoding='utf-8')
		data = f.read()
		f.close()

		textureSearchPath = self.texturePathOverride
		if not textureSearchPath:
			textureSearchPath = str(Path(self.filepath).parent)

		try:
			tpm_utils.Import(self, data, textureSearchPath, self.stripDirectoriesFromTextureNames, self.overwriteExistingMaterials, context.collection if self.importToActiveCollection else None)
		except tpm_utils.TPMException as e:
			self.report({'ERROR'}, str(e))
			return {'CANCELLED'}
		
		return {'FINISHED'}
		

# Only needed if you want to add into a dynamic menu
def menu_func_import(self, context):
	self.layout.operator(IMPORT_OT_tpm.bl_idname, text="Trespasser Model (.tpm)")


def register():
	bpy.utils.register_class(IMPORT_OT_tpm)
	bpy.types.TOPBAR_MT_file_import.append(menu_func_import)


def unregister():
	bpy.utils.unregister_class(IMPORT_OT_tpm)
	bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)