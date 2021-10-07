## Thinking process
I'm using the [pyRevit](https://github.com/eirannejad/pyRevit) framework to run the code in Revit. For the [PEP-8](https://www.python.org/dev/peps/pep-0008/) police, I acknowledge that I do not follow these rules. I use camelCase for variables and functions similar to the Java naming convention. This is an attempt to marry the Revit API naming conventions and still use lower case naming for functions. I know, it's not ideal and probably horrible to look at, but let's try to tolerate this and focus on the case.\
One of my colleagues wants to dimension all the beams in each section view like this. This is the beam that we will work with to test the code:\
<img src="img\wantedresult.png" width="600"/>\
To add the dimensions for this beam in Revit, you have to press TAB six times to cycle to the endpoint of the face's edge.
Six times six plus two clicks for activating the dimension tool, 38 clicks per beam. There are a lot of beams.\
One section:\
<img src="img\allbeamsinonesection.png" width="900"/>\
All the beams in a 3D-view:\
<img src="img\allbeams3d.png" width="900"/>\
Let's take a look at the [method](https://www.revitapidocs.com/2021.1/47b3977d-da93-e1a4-8bfa-f23a29e5c4c1.htm) in the Revit API to create a dimension:
>NewDimension Method (View, Line, ReferenceArray)

We need a view, a line and an array of references. Let's focus on the references for now. We have to:
1. Get the beams in the view   
2. Get the solids from the beams, `getSolidsFromElement`
3. Get the planar faces from the solids, `getPlanarFaceParallellToViewFromSolids`
4. Get the edges from the faces, `getStraightEdgesFromPlanarFaces`
5. Separate the edges which points in the
   -  same or opposite direction as the view direction (these will contain the endpoint references)
   -  XY-plane of the view (these are the edges that points in the dimension direction)
6. Figure out a logic that picks the correct edges and pick the endpoint reference for the new dimension.

The beam in 3D:\
<img src="img\beamIsolated3D.png" width="600"/>\
Step 1-3. After the faces are collected, I'm drawing the edges in the view.
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

We don't really need the top faces, but how can we take them out? One way would be to take the faces with the larges area, but that's not very elegant I think. I want to separate them because there's a hole in the face. Let's create the function `isFaceHollow` to do this and implement this in the `getPlanarFaceParallellToViewFromSolids`-function. Then I'll draw these lines in the view:\
<img src="img\afterhollowfilter.png" width="900"/>\
There's an annoying small face due to a badly cut beam present. Let's look at a close-up:\
<img src="img\topFace.png" width="900"/>\
<img src="img\smallface.png" width="900"/>\
I should pick the two faces that points in opposite direction. I'm creating another function, `getOppositeFaces` to filter out the unwanted face. Now we are very close, but I need to implement some sort of logic to which points I want for each line. For L1, I want P1, P3 and P4 and for L2 I want P1, P2 and P4.\
<img src="img\afterfacedirectionfilter.png" width="500"/>\
For the logic of which endpoints to use, I have a plan:\
<img src="img\selectpoints.png" width="1000"/>\
The distance P2->Px is the shortest distance between the point and the line. This distance will not be equal to the distance between P1 to P2. But for P3 and P4, the situation is different. There, the distance will be equal. Also the angle `<`P1,P3,P4 needs to not be 90 degrees.\
We need some new functions:
- A function to get the other references, `getAdditionalReferences`
- A function to create the dimensions, `createDimension`

Now we can set it all together and run. The dimensions are now placed on top of the lines, so the dimensions must be dragged to tidy up the view. This is after some tidying:\
<img src="img\finishedresult.png"/>
## [Full code here](addDimensionOnBeams.py)

*Kyrre Kolstad*