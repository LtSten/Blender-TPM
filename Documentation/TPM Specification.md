# Introduction
What follows is the documentation of the TPM format as implemented by this plugin. This is based extremely closely on the original [TPM documentation](https://www.trescom.org/files/docs/formats.html#TPM), adjusted for how TPM files appear to have been implemented in practice (e.g. in TresEd). Any differences or deviations are clearly marked. This is generally _specification by example_ for use in implementation, rather than a rigorous, formal syntax definition. Implementations are recommended to make as few assumptions as practical for import, and be as restrictive as possible on export.

# File Format
TPM files are text-based file formats used to store geometry for import to or export from Trespasser levels. It is similar to the [.obj model format](https://en.wikipedia.org/wiki/Wavefront_.obj_file). These are generally expected to be ASCII encoded - this is heavily recommended for maximum portability between legacy utilities. Whitespace is partially significant:
* The TPM format uses new lines to break up statements
* Within a single line, all remaining whitespace is only relevant for separating tokens

The fundamental segmentation of a TPM file is that of per-line. The input should be split into lines, and each line processed as follows:

1. Leading and trailing whitespace should be trimmed
1. Lines beginning with `//` should be discarded
1. Empty lines should be discarded

Note in particular that this provides _partial_ comment support: comments may only appear on lines by themselves, so `//` cannot be used to append a comment to an existing line:
| Valid | Invalid |
| --- | --- |
| `// TPM comment` | `{ // Start a block` |

Processing proceeds line-by-line, in groups of lines. Within each line, there are two basic token types:
* `identifier`, which is a `C/C++/Python`-style identifier consisting of a sequence of alphanumeric characters or underscores
* `string`, a sequence of non-line break ASCII characters initiated and terminated by the double quote mark character `"` (ASCII 34) . There is no escape character.

For specification purposes, all whitespace not contained by a `string` should be replaced with a single space character (ASCII 32). In practice, this means all per-line whitespace should be skipped over in contiguous blocks. In what follows, `[token]` means an _optional_ token to be referred to by the ID `token`.

The fundamental unit of the TPM format is that of the TPM block. At the top level, define a TPM by
```
block-list
```
where `block-list` is a sequence of `block` elements of the following form

```
block-type [block-name]
{
property-list
}
```
where
| Token | Definition | Notes |
| --- | --- | --- |
| `block-type` | `identifier` | |
| `block-name` | `string` | Optional |
| `property-list` | A newline-separated list of `property` | May be empty |
with `property` defined as
```
key = value
```
where
| Token | Definition | Notes |
| --- | --- | --- |
| `key` | `identifier` | There may be multiple entries for the same `key`. Their relative order must be preserved. |
| `value` | Per `key` | These should initially be parsed independently of `key` by taking everything after the `=` up to the end of the line, discarding leading or trailing whitespace |

## Example
```
BlockType "Block ID 0"
{
	PropertyA = "X Y Z"
	PropertyB = +2.99E8
	PropertyC = (1, A), (2, B)
	PropertyD = " string with = and whitespace "
}

BlockTypeNoName
{
	PropertyA = "A B C"
}
```

# TPM Block Specifications
Each block contains data in its `property-list` as identified by its `block-type`. A `block-name` may or may not be required or supported. Example blocks are given for each type. There are a few common helper types that it is useful to define in order to specify property types:
| Type | Definition | Example | Notes |
| --- | --- | --- | --- |
| `vec2` | `(float,float)` | `(0.31415,0.27818)` | A vector of two floating-point numbers. The recommended formatting specifier is `(%f,%f)`. |
| `vec3` | `(float,float,float)` | `(0.00585938,-0.51088,0.0339626)` | A vector of three floating-point numbers. The recommended formatting specifier is `(%f,%f,%f)`. |
| `ivec3` | `(int,int,int)` | `(3,1,4)` | A vector of three decimal integers. The recommended formatting specifier is `(%d,%d,%d)`. |

<!------------------------------------------------------------------------------>
## FileInfo
FileInfo blocks contain metadata about the current TPM file.

### Block Specification
| ID | Value |
| --- | --- |
| `block-type` | `fileinfo` |
| `block-name` | Not allowed |

### Properties
| Property | Value or Type | Optional | Unique | Description |
| --- | --- | --- | --- | --- |
| `formatversion` | `major.minor.revision` | Required | Unique | A dot-separated list of three integers specifying the TPM format of the file. |
| `name` | `string` | Optional | Unique | Used to identify the contents of the file. |
| `version` | `major.minor.revision` | Optional | Unique | The version of the contents of the file. |
| `source` | `string` | Optional | Unique | Source of the file. |
| `date` | `m/d/y h:m:s XX` | Optional | Unique | Timestamp for creation or modification. The recommended ISO-style read/write format specifier is `%m/%d/%Y %I:%M:%S %p` (see e.g. [`std::format`](https://en.cppreference.com/w/cpp/chrono/duration/formatter)) |
| `comments` | `string` | Optional | Unique | Additional comments. |

### Example
```
fileinfo
{
 formatversion = 1.0.1
 name = "NewRaptor.max"
 version = 0.1.3
 source = "NewRaptor.max"
 date = 7/2/2007 6:03:23 PM
 comments = "unfinished yet"
}
```

<!------------------------------------------------------------------------------>
## Instance
Instances are used to populate the scene by defining transformations of object instances using a particular mesh.

### Block Specification
| ID | Value |
| --- | --- |
| `block-type` | `instance` |
| `block-name` | The name of the instance |

### Properties
| Property | Value or Type | Optional | Unique | Description |
| --- | --- | --- | --- | --- |
| `mesh` | `string` | Required | Unique | The identifier of the mesh to use for this instance |
| `position` | `vec3` | Required | Unique | The XYZ position of the instance |
| `rotation` | `vec3` | Required | Unique | The Euler angles (XYZ), in degrees, specifying the orientation of the instance. Trespasser rotates first around X, then Y, then Z. |
| `scale` | `float` | Required | Unique | The scale to apply to the mesh |

### Example
```
instance "RaptorB"
{
 mesh = "RaptorB"
 position = (0.00585938,-0.51088,0.0339626)
 rotation = (30,45,90)
 scale = 3.05637
}
```

<!------------------------------------------------------------------------------>
## Material

### Block Specification
| ID | Value |
| --- | --- |
| `block-type` | `material` |
| `block-name` | The name of the material |

### Properties
| Property | Value or Type | Optional | Unique | Description |
| --- | --- | --- | --- | --- |
| `colormap` | `string` | Optional | Unique | File path of the colour map |
| `bumpmap` | `string` | Optional | Unique | File path of the bump map |
| `opacitymap` | `string` | Optional | Unique | File path of the opacity map | 

### Example
```
material "RaptorB.mat10"
{
 colormap = "Map\lab\Araptor10t2.bmp"
 bumpmap = "Map\lab\Araptor10b8.bmp"
 opacitymap = "Map\lab\Araptor10o8.bmp"
}
```

<!------------------------------------------------------------------------------>
## Mesh
Note that each property forms an array of the corresponding type (e.g. vertices) that must be indexed in the order that they appear in the file.

### Block Specification
| ID | Value |
| --- | --- |
| `block-type` | `mesh` |
| `block-name` | The name of the mesh |

### Properties
| Property | Value or Type | Optional | Unique | Description |
| --- | --- | --- | --- | --- |
| `m` | `string` | Required | Multiple | The name of the material defined elsewhere in the file |
| `v` | `vec3` | Required | Multiple | A vertex position definition |
| `n` | `vec3` | Required | Multiple | A normal definition. These should be normalised. |
| `t` | `vec2` | Required | Multiple | A texture coordinate (UV) definition |
| `f` | `ivec3,ivec3,ivec3,int` | Required | Multiple | A face definition. Each face is triangular (consisting of three vertices), where the elements define the indices of the vertices, texture coordinates, normals, and material respectively, i.e. of the form `(v1,v2,v3),(t1,t2,t3),(n1,n2,n3),m`. Note that all of these indices are one-based.

### Example
```
mesh "Plane01"
{
 m = "wood04"
 m = "stone03"
 v = (-1.0,-0.5,0.0)
 v = (1.0,-0.5,0.0)
 v = (-1.0,0.5,0.0)
 v = (1.0,0.5,0.0)
 t = (0.0,0.0)
 t = (1.0,0.0)
 t = (0.0,1.0)
 t = (1.0,1.0)
 n = (0.0,0.0,1.0)
 f = (3,1,4),(3,1,4),(1,1,1),2
 f = (2,4,1),(2,4,1),(1,1,1),1
}
```

<!------------------------------------------------------------------------------>
## Bone
Note that bones must be implicitly linked with skin vertices by being named in the format `$J{MeshName}{BoneIndex}`.

### Block Specification
| ID | Value |
| --- | --- |
| `block-type` | `bone` |
| `block-name` | The name of the bone |

### Properties
| Property | Value or Type | Optional | Unique | Description |
| --- | --- | --- | --- | --- |
| `position` | `vec3` | Required | Unique | The position of the bone |
| `rotation` | `vec3` | Required | Unique | The Euler angles (XYZ), in degrees, specifying the orientation of the bone. |

### Example
```
bone "$JRaptorB23"
{
 position = (0.002930,1.740082,0.810120)
 rotation = (31.740742,-0.000009,0.000010)
 Anim00 = 7
 Anim01 = 8
 Ratio = 0.500000
 RotationRatio = 0.500000
}
```

<!------------------------------------------------------------------------------>
## Skin

### Block Specification
| ID | Value |
| --- | --- |
| `block-type` | `skin` |
| `block-name` | The name of the skin |

### Properties
All properties of `mesh` blocks, with the following replacements:
| Property | Value or Type | Optional | Unique | Description |
| --- | --- | --- | --- | --- |
| `v` | `vec3,int` | Required | Multiple | A vertex definition, in the form `position,boneIndex`. Note that `0` is a valid bone index, and may bind to the bone `$JMesh00`.

### Example
```
skin "TestSkin"
{
 m = "default"
 v = (-1.0,-0.5,0.0),1
 v = (1.0,-0.5,0.0),1
 v = (-1.0,0.5,0.0),3
 v = (1.0,0.5,0.0),2
 t = (0.0,0.0)
 t = (1.0,0.0)
 t = (0.0,1.0)
 t = (1.0,1.0)
 n = (0.0,0.0,1.0)
 f = (3,1,4),(3,1,4),(1,1,1),1
 f = (2,4,1),(2,4,1),(1,1,1),1
}
```