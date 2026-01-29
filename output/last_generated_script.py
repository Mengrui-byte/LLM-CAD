# Palm parameters
palm_width = 40
palm_depth = 25
palm_height = 15

# Palm base shape
with BuildPart() as palm_part:
    with BuildSketch(Plane.XY):
        Rectangle(palm_width, palm_depth)
    extrude(amount=palm_height)

# Finger parameters
finger_radius = 4
finger_length = 50
finger_spacing = 8

# Thumb parameters
thumb_radius = 4.5
thumb_length = 45
thumb_angle = 30  # degrees

# Create fingers (index to pinky)
fingers = []
for i in range(4):
    x_offset = -palm_width/2 + finger_spacing + i * finger_spacing
    with BuildPart() as finger:
        with BuildSketch(Plane.XY.offset(palm_height)):
            Circle(radius=finger_radius)
        with BuildSketch(Plane.XY.offset(palm_height + finger_length)):
            Circle(radius=finger_radius * 0.8)
        loft()
    fingers.append(Location((x_offset, 0, 0)) * finger.part)

# Create thumb
with BuildPart() as thumb_part:
    with BuildSketch(Plane.XY.offset(palm_height)):
        Circle(radius=thumb_radius)
    with BuildSketch(Plane.XY.offset(palm_height + thumb_length)):
        Circle(radius=thumb_radius * 0.8)
    loft()

# Position thumb at an angle
thumb_location = Location((-palm_width/2 + 5, -palm_depth/2 + 5, 0)) * Rotation(0, 0, thumb_angle)
thumb = thumb_location * thumb_part.part

# Combine all parts
hand_parts = [palm_part.part] + fingers + [thumb]
compound = Compound(children=hand_parts)

try:
    if 'export_stl' in dir():
        export_stl(compound, 'output/model.stl')
    else:
        compound.export_stl('output/model.stl')
except Exception as e:
    print(f'Export failed: {e}')
    try:
        if 'export_step' in dir():
            export_step(compound, 'output/model.step')
        else:
            compound.export_step('output/model.step')
    except Exception as e2:
        print(f'STEP export failed: {e2}')