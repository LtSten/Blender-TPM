import re
from mathutils import Vector
from .tpm_utils import *

# ----------------------------------------------------------------
class TPMException(RuntimeError):
	pass

# ----------------------------------------------------------------
# TPM Representations
# ----------------------------------------------------------------

# ----------------------------------------------------------------
# A class encapsulating the TPM file format without any specific implementation
TPM_RawPropertyList = list[tuple[str, str]] # Type aliases defined in classes can't be used within those classes, unfortunately
class TPM_Raw:
	PropertyList = TPM_RawPropertyList
	class Block:
		def __init__(self, blockType: str, blockIdentifier: str, properties: TPM_RawPropertyList):
			self.type = blockType
			self.identifier = blockIdentifier # May be None
			self.properties = properties # list of pairs, not dict, since keys can be duplicated and we must preserve ordering
	
	def __init__(self, blocks: list[Block]):
		self.blocks = blocks

# ----------------------------------------------------------------
# A class encapsulating the TPM file format, with the expected types of blocks defined
class TPM:
	class FileInfo:
		def __init__(self, formatVersion: str, name: str, version: str, source: str, date: str, comments: str):
			if formatVersion is None:
				raise TPMException("FileInfo cannot be constructed with None formatVersion")
			self.formatVersion = formatVersion
			self.name = name
			self.version = version
			self.source = source
			self.date = date
			self.comments = comments
	
	class Instance:
		def __init__(self, name: str, mesh: str, position: Vector, rotation: Vector, scale: float):
			if None in (name, mesh, position, rotation, scale):
				raise TPMException("Instance cannot be constructed with None values")
			self.name = name
			self.mesh = mesh
			self.position = position
			self.rotation = rotation
			self.scale = scale
	
	class Material:
		def __init__(self, name: str, colourmap: str, bumpmap: str, opacitymap: str):
			if name is None:
				raise TPMException("Material cannot be constructed with None name")
			self.name = name
			self.colourmap = colourmap
			self.bumpmap = bumpmap
			self.opacitymap = opacitymap
	
	class Mesh:
		class Face:
			def __init__(self, vertexIndices: tuple[int, int, int], texCoordIndices: tuple[int, int, int], normalIndices: tuple[int, int, int], materialIndex: int):
				# All TPM instances are 1-based
				self.vertexIndices = vertexIndices
				self.texCoordIndices = texCoordIndices
				self.normalIndices = normalIndices
				self.materialIndex = materialIndex
				if len(vertexIndices) != 3:
					raise TPMException("Face must have exactly three vertex indices")
				if len(texCoordIndices) != 3:
					raise TPMException("Face must have exactly three texture coordinate indices")
				if len(normalIndices) != 3:
					raise TPMException("Face must have exactly three normal indices")
		
		def __init__(self, name: str, materialNames: list[str], vertices: list[Vector], textureCoords: list[Vector], normals: list[Vector], faces: list[Face]):
			if name is None:
				raise TPMException("Mesh cannot be constructed with None name")
			self.name = name
			self.materialNames = materialNames
			self.vertices = vertices
			self.textureCoords = textureCoords
			self.normals = normals
			self.faces = faces
	
	class Skin(Mesh):
		def __init__(self, name: str, materialNames: list[str], vertices: list[Vector], vertexBoneIndices: list[int], textureCoords: list[Vector], normals: list[Vector], faces: list["Mesh.Face"]):
			super().__init__(name, materialNames, vertices, textureCoords, normals, faces)
			self.vertexBoneIndices = vertexBoneIndices
			if len(vertexBoneIndices) != len(vertices):
				raise TPMException(f"Skin must have one bone index per vertex: there are {len(vertices)} vertices but {len(vertexBoneIndices)} bone indices.")

	class Bone:
		def __init__(self, name: str, position: Vector, rotation: Vector):
			if name is None:
				raise TPMException("Bone cannot be constructed with None name")
			self.name = name
			self.position = position
			self.rotation = rotation
	
	def __init__(self, fileInfo: FileInfo, materials: list[Material], meshes: list[Mesh], instances: list[Instance], bones: list[Bone]):
		if fileInfo is None:
			raise TPMException("TPM must contain a fileinfo block")
		self.fileInfo = fileInfo
		self.materials = materials
		self.meshes = meshes
		self.instances = instances
		self.bones = bones

# ----------------------------------------------------------------
# To-TPM conversions
# ----------------------------------------------------------------
def StringToTPMRaw(tpmData: str) -> TPM_Raw:
	return LinesToTPMRaw(tpmData.splitlines())

# ----------------------------------------------------------------
def LinesToTPMRaw(tpmData: list[str]) -> TPM_Raw:
	# Full line regex matches
	typeWithOptionalIdentifierRegex = re.compile(r'(\w+)\s*(?:"([^"]+)")?')
	propertyRegex = re.compile(r'(\w+)\s*=\s*(.+)')
	
	def NonTrivialLine(lineIter) -> str:
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
			raise TPMException(f"Error on line '{line}': expected property")
		return [pairMatch.group(1), pairMatch.group(2)] # Group indexing follows the usual regex convention of starting from 1
	
	def ParseBlock(lineIter) -> TPM_Raw.Block:
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
				raise TPMException(f"Error on line '{line}': expected block type or type-identifier")
			blockType = typeIdentifierMatch.group(1)
			blockIdentifier = None
			if len(typeIdentifierMatch.groups()) > 1:
				blockIdentifier = typeIdentifierMatch.group(2) # Group indexing starts from 1
			
			# Expect an open brace
			line = NonTrivialLine(lineIter)
			if line != "{":
				raise TPMException(f"Error on line '{line}': expected opening brace after type-identifier {blockType} {f' {blockIdentifier}' if blockIdentifier else ''}")
			
			# Read properties
			properties: TPM_Raw.PropertyList = []
			while True:
				line = NonTrivialLine(lineIter)
				if line == "}":
					break
				properties.append(ParseProperty(line))
			
			# Return the block
			return TPM_Raw.Block(blockType, blockIdentifier, properties)
		except StopIteration as e:
			raise TPMException("Unexpected end of file reached whilst parsing block") from e
	
	lineIter = iter(tpmData)
	
	blocks: list[TPM_Raw.Block] = []
	while True:
		block = ParseBlock(lineIter)
		if block is None:
			break
		blocks.append(block)
	return TPM_Raw(blocks)

# ----------------------------------------------------------------
def TPMRawToTPM(raw: TPM_Raw, WarningCallback) -> TPM:
	faceEntryRegex = re.compile(r'\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*\((\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\)\s*,\s*(\d+)')
	skinVertexRegex = re.compile(r'(\(.*?\))\s*,\s*(\d+)')
	
	# Iterate over each block, and load the data from it
	fileInfo: TPM.FileInfo = None
	materials: list[TPM.Material] = []
	meshes: list[TPM.Mesh] = []
	instances: list[TPM.Instance] = []
	bones: list[TPM.Bone] = []
	
	for block in raw.blocks:
		# Remove enclosing quotation marks from any string values
		if block.identifier is not None:
			block.identifier, *_ = ChopQuotes(block.identifier)
		for props in block.properties:
			props[1], *_ = ChopQuotes(props[1])
		
		# Create the relevant block type
		if block.type == "fileinfo":
			if fileInfo is not None:
				raise TPMException("TPM contains more than one fileinfo block")
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
		elif block.type in ("mesh", "skin"):
			# Vector conversion and face construction required
			materialNames: list[str] = []
			vertices: list[Vector] = []
			vertexBoneIndices: list[int] = []
			texCoords: list[Vector] = []
			normals: list[Vector] = []
			faces: list[TPM.Mesh.Face] = []
			for props in block.properties:
				if props[0] == "m":
					materialNames.append(props[1])
				elif props[0] == "v":
					vertexDef = props[1]
					if block.type == "skin":
						matches = skinVertexRegex.fullmatch(vertexDef)
						if not matches:
							raise TPMException(f"Skin vertex property '{props[1]}' is not in the expected format.")
						vertices.append(VectorStringToVector(matches.group(1)))
						vertexBoneIndices.append(int(matches.group(2)))
					else:
						vertices.append(VectorStringToVector(vertexDef))
				elif props[0] == "t":
					texCoords.append(VectorStringToVector(props[1]))
				elif props[0] == "n":
					normals.append(VectorStringToVector(props[1]))
				elif props[0] == "f":
					matches = faceEntryRegex.fullmatch(props[1])
					if not matches:
						raise TPMException(f"Mesh face property '{props[1]}' is not in the expected format.")
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
					raise TPMException(f"Unknown mesh property type '{props[0]}' - expected one of m, v, t, n, or f")
			if block.type == "mesh":
				meshes.append(TPM.Mesh(block.identifier, materialNames, vertices, texCoords, normals, faces))
			else:
				meshes.append(TPM.Skin(block.identifier, materialNames, vertices, vertexBoneIndices, texCoords, normals, faces))
		elif block.type == "bone":
			stringDict = dict(block.properties)
			position = VectorStringToVector(stringDict["position"])
			rotation = VectorStringToVector(stringDict["rotation"])
			bones.append(TPM.Bone(block.identifier, position, rotation))
		else:
			raise TPMException(f"TPM contains unexpected block type '{block.type}'")
	return TPM(fileInfo, materials, meshes, instances, bones)

# ----------------------------------------------------------------
# From-TPM conversions
# ----------------------------------------------------------------
def TPMToTPMRaw(tpm: TPM) -> TPM_Raw:
	# Some TPM-ifying needs to occur - in particular:
	# - Strings need enclosing in quotes
	# - Rotations need converting to degrees
	# - Vectors (vertices, tex coords, normals) and faces need to be put into the correct format

	blocks: list[TPM_Raw.Block] = []
	
	# FileInfo
	fileInfoProperties: TPM_Raw.PropertyList = []
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
		materialProperties: TPM_Raw.PropertyList = []
		if mat.colourmap:
			materialProperties.append(["colormap", EncloseInQuotes(mat.colourmap)])
		if mat.bumpmap:
			materialProperties.append(["bumpmap", EncloseInQuotes(mat.bumpmap)])
		if mat.opacitymap:
			materialProperties.append(["opacitymap", EncloseInQuotes(mat.opacitymap)])
		blocks.append(TPM_Raw.Block("material", EncloseInQuotes(mat.name), materialProperties))
	
	# Meshes
	for mesh in tpm.meshes:
		meshProperties: TPM_Raw.PropertyList = []
		# Materials
		for materialName in mesh.materialNames:
			meshProperties.append(["m", EncloseInQuotes(materialName)])
		# Vertices
		if isinstance(mesh, TPM.Skin):
			if len(mesh.vertices) != len(mesh.vertexBoneIndices):
				raise TPMException(f"Attempting to export skin '{mesh.name}', but the vertex count ({len(mesh.vertices)}) does not match the bone indices count ({len(mesh.vertexBoneIndices)})")
			for vertex, boneIndex in zip(mesh.vertices, mesh.vertexBoneIndices):
				meshProperties.append(["v", f"({vertex[0]},{vertex[1]},{vertex[2]}),{boneIndex}"])
		else:
			for vertex in mesh.vertices:
				meshProperties.append(["v", f"({vertex[0]},{vertex[1]},{vertex[2]})"])
		# Texture coordinates
		for texCoord in mesh.textureCoords:
			meshProperties.append(["t", f"({texCoord[0]},{texCoord[1]})"])
		# Normals
		for normal in mesh.normals:
			meshProperties.append(["n", f"({normal[0]},{normal[1]},{normal[2]})"])
		# Faces
		for face in mesh.faces:
			v = face.vertexIndices
			t = face.texCoordIndices
			n = face.normalIndices
			m = face.materialIndex
			meshProperties.append(["f", f"({v[0]},{v[1]},{v[2]}),({t[0]},{t[1]},{t[2]}),({n[0]},{n[1]},{n[2]}),{m}"])
		blocks.append(TPM_Raw.Block("skin" if isinstance(mesh, TPM.Skin) else "mesh", EncloseInQuotes(mesh.name), meshProperties))
	
	# Instances
	for instance in tpm.instances:
		p = instance.position
		r = ToDegrees(instance.rotation)
		s = instance.scale
		instanceProperties: TPM_Raw.PropertyList = []
		instanceProperties.append(["mesh", EncloseInQuotes(instance.mesh)])
		instanceProperties.append(["position", f"({p[0]},{p[1]},{p[2]})"])
		instanceProperties.append(["rotation", f"({r[0]},{r[1]},{r[2]})"])
		instanceProperties.append(["scale", f"{s}"])
		blocks.append(TPM_Raw.Block("instance", EncloseInQuotes(instance.name), instanceProperties))
	
	# Bones
	for bone in tpm.bones:
		p = bone.position
		r = ToDegrees(bone.rotation)
		boneProperties: TPM_Raw.PropertyList = []
		boneProperties.append(["position", f"({p[0]},{p[1]},{p[2]})"])
		boneProperties.append(["rotation", f"({r[0]},{r[1]},{r[2]})"])
		blocks.append(TPM_Raw.Block("bone", EncloseInQuotes(bone.name), boneProperties))

	return TPM_Raw(blocks)

# ----------------------------------------------------------------
def TPMRawToLines(tpmRaw: TPM_Raw) -> list[str]:
	lines: list[str] = []
	for block in tpmRaw.blocks:
		identifierLine = f"{block.type}"
		if block.identifier:
			identifierLine = f"{identifierLine} {block.identifier}"
		lines.append(identifierLine)
		lines.append("{")
		for p in block.properties:
			lines.append(f"\t{p[0]} = {p[1]}")
		lines.append("}")
		lines.append("")
	return lines

# ----------------------------------------------------------------
def TPMRawToString(tpmRaw: TPM_Raw) -> str:
	return "\n".join(TPMRawToLines(tpmRaw))