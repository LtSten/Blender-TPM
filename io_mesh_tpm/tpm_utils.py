import math
from mathutils import Vector

# ----------------------------------------------------------------
def ConstructJointName(parentName: str, jointIndex: int):
	if not jointIndex in range(100):
		raise ValueError(f"Joint index {jointIndex} is not in the range [0, 99]")
	return f"$J{parentName}{jointIndex:02d}"

# ----------------------------------------------------------------
def ToRadians(v: Vector) -> Vector:
	result = v.copy()
	for i, x in enumerate(v):
		result[i] = math.radians(x)
	return result

# ----------------------------------------------------------------
def ToDegrees(v: Vector) -> Vector:
	result = v.copy()
	for i, x in enumerate(v):
		result[i] = math.degrees(x)
	return result

# ----------------------------------------------------------------
def ChopCharsFromEndsAsymmetrical(s: str, cStart, cEnd) -> tuple[str, bool]:
	if len(s) >= 2 and s[0] in cStart and s[-1] in cEnd:
		return (s[1:-1], True)
	return (s, False)

# ----------------------------------------------------------------
def ChopCharsFromEnds(s: str, chop):
	return ChopCharsFromEndsAsymmetrical(s, chop, chop)

# ----------------------------------------------------------------
def ChopQuotes(s: str):
	return ChopCharsFromEnds(s, '"')

# ----------------------------------------------------------------
def VectorStringToVector(s: str) -> Vector:
	line = s.strip() # Remove leading and trailing whitespace
	line, wasChopped = ChopCharsFromEndsAsymmetrical(line, "(", ")")
	if not wasChopped:
		raise ValueError(f"'{s}' cannot be converted to a vector")
	compStrings = line.split(",")
	components: list[float] = []
	for c in compStrings:
		components.append(float(c))
	return Vector(components)

# ----------------------------------------------------------------
def EncloseInQuotes(s) -> str:
	return f'"{s}"'
