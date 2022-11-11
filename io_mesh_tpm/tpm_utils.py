import bpy
import bmesh
import math
import re
from datetime import datetime
from mathutils import Vector
from pathlib import Path

# A class encapsulating the TPM file format without any specific implementation
class TPM_Raw:
	class Block:
		def __init__(self, blockType, blockIdentifier, properties):
			self.type = blockType
			self.identifier = blockIdentifier # May be None
			self.properties = properties # list of pairs, not dict, since keys can be duplicated and we must preserve ordering
	
	def __init__(self, blocks):
		self.blocks = blocks

# A class encapsulating the TPM file format, with the expected types of blocks defined
class TPM:
	class FileInfo:
		def __init__(self, formatVersion, name, version, source, date, comments):
			if formatVersion is None:
				raise ValueError("FileInfo cannot be constructed with None formatVersion")
			self.formatVersion = formatVersion
			self.name = name
			self.version = version
			self.source = source
			self.date = date
			self.comments = comments
	
	class Instance:
		def __init__(self, name, mesh, position, rotation, scale):
			if None in (name, mesh, position, rotation, scale):
				raise ValueError("Instance cannot be constructed with None values")
			self.name = name
			self.mesh = mesh
			self.position = position
			self.rotation = rotation
			self.scale = scale
	
	class Material:
		def __init__(self, name, colourmap, bumpmap, opacitymap):
			if name is None:
				raise ValueError("Material cannot be constructed with None name")
			self.name = name
			self.colourmap = colourmap
			self.bumpmap = bumpmap
			self.opacitymap = opacitymap
	
	class Mesh:
		class Face:
			def __init__(self, vertexIndices, texCoordIndices, normalIndices, materialIndex):
				# All TPM instances are 1-based
				self.vertexIndices = vertexIndices
				self.texCoordIndices = texCoordIndices
				self.normalIndices = normalIndices
				self.materialIndex = materialIndex
				if len(vertexIndices) != 3:
					raise ValueError("Face must have exactly three vertex indices")
				if len(texCoordIndices) != 3:
					raise ValueError("Face must have exactly three texture coordinate indices")
				if len(normalIndices) != 3:
					raise ValueError("Face must have exactly three normal indices")
		
		def __init__(self, name, materialNames, vertices, textureCoords, normals, faces):
			if name is None:
				raise ValueError("Mesh cannot be constructed with None name")
			self.name = name
			self.materialNames = materialNames
			self.vertices = vertices
			self.textureCoords = textureCoords
			self.normals = normals
			self.faces = faces
					
	def __init__(self, fileInfo, materials, meshes, instances):
		if fileInfo is None:
			raise ValueError("TPM must contain a fileinfo block")
		self.fileInfo = fileInfo
		self.materials = materials
		self.meshes = meshes
		self.instances = instances

# ----------------------------------------------------------------
# TPM Importing
# ----------------------------------------------------------------
def StringToTPMRaw(tpmData):
	# Full line regex matches
	typeWithOptionalIdentifierRegex = re.compile(r'(\w+)\s*(?:"([^"]+)")?')
	propertyRegex = re.compile(r'(\w+)\s*=\s*(.+)')
	
	def NonTrivialLine(lineIter):
		# Skip over any empty or whitespace lines
		line = None
		while True:
			line = next(lineIter)
			if not line or line.isspace():
				continue
			# Remove any leading or trailing whitespace
			line = line.strip()
			# Ignore comments
			if line.startswith("//"):
				continue
			return line
	
	def ParseProperty(line):
		pairMatch = propertyRegex.fullmatch(line)
		if pairMatch is None:
			raise RuntimeError("Error on line \"" + line + "\": expected property")
		return [pairMatch.group(1), pairMatch.group(2)] # Group indexing follows the usual regex convention of starting from 1
	
	def ParseBlock(lineIter):
		# If we're at the end of the file, don't panic
		try:
			# Find a non-trivial line
			line = NonTrivialLine(lineIter)
		except StopIteration:
			return None
			
		try:
			# Find a type, with a possible identifier
			typeIdentifierMatch = typeWithOptionalIdentifierRegex.fullmatch(line)
			if typeIdentifierMatch is None:
				raise RuntimeError("Error on line \"" + line + "\": expected block type or type-identifier")
			blockType = typeIdentifierMatch.group(1)
			blockIdentifier = None
			if len(typeIdentifierMatch.groups()) > 1:
				blockIdentifier = typeIdentifierMatch.group(2) # Group indexing starts from 1
			
			# Expect an open brace
			line = NonTrivialLine(lineIter)
			if line != "{":
				raise RuntimeError("Error on line \"" + line + "\": expected opening brace after type-identifier " + blockType + ((" " + blockIdentifier) if blockIdentifier else ""))
			
			# Read properties
			properties = list()
			while True:
				line = NonTrivialLine(lineIter)
				if line == "}":
					break
				properties.append(ParseProperty(line))
			
			# Return the block
			return TPM_Raw.Block(blockType, blockIdentifier, properties)
		except StopIteration as e:
			raise RuntimeError("Unexpected end of file reached whilst parsing block") from e
	
	lines = tpmData.splitlines()
	lineIter = iter(lines)
	
	blocks = list()
	while True:
		block = ParseBlock(lineIter)
		if block is None:
			break
		blocks.append(block)
	return TPM_Raw(blocks)

# ----------------------------------------------------------------
def ChopCharsFromEndsAsymmetrical(s, cStart, cEnd):
	if len(s) >= 2 and s[0] in cStart and s[-1] in cEnd:
		return (s[1:-1], True)
	return (s, False)

# ----------------------------------------------------------------
def ChopCharsFromEnds(s, chop):
	return ChopCharsFromEndsAsymmetrical(s, chop, chop)

# ----------------------------------------------------------------
def ChopQuotes(s):
	return ChopCharsFromEnds(s, '"')

# ----------------------------------------------------------------
def VectorStringToVector(s):
	line = s.strip() # Remove leading and trailing whitespace
	line, wasChopped = ChopCharsFromEndsAsymmetrical(line, "(", ")")
	if not wasChopped:
		raise ValueError("\"" + s + "\" cannot be converted to a vector")
	compStrings = line.split(",")
	components = list()
	for c in compStrings:
		components.append(float(c))
	return Vector(components)

# ----------------------------------------------------------------
def TPMRawToTPM(raw):
	faceEntryRegex = re.compile(r'\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*(\d+)')
	
	# Iterate over each block, and load the data from it
	fileInfo = None
	materials = list()
	meshes = list()
	instances = list()
	
	for block in raw.blocks:
		# Remove enclosing quotation marks from any string values
		if block.identifier is not None:
			block.identifier, *_ = ChopQuotes(block.identifier)
		for props in block.properties:
			props[1], *_ = ChopQuotes(props[1])
		
		# Create the relevant block type
		if block.type == "fileinfo":
			if fileInfo is not None:
				raise ValueError("TPM contains more than one fileinfo block")
			stringDict = dict(block.properties)
			fileInfo = TPM.FileInfo(stringDict["formatversion"], stringDict.get("name"), stringDict.get("version"), stringDict.get("source"), stringDict.get("date"), stringDict.get("comments"))
		elif block.type == "instance":
			# Convert vectors and numeric types
			stringDict = dict(block.properties)
			position = VectorStringToVector(stringDict["position"])
			rotation = VectorStringToVector(stringDict["rotation"])
			scale = float(stringDict["scale"])
			instances.append(TPM.Instance(block.identifier, stringDict["mesh"], position, rotation, scale))
		elif block.type == "material":
			stringDict = dict(block.properties)
			materials.append(TPM.Material(block.identifier, stringDict.get("colormap"), stringDict.get("bumpmap"), stringDict.get("opacitymap")))
		elif block.type == "mesh":
			# Vector conversion and face construction required
			materialNames = list()
			vertices = list()
			texCoords = list()
			normals = list()
			faces = list()
			for props in block.properties:
				if props[0] == "m":
					materialNames.append(props[1])
				elif props[0] == "v":
					vertices.append(VectorStringToVector(props[1]))
				elif props[0] == "t":
					texCoords.append(VectorStringToVector(props[1]))
				elif props[0] == "n":
					normals.append(VectorStringToVector(props[1]))
				elif props[0] == "f":
					matches = faceEntryRegex.fullmatch(props[1])
					if not matches:
						raise ValueError("Mesh face property \"" + props[1] + "\" is not in the expected format.")
					v1 = int(matches.group(1))
					v2 = int(matches.group(2))
					v3 = int(matches.group(3))
					t1 = int(matches.group(4))
					t2 = int(matches.group(5))
					t3 = int(matches.group(6))
					n1 = int(matches.group(7))
					n2 = int(matches.group(8))
					n3 = int(matches.group(9))
					m = int(matches.group(10))
					faces.append(TPM.Mesh.Face((v1, v2, v3), (t1, t2, t3), (n1, n2, n3), m))
				else:
					raise ValueError("Unknown mesh property type \"" + props[0] + "\" - expected one of m, v, t, n, or f")
			meshes.append(TPM.Mesh(block.identifier, materialNames, vertices, texCoords, normals, faces))
		elif block.type == "skin" or block.type == "bone":
			continue # Silently ignore unsupported but valid block identifiers
		else:
			raise ValueError("TPM contains unexpected block type \"" + block.type + "\"")
	return TPM(fileInfo, materials, meshes, instances)

# ----------------------------------------------------------------
def FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, textureName):
	if stripDirectoriesFromTextureNames:
		textureName = Path(textureName).name
	filename = Path(textureSearchPath).joinpath(textureName)
	if not filename.is_file():
		raise ValueError("Failed to find texture \"" + textureName + "\" in path \"" + textureSearchPath + "\".\nFinal lookup was \"" + str(filename) + "\"")
	return str(filename)

# ----------------------------------------------------------------
def CreateImageNodeFromTPMTexMap(mat, mapName, filepath):
	imageNode = mat.node_tree.nodes.new("ShaderNodeTexImage")
	imageNode.image = bpy.data.images.get(mapName)
	if not imageNode.image:
		imageNode.image = bpy.data.images.load(filepath)
		imageNode.image.name = mapName
	return imageNode

# ----------------------------------------------------------------
def Import(tpmData, textureSearchPath, stripDirectoriesFromTextureNames, overwriteExistingMaterials, toCollection):
	print("Beginning import")
	# Process the TPM
	tpm = TPMRawToTPM(StringToTPMRaw(tpmData))
	
	# Add each material
	blenderMaterialsByName = dict()
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
				imageNode = CreateImageNodeFromTPMTexMap(mat, material.colourmap, FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, material.colourmap))
				imageNode.name = "Colour Map"
				mat.node_tree.links.new(imageNode.outputs[0], bsdfNode.inputs["Base Color"])
			
			if material.bumpmap:
				# Bump node between image and normal input
				bumpNode = nodes.new("ShaderNodeBump")
				bumpNode.name = "Bump"
				mat.node_tree.links.new(bumpNode.outputs[0], bsdfNode.inputs["Normal"])
				
				# Image node
				imageNode = CreateImageNodeFromTPMTexMap(mat, material.bumpmap, FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, material.bumpmap))
				imageNode.name = "Bump Map"
				mat.node_tree.links.new(imageNode.outputs[0], bumpNode.inputs[2])
				
			
			if material.opacitymap:
				imageNode = CreateImageNodeFromTPMTexMap(mat, material.opacitymap, FindTextureOnDisk(textureSearchPath, stripDirectoriesFromTextureNames, material.opacitymap))
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
	
	# Add each mesh
	blenderMeshesByName = dict()
	tpmMeshesByName = dict()
	for tpmMesh in tpm.meshes:
		mesh = bpy.data.meshes.new(tpmMesh.name)
		bm = bmesh.new()
		
		# Add each vertex
		for vertex in tpmMesh.vertices:
			bm.verts.new(vertex)
		bm.verts.ensure_lookup_table()
		bm.verts.index_update()
		
		# Add each face - note that TPM indices are 1-based
		blenderFaceToTPMFaceIndexMap = dict()
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
		
		# Populate the mesh
		bm.to_mesh(mesh)
		mesh.update()
		
		blenderMeshesByName[tpmMesh.name] = mesh
		tpmMeshesByName[tpmMesh.name] = tpmMesh

	# Get or create the collection to add to
	collection = toCollection
	if collection is None:
		collection = bpy.data.collections.new(tpm.fileInfo.name or "TPM_Import")
		bpy.context.scene.collection.children.link(collection)
	
	# Add each instance as an object in the collection
	for tpmInstance in tpm.instances:
		meshName = tpmInstance.mesh
		blenderMesh = blenderMeshesByName[meshName]
		object = bpy.data.objects.new(tpmInstance.name, blenderMesh)
		
		object.location = tpmInstance.position
		for i, v in enumerate(object.scale):
			object.scale[i] = tpmInstance.scale
		rotRadians = Vector(tpmInstance.rotation)
		for i, v in enumerate(rotRadians):
			rotRadians[i] = math.radians(v)
		object.rotation_euler = rotRadians
		
		# Append materials in order to ensure correct indexing
		if len(object.data.materials) != 0:
			raise RuntimeError("Expected object materials to be empty")
		
		tpmMesh = tpmMeshesByName[meshName]
		for materialIndex, materialName in enumerate(tpmMesh.materialNames):
			object.data.materials.append(blenderMaterialsByName[materialName])
			#object.data.materials[materialIndex] = blenderMaterialsByName[materialName]
		
		collection.objects.link(object)
	print("Import finished")

# ----------------------------------------------------------------
# TPM Exporting
# ----------------------------------------------------------------
def EncloseInQuotes(s):
	return "\"" + s + "\""

# ----------------------------------------------------------------
def TPMToTPMRaw(tpm):
	# Some TPM-ifying needs to occur - in particular:
	# - Strings need enclosing in quotes
	# - Rotations need converting to degrees
	# - Vectors (vertices, tex coords, normals) and faces need to be put into the correct format
	
	blocks = list()
	
	# FileInfo
	fileInfoProperties = list()
	fileInfoProperties.append(["formatversion", tpm.fileInfo.formatVersion])
	if tpm.fileInfo.name:
		fileInfoProperties.append(["name", EncloseInQuotes(tpm.fileInfo.name)])
	if tpm.fileInfo.version:
		fileInfoProperties.append(["version", tpm.fileInfo.version])
	if tpm.fileInfo.source:
		fileInfoProperties.append(["source", EncloseInQuotes(tpm.fileInfo.source)])
	if tpm.fileInfo.date:
		fileInfoProperties.append(["date", tpm.fileInfo.date])
	if tpm.fileInfo.comments:
		fileInfoProperties.append(["comments", EncloseInQuotes(tpm.fileInfo.comments)])
	blocks.append(TPM_Raw.Block("fileinfo", None, fileInfoProperties))
	
	# Materials
	for mat in tpm.materials:
		materialProperties = list()
		if mat.colourmap:
			materialProperties.append(["colormap", EncloseInQuotes(mat.colourmap)])
		if mat.bumpmap:
			materialProperties.append(["bumpmap", EncloseInQuotes(mat.bumpmap)])
		if mat.opacitymap:
			materialProperties.append(["opacitymap", EncloseInQuotes(mat.opacitymap)])
		blocks.append(TPM_Raw.Block("material", EncloseInQuotes(mat.name), materialProperties))
	
	# Meshes
	for mesh in tpm.meshes:
		meshProperties = list()
		# Materials
		for materialName in mesh.materialNames:
			meshProperties.append(["m", EncloseInQuotes(materialName)])
		# Vertices
		for vertex in mesh.vertices:
			meshProperties.append(["v", f"({vertex[0]},{vertex[1]},{vertex[2]})"])
		# Texture coordinates
		for texCoord in mesh.textureCoords:
			meshProperties.append(["t", f"({texCoord[0]},{texCoord[1]})"])
		# Normals
		for normal in mesh.normals:
			print("TPM: n = %s" % normal)
			meshProperties.append(["n", f"({normal[0]},{normal[1]},{normal[2]})"])
		# Faces
		for face in mesh.faces:
			v = face.vertexIndices
			t = face.texCoordIndices
			n = face.normalIndices
			m = face.materialIndex
			meshProperties.append(["f", f"({v[0]},{v[1]},{v[2]}),({t[0]},{t[1]},{t[2]}),({n[0]},{n[1]},{n[2]}),{m}"])
		blocks.append(TPM_Raw.Block("mesh", EncloseInQuotes(mesh.name), meshProperties))
	
	# Instances
	for instance in tpm.instances:
		p = instance.position
		r = instance.rotation.copy()
		for i, v in enumerate(r):
			r[i] = math.degrees(v)
		s = instance.scale
		instanceProperties = list()
		instanceProperties.append(["mesh", EncloseInQuotes(instance.mesh)])
		instanceProperties.append(["position", f"({p[0]},{p[1]},{p[2]})"])
		instanceProperties.append(["rotation", f"({r[0]},{r[1]},{r[2]})"])
		instanceProperties.append(["scale", f"{s}"])
		blocks.append(TPM_Raw.Block("instance", EncloseInQuotes(instance.name), instanceProperties))
	
	return TPM_Raw(blocks)

# ----------------------------------------------------------------
def WriteTPMRawToFile(tpmRaw, file):
	for block in tpmRaw.blocks:
		file.write(block.type)
		if block.identifier:
			file.write(" " + block.identifier)
		file.write("\n{\n")
		for p in block.properties:
			file.write("\t" + p[0] + " = " + p[1] + "\n")
		file.write("}\n\n")

# ----------------------------------------------------------------
def Export(objects, file, opacityFaceExportMode):
	print("Beginning export")
	# Find the set of meshes we need to export
	blenderMeshes = set()
	for object in objects:
		blenderMeshes.add(object.data)
	
	# Find the set of materials we need to export
	blenderMaterials = set()
	for mesh in blenderMeshes:
		for material in mesh.materials:
			blenderMaterials.add(material)
	
	# Create TPM lists (and file info)
	tpmFileInfo = TPM.FileInfo(formatVersion="1.0.1", name=Path(file.name).name, source=bpy.path.basename(bpy.context.blend_data.filepath), date=datetime.now().strftime("%m/%d/%Y %I:%M:%S %p"), version=None, comments=None)
	tpmInstances = list()
	tpmMaterials = list()
	tpmMeshes = list()
	
	# Populate TPM lists:
	# Materials - do these first so we can query alpha properties of faces during mesh construction
	for mat in blenderMaterials:
		# mat.node_tree.active_output is always -1. Useful.
		materialOutput = None
		for node in mat.node_tree.nodes:
			if node.bl_idname == "ShaderNodeOutputMaterial":
				materialOutput = node
				break
		if materialOutput is None:
			raise ValueError("Could not find a material output node for material \"" + mat.name + "\"")
		
		bsdfTypeNode = materialOutput.inputs["Surface"].links[0].from_node
		
		# See if it has a "Color" link
		tpmColourMap = None
		colourInput = bsdfTypeNode.inputs.get("Color")
		if not colourInput:
			colourInput = bsdfTypeNode.inputs.get("Base Color")
		if colourInput and len(colourInput.links) > 0:
			colourImageNode = colourInput.links[0].from_node
			if colourImageNode.bl_idname == "ShaderNodeTexImage" and colourImageNode.image:
				tpmColourMap = colourImageNode.image.name
		
		# See if it has a "Normal" link
		tpmBumpMap = None
		normalInput = bsdfTypeNode.inputs.get("Normal")
		if normalInput and len(normalInput.links) > 0:
			bumpNode = normalInput.links[0].from_node
			if bumpNode.bl_idname == "ShaderNodeBump":
				bumpHeightInput = bumpNode.inputs.get("Height")
				if bumpHeightInput and len(bumpHeightInput.links) > 0:
					bumpImageNode = bumpHeightInput.links[0].from_node
					if bumpImageNode.bl_idname == "ShaderNodeTexImage" and bumpImageNode.image:
						tpmBumpMap = bumpImageNode.image.name
		
		# See if it has an "Alpha" link
		tpmOpacityMap = None
		alphaInput = bsdfTypeNode.inputs.get("Alpha")
		if alphaInput and len(alphaInput.links) > 0:
			alphaImageNode = alphaInput.links[0].from_node
			if alphaImageNode.bl_idname == "ShaderNodeTexImage" and alphaImageNode.image:
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
	
	# Meshes
	bmeshMeshes = list() # (vectors in) bmeshes must persist until we've written the TPM 
	for mesh in blenderMeshes:
		tpmMeshName = mesh.name
		tpmMaterialNames = list()
		tpmVertices = list()
		tpmTexCoords = list()
		tpmNormals = list()
		tpmFaces = list()
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
		
		for vertex in bm.verts:
			tpmVertices.append(vertex.co)
			tpmNormals.append(vertex.normal)
		
		texCoordSet = set()
		for face in bm.faces:
			for loop in face.loops:
				# Must be immutable in order to emplace into a set (hashing requires immutable)
				# Cannot freeze the mesh's data since we don't own it
				uv = loop[uvLayer].uv.copy().freeze()
				texCoordSet.add(uv)
		tpmTexCoords = list(texCoordSet)
		
		# Now construct each face
		flippedNormalIndicesByVertexIndex = dict()
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
				vertexIndices = list()
				texCoordIndices = list()
				normalIndices = list()
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
					vertexIndices = list()
					texCoordIndices = list()
					normalIndices = list()
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
		tpmMeshes.append(TPM.Mesh(tpmMeshName, tpmMaterialNames, tpmVertices, tpmTexCoords, tpmNormals, tpmFaces))
	
	# Instances
	for object in objects:
		meshName = object.data.name
		position = object.location
		rotation = object.rotation_euler
		scale = max(object.scale)
		tpmInstances.append(TPM.Instance(object.name, meshName, position, rotation, scale))
	
	# Create a TPM
	tpm = TPM(tpmFileInfo, tpmMaterials, tpmMeshes, tpmInstances)
	
	# Convert it to a TPM_Raw
	tpmRaw = TPMToTPMRaw(tpm)
	
	# Write it to file
	WriteTPMRawToFile(tpmRaw, file)
	print("Export finished")