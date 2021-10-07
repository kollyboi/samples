## Thinking process
I'm using the [pyRevit](https://github.com/eirannejad/pyRevit) framework to run the code in Revit. For the [PEP-8](https://www.python.org/dev/peps/pep-0008/) police, I acknowledge that I do not follow these rules. I use camelCase for variables and functions similar to the Java naming convention. This is an attempt to marry the Revit API naming conventions and still use lower case naming for functions. I know, it's not ideal and probably horrible to look at, but let's try to tolerate this and focus on the case.\
One of my colleagues wants to dimension all the beams in each section view like this. This is the beam that we will work with to test the code:\
<img src="img\wantedresult.png" width="600"/>\
To do this in Revit, you have to press TAB six times to cycle to the endpoint of the face's edge.
Six times six plus two clicks for activating the dimension tool, 38 clicks per beam. There are a lot of beams.\
One section:\
<img src="img\allbeamsinonesection.png" width="900"/>\
All the beams in a 3D-view:\
<img src="img\allbeams3d.png" width="900"/>\
Let's take a look at the [method](https://www.revitapidocs.com/2021.1/47b3977d-da93-e1a4-8bfa-f23a29e5c4c1.htm) in the Revit API to create a dimension:\
>NewDimension Method (View, Line, ReferenceArray)

We need a view, a line and an array of references. Let's focus on the references for now. We have to:
1. Get the beams in the view   
2. Get the solids from the beams[^1]
3. Get the faces from the solids[^2]
4. Get the edges from the faces[^3]
5. Separate the edges which points in the
   -  same or opposite direction as the view direction (these will contain the endpoint references)
   -  XY-plane of the view (these are the edges that points in the dimension direction)
6. Figure out a logic that picks the correct edges and pick the endpoint reference for the new dimension.

The beam in 3D:\
<img src="img\beamIsolated3D.png" width="600"/>\
Step 1-3. After the faces are collected, I'm using a function[^4] to draw them.
```python
# the currently active view in Revit
av = revit.uidoc.ActiveView

# collect structural framing elements in view
beams = FilteredElementCollector(revit.doc, av.Id). \
				OfCategory(BuiltInCategory.OST_StructuralFraming)

# set up geometry options to calculate references in active view
o = Options()
o.ComputeReferences = True
o.View = av

# step-by-step inside a transaction
with revit.Transaction('Dimension beams in view.'):
	for beam in beams:
		solids = getSolidsFromElement(beam, options=o)
		faces = getPlanarFaceParallellToViewFromSolids(solids, av)
		map(drawModelLinesFromEdgesOnFace, faces)
```
The faces we have so far:\
<img src="img\faces.png" width="900"/>\
As we can see, we have collected:
- the top faces
- the outer faces which points away from the solid center
- not the inner faces

We don't really need the top faces, but how can we take them out? One way would be to take the faces with the larges area, but that's not very elegant I think. I want to separate them because there's a hole in the face. Let's create a function to do this[^5] and implement this in the `getPlanarFaceParallellToViewFromSolids`-function. Then I'll use another function[^6] to draw the XY and the Z-lines.\
<img src="img\afterhollowfilter.png" width="900"/>\
There's an annoying small face due to a badly cut beam present. Let's look at a close-up:\
<img src="img\topFace.png" width="900"/>\
<img src="img\smallface.png" width="900"/>\
I should pick the two faces that points in opposite direction. I'm creating another function[^7]. Now we are very close, but I need to implement some sort of logic to which points I want for each line. For L1, I want P1, P3 and P4 and for L2 I want P1, P2 and P4.\
<img src="img\afterfacedirectionfilter.png" width="500"/>\
For the logic of which endpoints to use, I have a plan:\
<img src="img\selectpoints.png" width="1000"/>\
The distance P2->Px is the shortest distance between the point and the line. This distance will not be equal to the distance between P1 to P2. But for P3 and P4, the situation is different. There, the distance will be equal. Also the angle `<`P1,P3,P4 needs to not be 90 degrees.\
We need some new functions:
- A function to get the other references[^8]
- A function to create the dimensions[^9]

Now we can set it all together and run. The dimensions are now placed on top of the lines, so the dimensions must be dragged to tidy up the view. This is after som tidying:\
<img src="img\finishedresult.png"/>
## Full code
```python

```
*Kyrre Kolstad*

[^1]:
	```python
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
	```
[^2]:
	```python
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
	```
[^3]:
	```python
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
	```
[^4]:
	```python
	def drawModelLinesFromEdgesOnFace(face):
		if isinstance(face, PlanarFace):
			plane = Plane.CreateByNormalAndOrigin(face.FaceNormal, face.Origin)
			sp = SketchPlane.Create(revit.doc, plane)
			edgeArrayArray = face.EdgeLoops
			for edgeArray in edgeArrayArray:
				for edge in edgeArray:
					edgeCurve = edge.AsCurve()
					revit.doc.Create.NewModelCurve(edgeCurve, sp)
	```
[^5]:
	```python
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
	```
[^6]:
	```python
	def drawModelLineFromEdge(edge):
		# edge is between two faces, the face needs to be planar if to be used for the sketchplane
		faces = [edge.GetFace(0), edge.GetFace(1)]
		for face in faces:
			if isinstance(face, PlanarFace):
				plane = Plane.CreateByNormalAndOrigin(face.FaceNormal, face.Origin)
				sp = SketchPlane.Create(revit.doc, plane)
				edgeCurve = edge.AsCurve()
				revit.doc.Create.NewModelCurve(edgeCurve, sp)
	```

[^7]:
	```python
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
	```
[^8]:
	```python
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
	```

[^9]:
	```python
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
	```
