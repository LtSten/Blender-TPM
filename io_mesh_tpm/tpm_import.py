import bpy
import bmesh
from bpy_extras.image_utils import load_image
from . import tpm_utils
from .tpm_types import *
from pathlib import Path
import mathutils

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# ----------------------------------------------------------------
def FindTextureOnDisk(textureSearchPath: str, stripDirectoriesFromTextureNames: bool, textureName: str, WarningCallback) -> str:
	if stripDirectoriesFromTextureNames:
		textureName = Path(textureName).name
	filename = Path(textureSearchPath).joinpath(textureName)
	if not filename.is_file():
		# Allow a texture to not exist on disk - we can still create the material.
		WarningCallback(f"Failed to find texture '{textureName}' in path '{textureSearchPath}'. Final lookup was '{str(filename)}'.")
		return None
	return str(filename)

# ----------------------------------------------------------------
def CreateImageNodeFromTPMTexMap(mat: bpy.types.Material, mapName: str, filepath: str) -> bpy.types.ShaderNodeTexImage:
	imageNode = mat.node_tree.nodes.new("ShaderNodeTexImage")
	imageNode.image = bpy.data.images.get(mapName)
	if not imageNode.image:
		imageNode.image = load_image(filepath if filepath else "", "", place_holder=True)
		imageNode.image.name = mapName
	return imageNode

# ----------------------------------------------------------------
def Import(operator: bpy.types.Operator, tpmData: str, textureSearchPath: str, stripDirectoriesFromTextureNames: bool, overwriteExistingMaterials: bool, toCollection: bpy.types.Collection):
	print("Beginning import")
	# Process the TPM
	WarningCallback = lambda msg: operator.report({'WARNING'}, msg)
	tpm = TPMRawToTPM(StringToTPMRaw(tpmData), WarningCallback)
	
	# Add each material
	blenderMaterialsByName: dict[str, bpy.types.Material] = {}
	for material in tpm.materials:
		mat = bpy.data.materials.get(material.name)
		createNewMaterial = mat is None
		recreateMaterialNodes = createNewMaterial or overwriteExistingMaterials
		
		if createNewMaterial:
			mat = bpy.data.materials.new(material.name)
			mat.use_nodes = True
			
		if recreateMaterialNodes:
			nodes = mat.node_tree.nodes
			for node in nodes:
				nodes.remove(node)
			
			materialOutputNode = nodes.new("ShaderNodeOutputMaterial")
			bsdfNode = mat.node_tree.nodes.new("ShaderNodeBsdfPrincipled")
			bsdfNode.inputs["Roughness"].default_value = 0.9
			bsdfNode.inputs["Specular"].default_value = 0.0
			mat.node_tree.links.new(bsdfNode.outputs[0], materialOutputNode.inputs[0])
			
			if material.colourmap:
				imageNode = CreateImageNodeFromTPMTexMap(mat, material.colourmap, FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, material.colourmap, WarningCallback))
				if not Path(imageNode.image.filepath).is_file():
					WarningCallback(f'Failed to load colour texture {material.colourmap}')
				imageNode.name = "Colour Map"
				mat.node_tree.links.new(imageNode.outputs[0], bsdfNode.inputs["Base Color"])
			
			if material.bumpmap:
				# Bump node between image and normal input
				bumpNode = nodes.new("ShaderNodeBump")
				bumpNode.name = "Bump"
				mat.node_tree.links.new(bumpNode.outputs[0], bsdfNode.inputs["Normal"])
				
				# Image node
				imageNode = CreateImageNodeFromTPMTexMap(mat, material.bumpmap, FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, material.bumpmap, WarningCallback))
				if not Path(imageNode.image.filepath).is_file():
					WarningCallback(f'Failed to load bumpmap texture {material.bumpmap}')
				imageNode.name = "Bump Map"
				mat.node_tree.links.new(imageNode.outputs[0], bumpNode.inputs[2])
				
			
			if material.opacitymap:
				imageNode = CreateImageNodeFromTPMTexMap(mat, material.opacitymap, FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, material.opacitymap, WarningCallback))
				if not Path(imageNode.image.filepath).is_file():
					WarningCallback(f'Failed to load opacity texture {material.opacitymap}')
				imageNode.name = "Opacity Map"
				mat.node_tree.links.new(imageNode.outputs[0], bsdfNode.inputs["Alpha"])
				mat.blend_method = 'CLIP'
			
			# Constants since dimensions don't seem to update immediately
			bsdfNodeWidth = 240.0
			bsdfNodeHeight = 591.0
			imageNodeWidth = 240.0
			imageNodeHeight = 251.0
			bumpNodeWidth = 140.0
			bumpNodeHeight = 168.0
			
			bsdfNode.location = [0.0, 0.0]
			materialOutputNode.location = [bsdfNodeWidth * 1.2, 0.0]
			
			offsetXFrom = bsdfNode.location[0]
			if material.bumpmap:
				bumpMapNode = nodes["Bump Map"]
				bumpNode = nodes["Bump"]
				bumpNode.location[1] = -(imageNodeHeight * 1.1 * 2 + (imageNodeHeight - bumpNodeHeight) * 0.5)
				bumpNode.location[0] = offsetXFrom - bumpNodeWidth * 1.5
				offsetXFrom = bumpNode.location[0]
				
			if material.colourmap:
				n = nodes["Colour Map"]
				n.location = [offsetXFrom - imageNodeWidth * 1.5, 0]
			
			if material.opacitymap:
				n = nodes["Opacity Map"]
				n.location = [offsetXFrom - imageNodeWidth * 1.5, -1 * 1.1 * imageNodeHeight]
			
			if material.bumpmap:
				n = nodes["Bump Map"]
				n.location = [offsetXFrom - imageNodeWidth * 1.5, -2 * 1.1 * imageNodeHeight]
		
		blenderMaterialsByName[material.name] = mat
	
	# Get or create the collection to add to
	collection = toCollection
	if collection is None:
		collection = bpy.data.collections.new(tpm.fileInfo.name or "TPM_Import")
		bpy.context.scene.collection.children.link(collection)

	# Add each mesh
	blenderMeshesByName: dict[str, bpy.types.Mesh] = {}
	tpmBonesByName: dict[str, TPM.Bone] = {b.name : b for b in tpm.bones}
	armatureObjectsByTPMMeshName: dict[str, bpy.types.Object] = {}
	for tpmMesh in tpm.meshes:
		mesh = bpy.data.meshes.new(tpmMesh.name)
		bm = bmesh.new()
		
		# Add each vertex
		for vertex in tpmMesh.vertices:
			bm.verts.new(vertex)
		bm.verts.ensure_lookup_table()
		bm.verts.index_update()
		
		# Add each face - note that TPM indices are 1-based
		blenderFaceToTPMFaceIndexMap = {}
		tpmFaceIndex = 0
		blenderFaceIndex = 0
		for face in tpmMesh.faces:
			tpmFaceIndex += 1 # 1-based, increment regardless of success
			try:
				blenderFace = bm.faces.new([bm.verts[i-1] for i in face.vertexIndices])
				blenderFaceToTPMFaceIndexMap[blenderFaceIndex] = tpmFaceIndex
				blenderFaceIndex += 1
			except ValueError:
				# Duplicate face, Blender doesn't like this. Pretend it doesn't exist.
				pass
			
		# Each "loop" is a vertex in a face.
		# Add texture coordinates and normals to each vertex, and a material to each face
		uvLayer = bm.loops.layers.uv.new()
		for faceIndex, face in enumerate(bm.faces):
			tpmFaceIndex = blenderFaceToTPMFaceIndexMap[faceIndex]
			tpmFace = tpmMesh.faces[tpmFaceIndex - 1] # Choose to be consistent by counting TPM faces from 1
			tpmNormalIndices = tpmFace.normalIndices
			tpmTexCoordIndices = tpmFace.texCoordIndices
			for faceLocalVertIndex, loop in enumerate(face.loops):
				loop[uvLayer].uv = tpmMesh.textureCoords[tpmTexCoordIndices[faceLocalVertIndex] - 1]
				loop.vert.normal = tpmMesh.normals[tpmNormalIndices[faceLocalVertIndex] - 1]
			face.material_index = tpmFace.materialIndex - 1
		
		# Add and populate an armature for this mesh
		if isinstance(tpmMesh, TPM.Skin):
			# Make sure there is no selection
			bpy.ops.object.select_all(action="DESELECT")
			bpy.ops.object.armature_add(enter_editmode=True)
			meshArmatureObject = bpy.context.object
			meshArmatureObject.name = f"Armature_{tpmMesh.name}"
			meshArmatureData: bpy.types.Armature = meshArmatureObject.data
			meshArmatureData.name = meshArmatureObject.name
			# Remove any existing bones
			for bone in meshArmatureData.edit_bones:
				meshArmatureData.edit_bones.remove(bone)
			# Add new bones
			for boneIndex in set(tpmMesh.vertexBoneIndices):
				# Following TresEd, Trespasser itself, and the 3ds Max import/export script, we allow 0 to be a valid bone index
				# The TPM spec says otherwise, but clearly this has never been the case in practice
				boneName =  ConstructJointName(tpmMesh.name, boneIndex)
				# Try to find the corresponding bone in the TPM
				tpmBone = tpmBonesByName.get(boneName)
				if tpmBone is not None:
					bone = meshArmatureData.edit_bones.new(boneName)
					bone.use_deform = True
					# Assume we're using a convention where bones are oriented along the Z axis by default
					alignAxis: Vector = Vector((0, 0, 1))
					alignAxis.rotate(mathutils.Euler(ToRadians(tpmBone.rotation), 'ZYX')) # Blender XYZ order means X at the bottom of the hierarchy
					# align_roll doesn't seem to work, so just set it up manually
					bone.head = Vector(alignAxis * 0.1)
					bone.tail = -bone.head
					bone.translate(tpmBone.position)
				else:
					WarningCallback(f"Skin '{tpmMesh.name}' contains a reference to a bone with index {boneIndex}, but no matching bone '{boneName}' exists")
			# Leave edit mode
			bpy.ops.object.mode_set(mode="OBJECT")
			bpy.ops.object.select_all(action="DESELECT") # Don't keep the armature selected
			# Keep track of this armature
			armatureObjectsByTPMMeshName[tpmMesh.name] = meshArmatureObject
			for c in meshArmatureObject.users_collection:
				c.objects.unlink(meshArmatureObject)
			collection.objects.link(meshArmatureObject)
		# Populate the mesh
		bm.to_mesh(mesh)
		mesh.update()
		
		# Assign the materials to the mesh
		# Ensure this is done in-order so that the indices are as expected
		if len(mesh.materials) != 0:
			raise TPMException("Expected mesh materials to be empty")
		for materialName in tpmMesh.materialNames:
			mesh.materials.append(blenderMaterialsByName[materialName])

		print(f"Successfully imported {'skin' if isinstance(tpmMesh, TPM.Skin) else 'mesh'} '{tpmMesh.name}'")
		blenderMeshesByName[tpmMesh.name] = mesh

	# Get or create the collection to add to
	collection = toCollection
	if collection is None:
		collection = bpy.data.collections.new(tpm.fileInfo.name or "TPM_Import")
		bpy.context.scene.collection.children.link(collection)
	
	# Add each instance as an object in the collection
	for tpmInstance in tpm.instances:
		meshName = tpmInstance.mesh
		if meshName not in blenderMeshesByName:
			WarningCallback(f"Instance '{tpmInstance.name}' references mesh '{meshName}', but this was not loaded.")
			continue
		blenderMesh = blenderMeshesByName[meshName]
		object = bpy.data.objects.new(tpmInstance.name, blenderMesh)
		
		object.location = tpmInstance.position
		for i, v in enumerate(object.scale):
			object.scale[i] = tpmInstance.scale
		object.rotation_euler = ToRadians(Vector(tpmInstance.rotation))
		
		# Configure skin-specific properties
		if isinstance(tpmMesh, TPM.Skin):
			# Collect all the vertex indices assigned to each bone
			vertexIndicesByBoneID: dict[int, list[int]] = {}
			for vertexIndex, boneIndex in enumerate(tpmMesh.vertexBoneIndices):
				vertexIndicesByBoneID.setdefault(boneIndex, []).append(vertexIndex)
			# Create a vertex group for each bone and add the corresponding vertices
			for boneIndex, vertexIndices in vertexIndicesByBoneID.items():
				vertexGroup: bpy.types.VertexGroup = object.vertex_groups.new(name=ConstructJointName(tpmMesh.name, boneIndex))
				vertexGroup.add(vertexIndices, 1.0, 'REPLACE')
			# Add an armature modifier to this instance for the corresponding mesh
			armatureObject = armatureObjectsByTPMMeshName.get(tpmMesh.name)
			if armatureObject is not None:
				modifier: bpy.types.ArmatureModifier = object.modifiers.new("Skin", "ARMATURE")
				modifier.object = armatureObject
		collection.objects.link(object)
	print("Import finished")

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
			Import(self, data, textureSearchPath, self.stripDirectoriesFromTextureNames, self.overwriteExistingMaterials, context.collection if self.importToActiveCollection else None)
		except TPMException as e:
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