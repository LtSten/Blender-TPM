import bpy
from io_mesh_tpm import tpm_utils
from pathlib import Path


# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator


class EXPORT_OT_tpm(Operator, ExportHelper):
	"""Export meshes and materials to a TPM"""
	bl_idname = "export_mesh.tpm"  # important since its how bpy.ops.import_test.some_data is constructed
	bl_label = "Export TPM"

	# ExportHelper mixin class uses this
	filename_ext = ".tpm"

	filter_glob: StringProperty(
		default="*.tpm",
		options={'HIDDEN'},
		maxlen=255,  # Max internal buffer length, longer would be clamped.
	)
	
	opacityFaceExportMode: EnumProperty(
		items=[
			("FORWARD_ONLY", "Forward Only", "Export only forward-facing sides of alpha geometry"),
			("DOUBLE_SIDED", "Double Sided", "Export alpha geometry as double sided"),
			("RESPECT_BACKFACE_CULLING", "Use Material Backface Culling", "Uses the face material's backface culling setting to determine whether to export forward only (if ticked) or double sided (if unticked)")
		],
		default="FORWARD_ONLY",
		name="Opacity Face Export",
		description="Determine how to export faces with opacity map material assigned"
	)
	
	def execute(self, context):
		f = open(self.filepath, 'w', encoding='utf-8')
		
		try:
			tpm_utils.Export(context.selected_objects, f, self.opacityFaceExportMode)
		except tpm_utils.TPMException as e:
			self.report({'ERROR'}, str(e))
			return {'CANCELLED'}
		
		f.close()
		return {'FINISHED'}
		

# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
	self.layout.operator(EXPORT_OT_tpm.bl_idname, text="Trespasser Model (.tpm)")


def register():
	bpy.utils.register_class(EXPORT_OT_tpm)
	bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
	bpy.utils.unregister_class(EXPORT_OT_tpm)
	bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)