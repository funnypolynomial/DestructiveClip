#!/usr/bin/env python 
'''
  ---DESTRUCTIVE Clip---
  An Inkscape Extension which works like Object|Clip|Set except that the paths clipped are actually *modified*
  Thus the clipping is included when exported, for example as a DXF file.
  Select two or more *paths* then choose Extensions|Modify path|Destructive clip.  The topmost path will be used to clip the others.
  Notes:-
    * Curves in paths are not supported (use Flatten Beziers).
    * Non-path objects in the selection will be ignored.  Use Object|Ungroup.
    * Paths entirely outside the clipping path will remain untouched (rather than modifying them to an empty path)
    * Complex paths may take a while (there seems to be no way too show progress)
    * Yes, using MBR's to do gross clipping might make it faster
    * No, Python is not my first language (C/C++ is)
    
  Mark Wilson Feb 2016
'''
import inkex, simplepath

class MyEffect(inkex.Effect):
  def __init__(self):
    self.tolerance = 0.0001  # arbitrary fudge factor 
    inkex.Effect.__init__(self)

  def approxEqual(self, a, b): 
    # compare with tiny tolerance
    return abs(a-b) <= self.tolerance

  def midPoint(self, line): 
    # midPoint of line
    return [(line[0][0] + line[1][0])/2, (line[0][1] + line[1][1])/2]
  
  def maxX(self, lineSegments):
    # return max X coord of lineSegments
    maxx = 0.0
    for line in lineSegments:
      maxx = max(maxx, line[0][0])
      maxx = max(maxx, line[1][0])
    return maxx
    
  def simplepathToLineSegments(self, path):
    # takes a simplepath and converts to line *segments*, for simplicity.
    # Thus [MoveTo P0, LineTo P1, LineTo P2] becomes [[P0-P1],[P1,P2]]
    # only handles, Move, Line and Close.  
    # The simplepath library has already simplified things, normalized relative commands, etc
    lineSegments = first = prev = this = []
    errors = set([])  # Similar errors will be stored only once
    for cmd in path:
      this = cmd[1]
      if cmd[0] == 'M': # moveto
        if first == []:
          first = this
      elif cmd[0] == 'L': # lineto
        lineSegments.append([prev, this])
      elif cmd[0] == 'Z': # close
        lineSegments.append([prev, first])
        first = []
      elif cmd[0] == 'C':
        # https://developer.mozilla.org/en/docs/Web/SVG/Tutorial/Paths
        lineSegments.append([prev, [this[4], this[5]]])
        errors.add("Curve node detected (svg type C), this node will be handled as a regular node")
      else:
        errors.add("Invalid node type detected: {}. This script only handle type M, L, Z".format(cmd[0]))
      prev = this
    return (lineSegments, errors)

  def linesgmentsToSimplePath(self, lineSegments):
    # reverses simplepathToLines - converts line segments to Move/Line-to's
    path = []
    end = None
    for line in lineSegments:
      start = line[0]
      if end is None:
        path.append(['M', start]) # start with a move
      elif not (self.approxEqual(end[0], start[0]) and self.approxEqual(end[1], start[1])):
        path.append(['M', start]) # only move if previous end not within tolerance of this start
      end = line[1]
      path.append(['L', end])
    return path
    
  def lineIntersection(self, L1From, L1To, L2From, L2To):
    # returns as [x, y] the intersection of the line L1From-L1To and L2From-L2To, or None
    # http://stackoverflow.com/questions/563198/how-do-you-detect-where-two-line-segments-intersect 
    dL1 = [L1To[0] - L1From[0], L1To[1] - L1From[1]]
    dL2 = [L2To[0] - L2From[0], L2To[1] - L2From[1]]
    denominator = -dL2[0]*dL1[1] + dL1[0]*dL2[1]
    if not self.approxEqual(denominator, 0.0):
      s = (-dL1[1]*(L1From[0] - L2From[0]) + dL1[0]*(L1From[1] - L2From[1]))/denominator
      t = (+dL2[0]*(L1From[1] - L2From[1]) - dL2[1]*(L1From[0] - L2From[0]))/denominator
      if s >= 0.0 and s <= 1.0 and t >= 0.0 and t <= 1.0:
        return [L1From[0] + (t * dL1[0]), L1From[1] + (t * dL1[1])]
    else:
      return None

  def insideRegion(self, point, lineSegments, lineSegmentsMaxX):
    # returns true if point is inside the region defined by lineSegments.  lineSegmentsMaxX is the maximum X extent
    ray = [point, [lineSegmentsMaxX*2.0, point[1]]]  # hz line to right of point, extending well outside MBR
    crossings = 0
    for line in lineSegments:
      if not self.lineIntersection(line[0], line[1], ray[0], ray[1]) is None:
        crossings += 1
    return (crossings % 2) == 1  # odd number of crossings means inside

  def cullSegmentedLine(self, segmentedLine, lineSegments, lineSegmentsMaxX):
    # returns just the segments in segmentedLine which are inside lineSegments
    culled = []
    for segment in segmentedLine:
      if self.insideRegion(self.midPoint(segment), lineSegments, lineSegmentsMaxX):
        culled.append(segment)
    return culled
      
  def clipLine(self, line, lineSegments):
    # returns line split where-ever lines in lineSegments cross it
    linesWrite = [line]
    for segment in lineSegments:
      linesRead = linesWrite
      linesWrite = []
      for line in linesRead:
        intersect = self.lineIntersection(line[0], line[1], segment[0], segment[1])
        if intersect is None:
          linesWrite.append(line)
        else: # split
          linesWrite.append([line[0], intersect])
          linesWrite.append([intersect, line[1]])
    return linesWrite
    
  def clipLineSegments(self, lineSegmentsToClip, clippingLineSegments):
    # return the lines in lineSegmentsToClip clipped by the lines in clippingLineSegments
    clippedLines = []
    for lineToClip in lineSegmentsToClip:
      clippedLines.extend(self.cullSegmentedLine(self.clipLine(lineToClip, clippingLineSegments), clippingLineSegments, self.maxX(clippingLineSegments)))
    return clippedLines
  
  def effect(self):
    clippingLineSegments = None
    pathTag = inkex.addNS('path','svg')
    groupTag = inkex.addNS('g','svg')
    error_messages = []
    for id in self.options.ids:  # the selection, top-down
      node = self.selected[id]
      if node.tag == pathTag:
        if clippingLineSegments is None: # first path is the clipper
          (clippingLineSegments, errors) = self.simplepathToLineSegments(simplepath.parsePath(node.get('d')))
          error_messages.extend(['{}: {}'.format(id, err) for err in errors])
        else:
          # do all the work!
          segmentsToClip, errors = self.simplepathToLineSegments(simplepath.parsePath(node.get('d')))
          error_messages.extend(['{}: {}'.format(id, err) for err in errors])
          clippedSegments = self.clipLineSegments(segmentsToClip, clippingLineSegments)
          if len(clippedSegments) != 0:
            # replace the path
            node.set('d', simplepath.formatPath(self.linesgmentsToSimplePath(clippedSegments)))
          else:
            # don't put back an empty path(?)  could perhaps put move, move?
            inkex.debug('Object {} clipped to nothing, will not be updated.'.format(node.get('id')))
      elif node.tag == groupTag:  # we don't look inside groups for paths
        inkex.debug('Group object {} will be ignored. Please ungroup before running the script.'.format(id))
      else: # something else
        inkex.debug('Object {} is not of type path ({}), and will be ignored. Current type "{}".'.format(id, pathTag, node.tag))

    for error in error_messages:
        inkex.debug(error)


      
if __name__ == '__main__':
    e = MyEffect()
    e.affect()
