import bpy
import bmesh
from . import tpm_utils
from .tpm_types import *
from pathlib import Path
from datetime import datetime
from dataclasses import dataclass

# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

# ----------------------------------------------------------------
def Export(operator: bpy.types.Operator, objects: list[bpy.types.Object], file, opacityFaceExportMode):
	print("Beginning export")
	vertexGroupBoneRegex = re.compile(r"\D(\d{2})$")

	# Find the set of meshes we need to export
	blenderMeshes: set[bpy.types.Mesh] = set()
	for object in objects:
		if isinstance(object.data, bpy.types.Mesh):
			blenderMeshes.add(object.data)
	
	# Find the set of materials we need to export
	blenderMaterials: set[bpy.types.Material] = set()
	for mesh in blenderMeshes:
		for material in mesh.materials:
			blenderMaterials.add(material)
	
	# Create TPM lists (and file info)
	tpmFileInfo = TPM.FileInfo(formatVersion="1.0.1", name=Path(file.name).name, source=bpy.path.basename(bpy.context.blend_data.filepath), date=datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"), version=None, comments=None)
	tpmInstances: list[TPM.Instance] = []
	tpmMaterials: list[TPM.Material] = []
	tpmMeshes: list[TPM.Mesh] = []
	tpmBones: list[TPM.Bone] = []
	
	# Populate TPM lists:
	# Materials - do these first so we can query alpha properties of faces during mesh construction
	for mat in blenderMaterials:
		# mat.node_tree.active_output is always -1. Useful.
		materialOutput: bpy.types.ShaderNodeOutputMaterial = None
		for node in mat.node_tree.nodes:
			if isinstance(node, bpy.types.ShaderNodeOutputMaterial):
				materialOutput = node
				break
		if materialOutput is None:
			raise TPMException(f"Could not find a material output node for material '{mat.name}'")
		
		bsdfTypeNode: bpy.types.Node = materialOutput.inputs["Surface"].links[0].from_node
		
		# See if it has a "Color" link
		tpmColourMap: str = None
		colourInput: bpy.types.NodeSocket = bsdfTypeNode.inputs.get("Color")
		if not colourInput:
			colourInput = bsdfTypeNode.inputs.get("Base Color")
		if colourInput and len(colourInput.links) > 0:
			colourImageNode = colourInput.links[0].from_node
			if isinstance(colourImageNode, bpy.types.ShaderNodeTexImage) and colourImageNode.image:
				tpmColourMap = colourImageNode.image.name
		
		# See if it has a "Normal" link
		tpmBumpMap: str = None
		normalInput: bpy.types.NodeSocket = bsdfTypeNode.inputs.get("Normal")
		if normalInput and len(normalInput.links) > 0:
			bumpNode: bpy.types.Node = normalInput.links[0].from_node
			if bumpNode.bl_idname == "ShaderNodeBump":
				bumpHeightInput = bumpNode.inputs.get("Height")
				if bumpHeightInput and len(bumpHeightInput.links) > 0:
					bumpImageNode = bumpHeightInput.links[0].from_node
					if isinstance(bumpImageNode, bpy.types.ShaderNodeTexImage) and bumpImageNode.image:
						tpmBumpMap = bumpImageNode.image.name
		
		# See if it has an "Alpha" link
		tpmOpacityMap: str = None
		alphaInput: bpy.types.NodeSocket = bsdfTypeNode.inputs.get("Alpha")
		if alphaInput and len(alphaInput.links) > 0:
			alphaImageNode: bpy.types.Node = alphaInput.links[0].from_node
			if isinstance(alphaImageNode, bpy.types.ShaderNodeTexImage) and alphaImageNode.image:
				tpmOpacityMap = alphaImageNode.image.name
		
		# Remove any path-like elements of the map names
		if tpmColourMap:
			tpmColourMap = Path(tpmColourMap).name
		if tpmBumpMap:
			tpmBumpMap = Path(tpmBumpMap).name
		if tpmOpacityMap:
			tpmOpacityMap = Path(tpmOpacityMap).name
		
		# Append the material
		tpmMaterials.append(TPM.Material(mat.name, tpmColourMap, tpmBumpMap, tpmOpacityMap))
	tpmMaterials.sort(key=lambda m: m.name)
	tpmMaterialsByName = {mat.name : mat for mat in tpmMaterials}
	
	# Check instances of each mesh to determine if we should write a skin
	@dataclass
	class SkinData:
		instanceObject: bpy.types.Object
		armatureObject: bpy.types.Object

	skinDataByMeshName: dict[str, SkinData] = {}
	for object in objects:
		# Mesh object
		if not isinstance(object.data, bpy.types.Mesh):
			continue
		# Fetch all armatures referenced by armature modifiers
		armatureObjects: list[bpy.types.Object] = [m.object for m in object.modifiers if isinstance(m, bpy.types.ArmatureModifier) and m.object and isinstance(m.object.data, bpy.types.Armature)]
		if len(armatureObjects) != 1:
			operator.report({'WARNING'}, f"Object '{object.name}' has multiple armature objects assigned via armature modifiers - only the first will be used to define a skin")
		armatureObject = armatureObjects[0]
		# If it already exists, warn if this is a different armature object for this mesh
		meshName = object.data.name
		if meshName in skinDataByMeshName:
			existingObject, existingArmatureObject = skinDataByMeshName.get(meshName)
			if armatureObject != existingArmatureObject:
				operator.report({'WARNING'}, f"Mesh '{meshName}' has instances '{object.name}' and '{existingObject.name}', but with differing armature modifier objects ('{armatureObject.name}' and '{existingArmatureObject.name}' respectively")
		else:
			skinDataByMeshName[meshName] = SkinData(object, armatureObject)
	# Meshes
	bmeshMeshes: list[bmesh.types.BMesh] = [] # (vectors in) bmeshes must persist until we've written the TPM
	for mesh in blenderMeshes:
		tpmMeshName = mesh.name
		tpmMaterialNames: list[str] = []
		tpmVertices: list[Vector] = []
		tpmVertexBoneIndices: list[Vector] = []
		tpmTexCoords: list[Vector] = []
		tpmNormals: list[Vector] = []
		tpmFaces: list[TPM.Mesh.Face] = []
		# Materials
		for material in mesh.materials:
			tpmMaterialNames.append(material.name)
		# Vertices and their properties
		bm = bmesh.new()
		bmeshMeshes.append(bm) # Keep track of the bmeshes we create
		bm.from_mesh(mesh)
		bm.verts.ensure_lookup_table()
		bm.verts.index_update()
		uvLayer = bm.loops.layers.uv.active
		if not uvLayer:
			uvLayer = bm.loops.layers.uv[0]

		# If we're generating a skin element, recover the vertex group that each vertex belongs to
		skinData: SkinData = skinDataByMeshName.get(mesh.name)
		exportSkinElement = skinData is not None
		boneIndicesByVertexGroupIndex: dict[int, list[int]] = {}
		if skinData:
			sourceObject: bpy.types.Object = skinData.instanceObject
			for vertexGroup in sourceObject.vertex_groups:
				# To convert a vertex group to a TPM bone, its name must end in a two-digit number (and not be *just* a number)
				boneMatch = vertexGroupBoneRegex.match(vertexGroup.name[-3:])
				if not boneMatch:
					exportSkinElement = False
					operator.report({'WARNING'}, f"Mesh '{tpmMeshName}' (with instance '{sourceObject.name}') contains an invalid vertex group '{vertexGroup.name}' - for bones to be generated, the name must end in a two-digit number.")
					continue # Continue rather than break so we report all the bad bone names
				# Construct the desired vertex group/bone name
				boneIndex = int(boneMatch.group(1))
				if boneIndex in boneIndicesByVertexGroupIndex.values():
					exportSkinElement = False
					operator.report({'WARNING'}, f"Mesh '{tpmMeshName}' (with instance '{sourceObject.name}') contains a duplicate bone ID (vertex group name's trailing digits): {boneIndex}")
					continue
				boneIndicesByVertexGroupIndex[vertexGroup.index] = boneIndex

		vertex: bmesh.types.BMVert
		for vertex in bm.verts:
			tpmVertices.append(vertex.co)
			tpmNormals.append(vertex.normal)
			# bmesh vertices, as long as we haven't add/removed any since creation, are indexed identically to the mesh vertices
			# Assign this vertex to a bone based on the greatest weighted vertex group, or leave it unbound if this vertex is not assigned to any groups
			if exportSkinElement:
				meshVertex = mesh.vertices[vertex.index]
				if meshVertex.groups:
					vertexGroupIndex = max(meshVertex.groups, key=lambda groupEl : groupEl.weight).group
					tpmVertexBoneIndices.append(boneIndicesByVertexGroupIndex.get(vertexGroupIndex))
				else:
					tpmVertexBoneIndices.append(GetDefaultUnboundBoneIndex())
		if exportSkinElement and len(tpmVertexBoneIndices) != len(tpmVertices):
			raise TPMException(f"Mesh '{tpmMeshName}': number of vertices ({len(tpmVertices)}) does not match the number of vertex bone indices ({len(tpmVertexBoneIndices)})")
		
		texCoordSet: set[Vector] = set()
		for face in bm.faces:
			for loop in face.loops:
				# Must be immutable in order to emplace into a set (hashing requires immutable)
				# Cannot freeze the mesh's data since we don't own it
				uv = loop[uvLayer].uv.copy().freeze()
				texCoordSet.add(uv)
		tpmTexCoords = list(texCoordSet)
		
		# Now construct each face
		flippedNormalIndicesByVertexIndex: dict[int, int] = {}
		face: bmesh.types.BMFace
		for face in bm.faces:
			# Figure out if this is an alpha face - if so, we likely need to double-side it
			alphaFace = False
			backfaceCulling = None
			if face.material_index < len(tpmMaterialNames):
				tpmMaterialForFace = tpmMaterialsByName.get(tpmMaterialNames[face.material_index])
				if tpmMaterialForFace:
					alphaFace = tpmMaterialForFace.opacitymap is not None
					backfaceCulling = mesh.materials[face.material_index].use_backface_culling
			
			materialIndex = face.material_index + 1
			# Convert triangle fan to triangle list
			for triangle in range(0, len(face.loops) - 2):
				vertexIndices: list[int] = []
				texCoordIndices: list[int] = []
				normalIndices: list[int] = []
				v0 = 0
				v1 = triangle + 1
				v2 = triangle + 2
				
				for v in (v0, v1, v2):
					loop = face.loops[v]
					# TPM indices are 1-based
					vertexIndices.append(loop.vert.index + 1)
					normalIndices.append(loop.vert.index + 1)
					texCoordIndices.append(tpmTexCoords.index(loop[uvLayer].uv) + 1)
				tpmFaces.append(TPM.Mesh.Face(vertexIndices, texCoordIndices, normalIndices, materialIndex))
			
			# Determine whether we need to write a backface as well
			if alphaFace and (opacityFaceExportMode == "DOUBLE_SIDED" or opacityFaceExportMode == "RESPECT_BACKFACE_CULLING" and not backfaceCulling):
				# Write a face wound in reverse, with flipped normals
				for triangle in range(0, len(face.loops) - 2):
					vertexIndices: list[int] = []
					texCoordIndices: list[int] = []
					normalIndices: list[int] = []
					v0 = 0
					v1 = triangle + 1
					v2 = triangle + 2
					
					faceForwardNormal = (face.loops[v1].vert.co - face.loops[v0].vert.co).cross(face.loops[v2].vert.co - face.loops[v0].vert.co)
					faceForwardNormal.normalize()
					
					for v in (v0, v2, v1): # Flipped vertex order
						loop = face.loops[v]
						# TPM indices are 1-based
						vertexIndices.append(loop.vert.index + 1)
						texCoordIndices.append(tpmTexCoords.index(loop[uvLayer].uv) + 1)
						# Handle the reflected normals
						reflectedNormalIndex = flippedNormalIndicesByVertexIndex.get(loop.vert.index)
						if not reflectedNormalIndex:
							flippedNormal = loop.vert.normal.reflect(faceForwardNormal)
							reflectedNormalIndex = len(tpmNormals)
							flippedNormalIndicesByVertexIndex[loop.vert.index] = reflectedNormalIndex
							tpmNormals.append(flippedNormal)
						normalIndices.append(reflectedNormalIndex + 1) # 1-based
							
					tpmFaces.append(TPM.Mesh.Face(vertexIndices, texCoordIndices, normalIndices, materialIndex))
		
		# Sort faces by material index
		tpmFaces.sort(key=lambda f: f.materialIndex)
		print(f"Wrote {len(tpmFaces)} faces in the export of {tpmMeshName}")
		
		# Construct the mesh
		if exportSkinElement:
			print(f"Exporting '{tpmMeshName}' as Skin")
			tpmMeshes.append(TPM.Skin(tpmMeshName, tpmMaterialNames, tpmVertices, tpmVertexBoneIndices, tpmTexCoords, tpmNormals, tpmFaces))
		else:
			print(f"Exporting '{tpmMeshName}' as Mesh")
			tpmMeshes.append(TPM.Mesh(tpmMeshName, tpmMaterialNames, tpmVertices, tpmTexCoords, tpmNormals, tpmFaces))
	
	# Instances
	for object in objects:
		if isinstance(object.data, bpy.types.Mesh):
			meshName = object.data.name
			position = object.location
			rotation = object.rotation_euler
			scale = max(object.scale)
			tpmInstances.append(TPM.Instance(object.name, meshName, position, rotation, scale))
	
	# Bones
	for meshName, skinData in skinDataByMeshName.items():
		armatureObject: bpy.types.Object = skinData.armatureObject
		armature: bpy.types.Armature = armatureObject.data
		for bone in armature.bones:
			nameMatch = vertexGroupBoneRegex.match(bone.name[-3:])
			if not nameMatch:
				operator.report({'WARNING'}, f"Mesh '{meshName}' (with instance '{skinData.instanceObject.name}') contains a bone with invalid name '{bone.name}' - expected this to end with exactly two digits.")
				continue
			tpmBoneName = ConstructJointName(meshName, int(nameMatch.group(1)))
			pos = bone.center
			rot = bone.matrix.to_euler('ZYX')
			tpmBones.append(TPM.Bone(tpmBoneName, pos, Vector((rot.x, rot.y, rot.z))))

	# Create a TPM
	tpm = TPM(tpmFileInfo, tpmMaterials, tpmMeshes, tpmInstances, tpmBones)
	
	# Convert it to a TPM_Raw
	tpmRaw = TPMToTPMRaw(tpm)
	
	# Write it to file
	file.write(TPMRawToString(tpmRaw))
	print("Export finished")

# ----------------------------------------------------------------
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
			Export(self, context.selected_objects, f, self.opacityFaceExportMode)
		except TPMException as e:
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