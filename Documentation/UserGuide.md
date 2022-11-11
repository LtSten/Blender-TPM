# User Guide

## Installation
* You should be able to install it as you would any other plugin. If you're having trouble, simply extract the contents of the zip into a new folder named io_mesh_tpm in your Blender addons folder (e.g. `Program Files\Blender Foundation\Blender 3.0\3.0\scripts\addons`). Remember to enable it in the preferences - search for "Trespasser".
* It should appear under "File > Import" and "File > Export" as "Trespasser Model (.tpm)"

## Importing
* The Import dialog conists of a file explorer with some additional options on the right-hand side. Browse to a TPM file you wish to import (only one file at a time is supported, but this may contain multiple models)
* You can hover over the options to display a tooltip explaining what they do.
* By default, textures are expected to be located in the same directory as the TPM. This can be overriden by specifying a path in the "Texture path override" option.
* By default, "Ignore texture directories" is enabled. This means that any prefix in the material's maps (usually of the form "Map\lab", "Map\be", etc) are discarded. Use this if your textures live in the same directory as the TPM.
* "Import to Active Collection" will add the TPM's contents to the current scene collection. Enabling this tickbox will instead create a new collection.
* "Overwrite existing materials" will replace any materials with the same name already located in the .blend file.
* "Bone" and "Skin" blocks are not currently supported. Bone blocks will be skipped entirely on import, whereas skin blocks will be imported as meshes (in particular, vertex bone assignments are _not_ preserved).

## Exporting
* Exporting works with the current selection. You should select the meshes you want to include when performing an export.
* All directory prefixes are stripped from texture names upon export. This is to prevent paths such as "C:/Users/..." etc from being included. Currently, this means it is not possible to export with "Map\mapname" prefixes. If this is required, you should adjust them manually after export.
* Due to Blender not supporting duplicate faces, you must decide how to export alpha faces. These only apply when a material has an alpha node input. The options act as follows:
	* "Forward Only" exports only the forward-facing face
	* "Double Sided" duplicates the front face and flips the winding order
	* "Use Material Backface Culling" examines the "Backface Culling" material option (so occurs on a per-material basis) and writes the back face if and only if this is disabled.

## Use Notes
* Blender does not support duplicate faces, which are sometimes used in Tres models for double-sided alpha faces. These will be silently ignored, since Blender defaults to rendering faces two-sided.
* Any errors should be reported as a tooltip. If you want to view more verbose output, enable the Blender console under "Window > Toggle System Console".
* Materials make use of nodes. It is best to examine the setup of an imported model to see how you should set up your own materials. However, generally you should consider the following:
	* The surface should be of BRDF or BSDF type
	* Each texture input should be an "Image Texture" node
	* The "colormap" image should connect to the base/diffuse colour slot
	* The "bumpmap" should go through a Bump module and be input into the Normal slot
	* The "opacitymap" texture should go into the "Alpha" slot and the material's Blend Mode should be set to Alpha Clip.
* There is no valuetable/tscript support, nor are subobjects linked to their parents.
* Instances are respected - you should use positions, rotations, and scales relative to the underlying mesh.

# Links
* [Installing add-ons](https://docs.blender.org/manual/en/latest/editors/preferences/addons.html#installing-add-ons)
* [Add-on TresCom forum thread](https://www.trescomforum.org/viewtopic.php?f=58&t=11689)