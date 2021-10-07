# -*- coding: utf-8 -*-
import itertools
from Autodesk.Revit.DB import BuiltInCategory, FilteredElementCollector, GeometryInstance, \
				Line, Options, PlanarFace, Plane, ReferenceArray, SketchPlane, Solid
from pyrevit import revit

def getSolidsFromElement(element, options=None):
	'''Tries to get solids from element, will not return solids with no volume'''
	if options == None:
		options = Options()
	solids = []
	try:
		geos = element.get_Geometry(options)
		for geo in geos:
			if type(geo) == Solid and geo.Volume > 0:
				solids.Add(geo)
			if type(geo) == GeometryInstance:
				instanceGeos = geo.GetInstanceGeometry()
				for igeo in instanceGeos:
					if type(igeo) == Solid and igeo.Volume > 0:
						solids.append(igeo)
	except:
		pass
	return solids

def getPlanarFaceParallellToViewFromSolids(solids, view):
	'''Find faces where the solids' face's normal vector is perpendicular to the \
	view direction. Also checks if similar faces are found pointing in opposite \
	directions.'''
	viewDirection = view.ViewDirection
	faces = []
	for solid in solids:
		solidCenter = solid.ComputeCentroid()
		faceIt = solid.Faces.ForwardIterator()
		while faceIt.MoveNext():
			if isinstance(faceIt.Current, PlanarFace):
				# calculate dot product of the view direction to the face direction. if this
				# is almost zero, the faces are almost perpendicular. 
				dp = viewDirection.DotProduct(faceIt.Current.FaceNormal)
				# calculate a normalized vector from the center of the solid to the origin of the face
				centerToFaceDirectionVector = solidCenter.Subtract(faceIt.Current.Origin).Normalize()
				# the dot product of this direction vector and the face direction will be less than
				# zero if the face is pointing towards centroid
				insideCheck = centerToFaceDirectionVector.DotProduct(faceIt.Current.FaceNormal)
				if abs(dp) < 0.01 and insideCheck < 0:
					hollow = isFaceHollow(faceIt.Current)
					if hollow is not None and not hollow:
						faces.append(faceIt.Current)
	return faces

def getStraightEdgesFromPlanarFaces(faces, view):
	'''Returns dictionary with two lists with straight edges. 'XY' for edges which are in the \
	XY-plan of the view, and 'Z' for edges pointing in in the Z-direction.'''
	viewDirection = view.ViewDirection
	edgeDict = {}
	edgeDict['XY'] = []
	edgeDict['Z'] = []
	if len(faces) > 0:
		for face in faces:
			# create a temporary list for the XY-edges
			tempXY = []
			edgeArrayArray = face.EdgeLoops
			for edgeArray in edgeArrayArray:
				for edge in edgeArray:
					edgeCurve = edge.AsCurve()
					if isinstance(edgeCurve, Line):
						# calculate the dot product of the view direction and edge direction
						dp = edgeCurve.Direction.DotProduct(viewDirection)
						# if the result is around -1 or 1, the direction is similar or opposite
						# these will be our references. calculate closest point from view origin
						if abs(dp) > 0.99:
							referenceEdgeDict = {}
							p1 = edgeCurve.GetEndPoint(0)
							p2 = edgeCurve.GetEndPoint(1)
							closestPoint = min([p1, p2], key=lambda p:\
								p.DistanceTo(view.Origin))
							# this should not matter, but I append the same index for the
							# reference as the closes point, I do not know if these actually match
							if closestPoint == p1:
								referenceEdgeDict['ref'] = edge.GetEndPointReference(0)
							else:
								referenceEdgeDict['ref'] = edge.GetEndPointReference(1)
							referenceEdgeDict['p'] = closestPoint
							referenceEdgeDict['edge'] = edge
							edgeDict['Z'].append(referenceEdgeDict)
						# if the result is around 0, the directions are perpendicular to each other
						if abs(dp) < 0.01:
							tempXY.append(edge)
			# filter which selects the one closest to the view (a bit ugly)
			if len(tempXY) > 1:
				closestEdgeToView = min(tempXY, key=lambda e: \
								e.AsCurve().GetEndPoint(0).DistanceTo(view.Origin))
				edgeDict['XY'].append(closestEdgeToView)
			else:
				edgeDict['XY'].extend(tempXY)
	return edgeDict

def isFaceHollow(face):
	'''Returns True if face is hollow. The faces has curveloops. If the face contains curveloops \
	which are counterclockwise AND not counterclockwise with respect to the face's normal vector, \
	the face is hollow.'''
	if isinstance(face, PlanarFace):
		tests = []
		curveLoops = face.GetEdgesAsCurveLoops()
		for cl in curveLoops:
			ccw = cl.IsCounterclockwise(face.FaceNormal)
			tests.append(ccw)
		if False in tests and True in tests:
			return True
		else:
			return False
	return

def getOppositeFaces(faces):
	'''Returns the two faces that points in opposite direction. \
	Using itertools to ensure to not check the face against the same face'''
	faceCombination = itertools.combinations(faces, 2)
	for f1,f2 in faceCombination:
		if isinstance(f1, PlanarFace) and isinstance(f2, PlanarFace):
			directionCheck = f1.FaceNormal.DotProduct(f2.FaceNormal)
			if abs(directionCheck) > 0.99:
				return [f1, f2]
	return

def getAdditionalReferences(dimensionEdge, referenceEdgeDicts):
	'''Returns the reference(s) which has a point equal distance to the dimension edgeline and
	dimension edgeline endpoint.'''
	refs = []
	line = dimensionEdge.AsCurve()
	lineEndPoint1 = line.GetEndPoint(0)
	lineEndPoint2 = line.GetEndPoint(1)
	lineEndPoints = [lineEndPoint1, lineEndPoint2]
	for lineEndPoint in lineEndPoints:
		for edgeDict in referenceEdgeDicts:
			p = edgeDict['p']
			distToEndPoint = p.DistanceTo(lineEndPoint)
			distToLine = line.Distance(p)
			# distance between the line endpoints and the reference points has to be larger
			# than 0.
			if distToEndPoint > 0.1 and abs(distToLine - distToEndPoint) < 0.01:
				# angle between line to endpoint and dimension line must not be 90 degrees
				# create a normalized vector from point to line endpoint
				normVectorToEndpoint = lineEndPoint.Subtract(p).Normalize()
				# calculating the dot product which will be close to zero if 90 degrees
				dotProductPointToLine = line.Direction.DotProduct(normVectorToEndpoint)
				if abs(dotProductPointToLine) > 0.01:
					refs.append(edgeDict['ref'])
	return refs

def createDimension(dimensionEdges, zEdgeDicts, view):
	for dimensionEdge in dimensionEdges:
		edgeLine = dimensionEdge.AsCurve()
		ra = ReferenceArray()
		ref1 = dimensionEdge.GetEndPointReference(0)
		ref2 = dimensionEdge.GetEndPointReference(1)
		ra.Append(ref1); ra.Append(ref2)
		ref3 = getAdditionalReferences(dimensionEdge, zEdgeDicts)
		if len(ref3) > 0:
			map(ra.Append, ref3)
		view.Document.Create.NewDimension(view, edgeLine, ra)

def drawModelLineFromEdge(edge):
	# edge is between two faces, the face needs to be planar if to be used for the sketchplane
	faces = [edge.GetFace(0), edge.GetFace(1)]
	for face in faces:
		if isinstance(face, PlanarFace):
			plane = Plane.CreateByNormalAndOrigin(face.FaceNormal, face.Origin)
			sp = SketchPlane.Create(revit.doc, plane)
			edgeCurve = edge.AsCurve()
			revit.doc.Create.NewModelCurve(edgeCurve, sp)

def drawModelLinesFromEdgesOnFace(face):
	if isinstance(face, PlanarFace):
		plane = Plane.CreateByNormalAndOrigin(face.FaceNormal, face.Origin)
		sp = SketchPlane.Create(revit.doc, plane)
		edgeArrayArray = face.EdgeLoops
		for edgeArray in edgeArrayArray:
			for edge in edgeArray:
				edgeCurve = edge.AsCurve()
				revit.doc.Create.NewModelCurve(edgeCurve, sp)

# the currently active view in Revit
av = revit.uidoc.ActiveView

# collect structural framing elements in view
beams = FilteredElementCollector(revit.doc, av.Id). \
				OfCategory(BuiltInCategory.OST_StructuralFraming)

# set up geometry options to calculate references in active view
o = Options()
o.ComputeReferences = True
o.View = av

with revit.Transaction('Dimension beams in view.'):
	for beam in beams:
		solids = getSolidsFromElement(beam, options=o)
		faces = getPlanarFaceParallellToViewFromSolids(solids, av)
		# possibliy, the face list could be empty
		if len(faces) > 0:
			oppositeFaces = getOppositeFaces(faces)
			edges = getStraightEdgesFromPlanarFaces(oppositeFaces, av)
			createDimension(edges['XY'], edges['Z'], av)