# DestructiveClip
An Inkscape Extension which works like Object|Clip|Set except that the paths clipped are actually **modified**.

Thus the clipping is included when exported, for example as a DXF file.
Select two or more **paths** then choose Extensions|Modify path|Destructive clip.  The topmost path will be used to clip the others.

Notes:-
* Curves in paths are not supported (use Flatten Beziers).
* Non-path objects in the selection will be ignored.  Use Object|Ungroup.
* Paths entirely outside the clipping path will remain untouched (rather than modifying them to an empty path)
* Complex paths may take a while (there seems to be no way too show progress)
* Yes, using MBR's to do gross clipping might make it faster
* No, Python is not my first language (C/C++ is)
    
Mark Wilson Feb 2016

# To install
Copy destructiveclip.py & destructiveclip.inx into Inkscape\share\extensions where-ever Inkscape is installed (eg Program Files).
Start Inkscape.  "Destructive Clip" should now be available under the Extensions menu, in the Modify Path submenu.

# Example
clipped.png shows the rectangular blue path clipping the tiled "dovetail" red path.  The red path has been *modified*

