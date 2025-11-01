# Triplanar UV Mapping - EXACT 1:1 copy from Key Ops Toolkit
import bpy
from bpy.types import Operator
from bpy.props import BoolProperty, FloatProperty, StringProperty


def triplanar_uv_mapping_node_group():
    """Create Triplanar UV Mapping node group - EXACT 1:1 copy from Key Ops Toolkit"""
    triplanar_uv_mapping = bpy.data.node_groups.new(type = 'GeometryNodeTree', name = "Triplanar UV Mapping")

    triplanar_uv_mapping.color_tag = 'NONE'
    triplanar_uv_mapping.description = ""

    triplanar_uv_mapping.is_modifier = True

    #triplanar_uv_mapping interface
    #Socket Geometry
    geometry_socket = triplanar_uv_mapping.interface.new_socket(name = "Geometry", in_out='OUTPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket.attribute_domain = 'POINT'

    #Socket Geometry
    geometry_socket_1 = triplanar_uv_mapping.interface.new_socket(name = "Geometry", in_out='INPUT', socket_type = 'NodeSocketGeometry')
    geometry_socket_1.attribute_domain = 'POINT'

    #Socket Selection
    selection_socket = triplanar_uv_mapping.interface.new_socket(name = "Selection", in_out='INPUT', socket_type = 'NodeSocketBool')
    selection_socket.default_value = False
    selection_socket.attribute_domain = 'POINT'
    selection_socket.hide_value = True

    #Socket Name
    name_socket = triplanar_uv_mapping.interface.new_socket(name = "Name", in_out='INPUT', socket_type = 'NodeSocketString')
    name_socket.default_value = ""
    # name_socket.subtype = 'NONE'
    name_socket.attribute_domain = 'POINT'

    #Panel Offset
    offset_panel = triplanar_uv_mapping.interface.new_panel("Offset")
    #Socket World Offset
    world_offset_socket = triplanar_uv_mapping.interface.new_socket(name = "World Offset", in_out='INPUT', socket_type = 'NodeSocketBool', parent = offset_panel)
    world_offset_socket.default_value = False
    world_offset_socket.attribute_domain = 'POINT'

    #Socket Offset Y
    offset_y_socket = triplanar_uv_mapping.interface.new_socket(name = "Offset Y", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = offset_panel)
    offset_y_socket.default_value = 0.5
    offset_y_socket.min_value = -10000.0
    offset_y_socket.max_value = 10000.0
    # offset_y_socket.subtype = 'NONE'
    offset_y_socket.attribute_domain = 'POINT'

    #Socket Offset X
    offset_x_socket = triplanar_uv_mapping.interface.new_socket(name = "Offset X", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = offset_panel)
    offset_x_socket.default_value = 0.5
    offset_x_socket.min_value = -10000.0
    offset_x_socket.max_value = 10000.0
    # offset_x_socket.subtype = 'NONE'
    offset_x_socket.attribute_domain = 'POINT'


    #Panel Scale
    scale_panel = triplanar_uv_mapping.interface.new_panel("Scale")
    #Socket World Scale
    world_scale_socket = triplanar_uv_mapping.interface.new_socket(name = "World Scale", in_out='INPUT', socket_type = 'NodeSocketBool', parent = scale_panel)
    world_scale_socket.default_value = False
    world_scale_socket.attribute_domain = 'POINT'

    #Socket Scale
    scale_socket = triplanar_uv_mapping.interface.new_socket(name = "Scale", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = scale_panel)
    scale_socket.default_value = 0.5
    scale_socket.min_value = 0.0
    scale_socket.max_value = 10000.0
    scale_socket.subtype = 'DISTANCE'
    scale_socket.attribute_domain = 'POINT'


    #Panel Rotation
    rotation_panel = triplanar_uv_mapping.interface.new_panel("Rotation")
    #Socket World Rotation
    world_rotation_socket = triplanar_uv_mapping.interface.new_socket(name = "World Rotation", in_out='INPUT', socket_type = 'NodeSocketBool', parent = rotation_panel)
    world_rotation_socket.default_value = False
    world_rotation_socket.attribute_domain = 'POINT'
    world_rotation_socket.hide_in_modifier = True

    #Socket Angle
    angle_socket = triplanar_uv_mapping.interface.new_socket(name = "Angle", in_out='INPUT', socket_type = 'NodeSocketFloat', parent = rotation_panel)
    angle_socket.default_value = 0.0
    angle_socket.min_value = -360.0
    angle_socket.max_value = 360.0
    angle_socket.subtype = 'ANGLE'
    angle_socket.attribute_domain = 'POINT'



    #initialize triplanar_uv_mapping nodes
    #node Group Input
    group_input = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input.name = "Group Input"
    group_input.outputs[3].hide = True
    group_input.outputs[6].hide = True
    group_input.outputs[7].hide = True
    group_input.outputs[8].hide = True
    group_input.outputs[9].hide = True
    group_input.outputs[10].hide = True

    #node Group Output
    group_output = triplanar_uv_mapping.nodes.new("NodeGroupOutput")
    group_output.name = "Group Output"
    group_output.is_active_output = True
    group_output.inputs[1].hide = True

    #node Store Named Attribute
    store_named_attribute = triplanar_uv_mapping.nodes.new("GeometryNodeStoreNamedAttribute")
    store_named_attribute.name = "Store Named Attribute"
    store_named_attribute.data_type = 'FLOAT2'
    store_named_attribute.domain = 'CORNER'

    #node Combine XYZ
    combine_xyz = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz.name = "Combine XYZ"
    combine_xyz.inputs[2].hide = True
    #Z
    combine_xyz.inputs[2].default_value = 0.0

    #node Vector Rotate.001
    vector_rotate_001 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorRotate")
    vector_rotate_001.name = "Vector Rotate.001"
    vector_rotate_001.invert = False
    vector_rotate_001.rotation_type = 'AXIS_ANGLE'
    vector_rotate_001.inputs[2].hide = True
    vector_rotate_001.inputs[4].hide = True
    #Axis
    vector_rotate_001.inputs[2].default_value = (0.0, 0.0, 1.0)

    #node Separate XYZ.001
    separate_xyz_001 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_001.name = "Separate XYZ.001"

    #node Compare.002
    compare_002 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare_002.name = "Compare.002"
    compare_002.data_type = 'FLOAT'
    compare_002.mode = 'ELEMENT'
    compare_002.operation = 'GREATER_THAN'

    #node Compare.003
    compare_003 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare_003.name = "Compare.003"
    compare_003.data_type = 'FLOAT'
    compare_003.mode = 'ELEMENT'
    compare_003.operation = 'GREATER_THAN'

    #node Position
    position = triplanar_uv_mapping.nodes.new("GeometryNodeInputPosition")
    position.name = "Position"

    #node Vector Math
    vector_math = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math.name = "Vector Math"
    vector_math.operation = 'MULTIPLY'

    #node Switch
    switch = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch.name = "Switch"
    switch.input_type = 'VECTOR'
    #True
    switch.inputs[2].default_value = (1.0, 0.0, 1.0)

    #node Switch.001
    switch_001 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_001.name = "Switch.001"
    switch_001.input_type = 'VECTOR'
    #False
    switch_001.inputs[1].default_value = (1.0, 1.0, 0.0)
    #True
    switch_001.inputs[2].default_value = (0.0, 1.0, 1.0)

    #node Switch.003
    switch_003 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_003.name = "Switch.003"
    switch_003.input_type = 'VECTOR'
    #False
    switch_003.inputs[1].default_value = (0.0, 0.0, 0.0)
    #True
    switch_003.inputs[2].default_value = (0.0, -1.5707999467849731, 0.0)

    #node Switch.002
    switch_002 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_002.name = "Switch.002"
    switch_002.input_type = 'VECTOR'
    #True
    switch_002.inputs[2].default_value = (-1.5707999467849731, 0.0, 0.0)

    #node Normal
    normal = triplanar_uv_mapping.nodes.new("GeometryNodeInputNormal")
    normal.name = "Normal"

    #node Vector Math.001
    vector_math_001 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_001.name = "Vector Math.001"
    vector_math_001.operation = 'ABSOLUTE'

    #node Separate XYZ
    separate_xyz = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz.name = "Separate XYZ"

    #node Compare
    compare = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare.name = "Compare"
    compare.data_type = 'FLOAT'
    compare.mode = 'ELEMENT'
    compare.operation = 'GREATER_THAN'

    #node Compare.001
    compare_001 = triplanar_uv_mapping.nodes.new("FunctionNodeCompare")
    compare_001.name = "Compare.001"
    compare_001.data_type = 'FLOAT'
    compare_001.mode = 'ELEMENT'
    compare_001.operation = 'GREATER_THAN'

    #node Boolean Math
    boolean_math = triplanar_uv_mapping.nodes.new("FunctionNodeBooleanMath")
    boolean_math.name = "Boolean Math"
    boolean_math.operation = 'AND'

    #node Boolean Math.001
    boolean_math_001 = triplanar_uv_mapping.nodes.new("FunctionNodeBooleanMath")
    boolean_math_001.name = "Boolean Math.001"
    boolean_math_001.operation = 'AND'

    #node Vector Rotate
    vector_rotate = triplanar_uv_mapping.nodes.new("ShaderNodeVectorRotate")
    vector_rotate.name = "Vector Rotate"
    vector_rotate.invert = False
    vector_rotate.rotation_type = 'EULER_XYZ'
    #Center
    vector_rotate.inputs[1].default_value = (0.0, 0.0, 0.0)

    #node Vector Math.004
    vector_math_004 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_004.name = "Vector Math.004"
    vector_math_004.operation = 'MULTIPLY'

    #node Object Info.001
    object_info_001 = triplanar_uv_mapping.nodes.new("GeometryNodeObjectInfo")
    object_info_001.name = "Object Info.001"
    object_info_001.transform_space = 'ORIGINAL'
    #As Instance
    object_info_001.inputs[1].default_value = False

    #node Self Object.001
    self_object_001 = triplanar_uv_mapping.nodes.new("GeometryNodeSelfObject")
    self_object_001.name = "Self Object.001"

    #node Group Input.002
    group_input_002 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_002.name = "Group Input.002"
    group_input_002.outputs[0].hide = True
    group_input_002.outputs[1].hide = True
    group_input_002.outputs[2].hide = True
    group_input_002.outputs[3].hide = True
    group_input_002.outputs[4].hide = True
    group_input_002.outputs[5].hide = True
    group_input_002.outputs[7].hide = True
    group_input_002.outputs[8].hide = True
    group_input_002.outputs[9].hide = True
    group_input_002.outputs[10].hide = True

    #node Switch.004
    switch_004 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_004.name = "Switch.004"
    switch_004.input_type = 'VECTOR'

    #node Vector Math.006
    vector_math_006 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_006.name = "Vector Math.006"
    vector_math_006.operation = 'SCALE'
    vector_math_006.inputs[1].hide = True
    vector_math_006.inputs[2].hide = True
    vector_math_006.outputs[1].hide = True

    #node Group Input.004
    group_input_004 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_004.name = "Group Input.004"
    group_input_004.outputs[0].hide = True
    group_input_004.outputs[1].hide = True
    group_input_004.outputs[2].hide = True
    group_input_004.outputs[3].hide = True
    group_input_004.outputs[4].hide = True
    group_input_004.outputs[5].hide = True
    group_input_004.outputs[6].hide = True
    group_input_004.outputs[8].hide = True
    group_input_004.outputs[10].hide = True

    #node Vector Math.007
    vector_math_007 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_007.name = "Vector Math.007"
    vector_math_007.operation = 'ADD'
    vector_math_007.inputs[2].hide = True
    vector_math_007.inputs[3].hide = True
    vector_math_007.outputs[1].hide = True

    #node Object Info.003
    object_info_003 = triplanar_uv_mapping.nodes.new("GeometryNodeObjectInfo")
    object_info_003.name = "Object Info.003"
    object_info_003.mute = True
    object_info_003.transform_space = 'ORIGINAL'
    #As Instance
    object_info_003.inputs[1].default_value = False

    #node Self Object.003
    self_object_003 = triplanar_uv_mapping.nodes.new("GeometryNodeSelfObject")
    self_object_003.name = "Self Object.003"
    self_object_003.mute = True

    #node Group Input.003
    group_input_003 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_003.name = "Group Input.003"
    group_input_003.outputs[0].hide = True
    group_input_003.outputs[1].hide = True
    group_input_003.outputs[2].hide = True
    group_input_003.outputs[3].hide = True
    group_input_003.outputs[4].hide = True
    group_input_003.outputs[5].hide = True
    group_input_003.outputs[6].hide = True
    group_input_003.outputs[7].hide = True
    group_input_003.outputs[8].hide = True
    group_input_003.outputs[10].hide = True

    #node Boolean Math.003
    boolean_math_003 = triplanar_uv_mapping.nodes.new("FunctionNodeBooleanMath")
    boolean_math_003.name = "Boolean Math.003"
    boolean_math_003.operation = 'NOT'

    #node Math
    math = triplanar_uv_mapping.nodes.new("ShaderNodeMath")
    math.name = "Math"
    math.operation = 'ADD'
    math.use_clamp = False

    #node Separate XYZ.002
    separate_xyz_002 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_002.name = "Separate XYZ.002"

    #node Combine XYZ.001
    combine_xyz_001 = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz_001.name = "Combine XYZ.001"
    #X
    combine_xyz_001.inputs[0].default_value = 0.0
    #Y
    combine_xyz_001.inputs[1].default_value = -1.5707999467849731

    #node Separate XYZ.003
    separate_xyz_003 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_003.name = "Separate XYZ.003"

    #node Combine XYZ.002
    combine_xyz_002 = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz_002.name = "Combine XYZ.002"
    #X
    combine_xyz_002.inputs[0].default_value = -1.5707999467849731
    #Y
    combine_xyz_002.inputs[1].default_value = 0.0

    #node Math.001
    math_001 = triplanar_uv_mapping.nodes.new("ShaderNodeMath")
    math_001.name = "Math.001"
    math_001.operation = 'MULTIPLY'
    math_001.use_clamp = False
    #Value_001
    math_001.inputs[1].default_value = -1.0

    #node Vector Math.010
    vector_math_010 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_010.name = "Vector Math.010"
    vector_math_010.operation = 'ADD'
    vector_math_010.inputs[2].hide = True
    vector_math_010.inputs[3].hide = True
    vector_math_010.outputs[1].hide = True

    #node Position.002
    position_002 = triplanar_uv_mapping.nodes.new("GeometryNodeInputPosition")
    position_002.name = "Position.002"

    #node Separate XYZ.004
    separate_xyz_004 = triplanar_uv_mapping.nodes.new("ShaderNodeSeparateXYZ")
    separate_xyz_004.name = "Separate XYZ.004"

    #node Combine XYZ.003
    combine_xyz_003 = triplanar_uv_mapping.nodes.new("ShaderNodeCombineXYZ")
    combine_xyz_003.name = "Combine XYZ.003"
    #X
    combine_xyz_003.inputs[0].default_value = 0.0
    #Y
    combine_xyz_003.inputs[1].default_value = 0.0

    #node Object Info.004
    object_info_004 = triplanar_uv_mapping.nodes.new("GeometryNodeObjectInfo")
    object_info_004.name = "Object Info.004"
    object_info_004.transform_space = 'ORIGINAL'
    #As Instance
    object_info_004.inputs[1].default_value = False

    #node Self Object.004
    self_object_004 = triplanar_uv_mapping.nodes.new("GeometryNodeSelfObject")
    self_object_004.name = "Self Object.004"

    #node Vector Math.009
    vector_math_009 = triplanar_uv_mapping.nodes.new("ShaderNodeVectorMath")
    vector_math_009.name = "Vector Math.009"
    vector_math_009.operation = 'ADD'
    vector_math_009.inputs[2].hide = True
    vector_math_009.inputs[3].hide = True
    vector_math_009.outputs[1].hide = True

    #node Group Input.005
    group_input_005 = triplanar_uv_mapping.nodes.new("NodeGroupInput")
    group_input_005.name = "Group Input.005"
    group_input_005.outputs[0].hide = True
    group_input_005.outputs[1].hide = True
    group_input_005.outputs[2].hide = True
    group_input_005.outputs[4].hide = True
    group_input_005.outputs[5].hide = True
    group_input_005.outputs[6].hide = True
    group_input_005.outputs[7].hide = True
    group_input_005.outputs[8].hide = True
    group_input_005.outputs[9].hide = True
    group_input_005.outputs[10].hide = True

    #node Switch.005
    switch_005 = triplanar_uv_mapping.nodes.new("GeometryNodeSwitch")
    switch_005.name = "Switch.005"
    switch_005.input_type = 'VECTOR'





    #Set locations
    group_input.location = (1618.71875, -177.65013122558594)
    group_output.location = (3218.12109375, -119.95706176757812)
    store_named_attribute.location = (3024.74951171875, -120.89886474609375)
    combine_xyz.location = (2440.536865234375, -269.6875)
    vector_rotate_001.location = (2607.607421875, -369.5301208496094)
    separate_xyz_001.location = (-850.6109619140625, -997.3045043945312)
    compare_002.location = (-585.7400512695312, -844.56103515625)
    compare_003.location = (-585.2684936523438, -1009.624267578125)
    position.location = (-46.76734924316406, -392.42816162109375)
    vector_math.location = (806.116455078125, -627.3997192382812)
    switch.location = (412.1543884277344, -818.9706420898438)
    switch_001.location = (151.3099365234375, -899.8958129882812)
    switch_003.location = (842.8276977539062, -849.111083984375)
    switch_002.location = (1219.5185546875, -736.88232421875)
    normal.location = (-1246.9434814453125, -1070.3668212890625)
    vector_math_001.location = (-1053.5908203125, -1015.7783813476562)
    separate_xyz.location = (-538.8992919921875, -1285.957763671875)
    compare.location = (-322.9216003417969, -1095.156982421875)
    compare_001.location = (-294.9595642089844, -1298.4024658203125)
    boolean_math.location = (-104.07305908203125, -1270.914794921875)
    boolean_math_001.location = (-143.67474365234375, -724.1923828125)
    vector_rotate.location = (1799.5244140625, -642.817138671875)
    vector_math_004.location = (239.3844757080078, -417.611572265625)
    object_info_001.location = (-48.02244186401367, -450.4876403808594)
    self_object_001.location = (-233.47183227539062, -499.84259033203125)
    group_input_002.location = (74.32839965820312, -233.9241943359375)
    switch_004.location = (454.7678527832031, -385.1258544921875)
    vector_math_006.location = (2319.488037109375, -365.44622802734375)
    group_input_004.location = (2072.93798828125, -502.40576171875)
    vector_math_007.location = (2850.14794921875, -323.29901123046875)
    object_info_003.location = (327.0261535644531, -1213.8956298828125)
    self_object_003.location = (177.04380798339844, -1415.77587890625)
    group_input_003.location = (2417.1044921875, -656.2293701171875)
    boolean_math_003.location = (1442.992431640625, -1154.0697021484375)
    math.location = (1195.0794677734375, -1200.3321533203125)
    separate_xyz_002.location = (797.0464477539062, -1394.712890625)
    combine_xyz_001.location = (980.4664916992188, -1386.6495361328125)
    separate_xyz_003.location = (755.58447265625, -1579.6807861328125)
    combine_xyz_002.location = (1147.4310302734375, -1500.011474609375)
    math_001.location = (956.2252807617188, -1576.642822265625)
    vector_math_010.location = (478.9027404785156, -1590.67919921875)
    position_002.location = (245.85205078125, -1612.192626953125)
    separate_xyz_004.location = (629.2012939453125, -1178.031494140625)
    combine_xyz_003.location = (1055.3148193359375, -1041.5009765625)
    object_info_004.location = (495.8307189941406, -56.04844665527344)
    self_object_004.location = (293.0511779785156, -194.81289672851562)
    vector_math_009.location = (1090.20458984375, -269.9072265625)
    group_input_005.location = (1182.134033203125, -545.7793579101562)
    switch_005.location = (1422.7188720703125, -503.6679992675781)

    #Set dimensions
    group_input.width, group_input.height = 140.0, 100.0
    group_output.width, group_output.height = 140.0, 100.0
    store_named_attribute.width, store_named_attribute.height = 140.0, 100.0
    combine_xyz.width, combine_xyz.height = 140.0, 100.0
    vector_rotate_001.width, vector_rotate_001.height = 140.0, 100.0
    separate_xyz_001.width, separate_xyz_001.height = 140.0, 100.0
    compare_002.width, compare_002.height = 140.0, 100.0
    compare_003.width, compare_003.height = 140.0, 100.0
    position.width, position.height = 140.0, 100.0
    vector_math.width, vector_math.height = 140.0, 100.0
    switch.width, switch.height = 140.0, 100.0
    switch_001.width, switch_001.height = 140.0, 100.0
    switch_003.width, switch_003.height = 140.0, 100.0
    switch_002.width, switch_002.height = 140.0, 100.0
    normal.width, normal.height = 140.0, 100.0
    vector_math_001.width, vector_math_001.height = 140.0, 100.0
    separate_xyz.width, separate_xyz.height = 140.0, 100.0
    compare.width, compare.height = 140.0, 100.0
    compare_001.width, compare_001.height = 140.0, 100.0
    boolean_math.width, boolean_math.height = 140.0, 100.0
    boolean_math_001.width, boolean_math_001.height = 140.0, 100.0
    vector_rotate.width, vector_rotate.height = 140.0, 100.0
    vector_math_004.width, vector_math_004.height = 140.0, 100.0
    object_info_001.width, object_info_001.height = 140.0, 100.0
    self_object_001.width, self_object_001.height = 140.0, 100.0
    group_input_002.width, group_input_002.height = 140.0, 100.0
    switch_004.width, switch_004.height = 140.0, 100.0
    vector_math_006.width, vector_math_006.height = 140.0, 100.0
    group_input_004.width, group_input_004.height = 140.0, 100.0
    vector_math_007.width, vector_math_007.height = 140.0, 100.0
    object_info_003.width, object_info_003.height = 140.0, 100.0
    self_object_003.width, self_object_003.height = 140.0, 100.0
    group_input_003.width, group_input_003.height = 140.0, 100.0
    boolean_math_003.width, boolean_math_003.height = 140.0, 100.0
    math.width, math.height = 140.0, 100.0
    separate_xyz_002.width, separate_xyz_002.height = 140.0, 100.0
    combine_xyz_001.width, combine_xyz_001.height = 140.0, 100.0
    separate_xyz_003.width, separate_xyz_003.height = 140.0, 100.0
    combine_xyz_002.width, combine_xyz_002.height = 140.0, 100.0
    math_001.width, math_001.height = 140.0, 100.0
    vector_math_010.width, vector_math_010.height = 132.3218994140625, 100.0
    position_002.width, position_002.height = 140.0, 100.0
    separate_xyz_004.width, separate_xyz_004.height = 140.0, 100.0
    combine_xyz_003.width, combine_xyz_003.height = 140.0, 100.0
    object_info_004.width, object_info_004.height = 140.0, 100.0
    self_object_004.width, self_object_004.height = 140.0, 100.0
    vector_math_009.width, vector_math_009.height = 140.0, 100.0
    group_input_005.width, group_input_005.height = 140.0, 100.0
    switch_005.width, switch_005.height = 140.0, 100.0

    #initialize triplanar_uv_mapping links
    #store_named_attribute.Geometry -> group_output.Geometry
    triplanar_uv_mapping.links.new(store_named_attribute.outputs[0], group_output.inputs[0])
    #group_input.Geometry -> store_named_attribute.Geometry
    triplanar_uv_mapping.links.new(group_input.outputs[0], store_named_attribute.inputs[0])
    #group_input.Selection -> store_named_attribute.Selection
    triplanar_uv_mapping.links.new(group_input.outputs[1], store_named_attribute.inputs[1])
    #group_input.Name -> store_named_attribute.Name
    triplanar_uv_mapping.links.new(group_input.outputs[2], store_named_attribute.inputs[2])
    #normal.Normal -> vector_math_001.Vector
    triplanar_uv_mapping.links.new(normal.outputs[0], vector_math_001.inputs[0])
    #vector_math_001.Vector -> separate_xyz.Vector
    triplanar_uv_mapping.links.new(vector_math_001.outputs[0], separate_xyz.inputs[0])
    #separate_xyz.X -> compare.A
    triplanar_uv_mapping.links.new(separate_xyz.outputs[0], compare.inputs[0])
    #separate_xyz.Y -> compare.B
    triplanar_uv_mapping.links.new(separate_xyz.outputs[1], compare.inputs[1])
    #separate_xyz.X -> compare_001.A
    triplanar_uv_mapping.links.new(separate_xyz.outputs[0], compare_001.inputs[0])
    #separate_xyz.Z -> compare_001.B
    triplanar_uv_mapping.links.new(separate_xyz.outputs[2], compare_001.inputs[1])
    #compare.Result -> boolean_math.Boolean
    triplanar_uv_mapping.links.new(compare.outputs[0], boolean_math.inputs[0])
    #compare_001.Result -> boolean_math.Boolean
    triplanar_uv_mapping.links.new(compare_001.outputs[0], boolean_math.inputs[1])
    #vector_math_001.Vector -> separate_xyz_001.Vector
    triplanar_uv_mapping.links.new(vector_math_001.outputs[0], separate_xyz_001.inputs[0])
    #separate_xyz_001.Z -> compare_003.B
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[2], compare_003.inputs[1])
    #compare_002.Result -> boolean_math_001.Boolean
    triplanar_uv_mapping.links.new(compare_002.outputs[0], boolean_math_001.inputs[0])
    #compare_003.Result -> boolean_math_001.Boolean
    triplanar_uv_mapping.links.new(compare_003.outputs[0], boolean_math_001.inputs[1])
    #separate_xyz_001.Y -> compare_002.A
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[1], compare_002.inputs[0])
    #separate_xyz_001.X -> compare_002.B
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[0], compare_002.inputs[1])
    #separate_xyz_001.Y -> compare_003.A
    triplanar_uv_mapping.links.new(separate_xyz_001.outputs[1], compare_003.inputs[0])
    #switch.Output -> vector_math.Vector
    triplanar_uv_mapping.links.new(switch.outputs[0], vector_math.inputs[1])
    #switch_001.Output -> switch.False
    triplanar_uv_mapping.links.new(switch_001.outputs[0], switch.inputs[1])
    #boolean_math.Boolean -> switch_001.Switch
    triplanar_uv_mapping.links.new(boolean_math.outputs[0], switch_001.inputs[0])
    #boolean_math_001.Boolean -> switch.Switch
    triplanar_uv_mapping.links.new(boolean_math_001.outputs[0], switch.inputs[0])
    #switch_003.Output -> switch_002.False
    triplanar_uv_mapping.links.new(switch_003.outputs[0], switch_002.inputs[1])
    #boolean_math.Boolean -> switch_003.Switch
    triplanar_uv_mapping.links.new(boolean_math.outputs[0], switch_003.inputs[0])
    #boolean_math_001.Boolean -> switch_002.Switch
    triplanar_uv_mapping.links.new(boolean_math_001.outputs[0], switch_002.inputs[0])
    #group_input.Offset X -> combine_xyz.X
    triplanar_uv_mapping.links.new(group_input.outputs[5], combine_xyz.inputs[0])
    #group_input.Offset Y -> combine_xyz.Y
    triplanar_uv_mapping.links.new(group_input.outputs[4], combine_xyz.inputs[1])
    #position.Position -> vector_math_004.Vector
    triplanar_uv_mapping.links.new(position.outputs[0], vector_math_004.inputs[0])
    #self_object_001.Self Object -> object_info_001.Object
    triplanar_uv_mapping.links.new(self_object_001.outputs[0], object_info_001.inputs[0])
    #object_info_001.Scale -> vector_math_004.Vector
    triplanar_uv_mapping.links.new(object_info_001.outputs[3], vector_math_004.inputs[1])
    #group_input_002.World Scale -> switch_004.Switch
    triplanar_uv_mapping.links.new(group_input_002.outputs[6], switch_004.inputs[0])
    #vector_math_004.Vector -> switch_004.True
    triplanar_uv_mapping.links.new(vector_math_004.outputs[0], switch_004.inputs[2])
    #position.Position -> switch_004.False
    triplanar_uv_mapping.links.new(position.outputs[0], switch_004.inputs[1])
    #switch_004.Output -> vector_math.Vector
    triplanar_uv_mapping.links.new(switch_004.outputs[0], vector_math.inputs[0])
    #group_input_004.Scale -> vector_math_006.Scale
    triplanar_uv_mapping.links.new(group_input_004.outputs[7], vector_math_006.inputs[3])
    #vector_rotate.Vector -> vector_math_006.Vector
    triplanar_uv_mapping.links.new(vector_rotate.outputs[0], vector_math_006.inputs[0])
    #combine_xyz.Vector -> vector_math_007.Vector
    triplanar_uv_mapping.links.new(combine_xyz.outputs[0], vector_math_007.inputs[1])
    #vector_rotate_001.Vector -> vector_math_007.Vector
    triplanar_uv_mapping.links.new(vector_rotate_001.outputs[0], vector_math_007.inputs[0])
    #vector_math_007.Vector -> store_named_attribute.Value
    triplanar_uv_mapping.links.new(vector_math_007.outputs[0], store_named_attribute.inputs[3])
    #self_object_003.Self Object -> object_info_003.Object
    triplanar_uv_mapping.links.new(self_object_003.outputs[0], object_info_003.inputs[0])
    #math.Value -> boolean_math_003.Boolean
    triplanar_uv_mapping.links.new(math.outputs[0], boolean_math_003.inputs[0])
    #boolean_math_001.Boolean -> math.Value
    triplanar_uv_mapping.links.new(boolean_math_001.outputs[0], math.inputs[0])
    #boolean_math.Boolean -> math.Value
    triplanar_uv_mapping.links.new(boolean_math.outputs[0], math.inputs[1])
    #object_info_003.Rotation -> separate_xyz_002.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[2], separate_xyz_002.inputs[0])
    #object_info_003.Rotation -> separate_xyz_003.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[2], separate_xyz_003.inputs[0])
    #separate_xyz_003.Y -> math_001.Value
    triplanar_uv_mapping.links.new(separate_xyz_003.outputs[1], math_001.inputs[0])
    #math_001.Value -> combine_xyz_002.Z
    triplanar_uv_mapping.links.new(math_001.outputs[0], combine_xyz_002.inputs[2])
    #position_002.Position -> vector_math_010.Vector
    triplanar_uv_mapping.links.new(position_002.outputs[0], vector_math_010.inputs[1])
    #object_info_003.Location -> vector_math_010.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[1], vector_math_010.inputs[0])
    #separate_xyz_002.X -> combine_xyz_001.Z
    triplanar_uv_mapping.links.new(separate_xyz_002.outputs[0], combine_xyz_001.inputs[2])
    #object_info_003.Rotation -> separate_xyz_004.Vector
    triplanar_uv_mapping.links.new(object_info_003.outputs[2], separate_xyz_004.inputs[0])
    #separate_xyz_004.Z -> combine_xyz_003.Z
    triplanar_uv_mapping.links.new(separate_xyz_004.outputs[2], combine_xyz_003.inputs[2])
    #self_object_004.Self Object -> object_info_004.Object
    triplanar_uv_mapping.links.new(self_object_004.outputs[0], object_info_004.inputs[0])
    #vector_math.Vector -> vector_math_009.Vector
    triplanar_uv_mapping.links.new(vector_math.outputs[0], vector_math_009.inputs[1])
    #object_info_004.Location -> vector_math_009.Vector
    triplanar_uv_mapping.links.new(object_info_004.outputs[1], vector_math_009.inputs[0])
    #vector_math_006.Vector -> vector_rotate_001.Vector
    triplanar_uv_mapping.links.new(vector_math_006.outputs[0], vector_rotate_001.inputs[0])
    #group_input_003.Angle -> vector_rotate_001.Angle
    triplanar_uv_mapping.links.new(group_input_003.outputs[9], vector_rotate_001.inputs[3])
    #switch_002.Output -> vector_rotate.Rotation
    triplanar_uv_mapping.links.new(switch_002.outputs[0], vector_rotate.inputs[4])
    #vector_math.Vector -> switch_005.False
    triplanar_uv_mapping.links.new(vector_math.outputs[0], switch_005.inputs[1])
    #vector_math_009.Vector -> switch_005.True
    triplanar_uv_mapping.links.new(vector_math_009.outputs[0], switch_005.inputs[2])
    #switch_005.Output -> vector_rotate.Vector
    triplanar_uv_mapping.links.new(switch_005.outputs[0], vector_rotate.inputs[0])
    #group_input_005.World Offset -> switch_005.Switch
    triplanar_uv_mapping.links.new(group_input_005.outputs[3], switch_005.inputs[0])
    #combine_xyz.Vector -> vector_rotate_001.Center
    triplanar_uv_mapping.links.new(combine_xyz.outputs[0], vector_rotate_001.inputs[1])
    return triplanar_uv_mapping

def select_atribute(attribute_name):
    C = bpy.context
    ip_name = attribute_name
    named_attributes = C.object.data.attributes

    set_act = named_attributes.get(ip_name)
    C.object.data.attributes.active = set_act
    set_act_index = C.object.data.attributes.find(ip_name)
    C.object.data.attributes.active_index = set_act_index

def get_scale(obj):
    s = obj.scale
    return (s[0] + s[1] + s[2]) / 3


class UVV_OT_TriplanarMapping(Operator):
    """Triplanar UV Mapping"""
    bl_idname = "uv.uvv_triplanar_mapping"
    bl_label = "Utilities Operator"
    bl_description = "Triplanar UV Mapping"
    bl_options = {'REGISTER', 'UNDO'}

    type: StringProperty() # type: ignore

    world_offset: BoolProperty(name="World Offset", default=False) # type: ignore
    world_scale: BoolProperty(name="World Scale", default=False) # type: ignore
    scale_triplanar: FloatProperty(name="Scale", default=0.5) # type: ignore
    rotation_triplanar: FloatProperty(name="Rotation", default=0.0) # type: ignore
    axis_x: FloatProperty(name="X", default=0.5) # type: ignore
    axis_y: FloatProperty(name="Y", default=0.5 ) # type: ignore
    appy_triplanar: BoolProperty(name="Apply Triplanar", default=False) # type: ignore

    @classmethod
    def poll(cls, context):
        return context.active_object is not None and context.active_object.type == 'MESH'

    def draw(self, context):
        layout = self.layout
        if self.type == "Triplanar_UV_Mapping":
            layout.label(text="Triplanar UV", icon="AXIS_SIDE")
            layout.prop(self, "world_offset")
            layout.prop(self, "axis_x")
            layout.prop(self, "axis_y")
            layout.prop(self, "world_scale")
            layout.prop(self, "scale_triplanar")
            layout.prop(self, "rotation_triplanar")

    def execute(self, context):
        prefs = None  # Would be get_keyops_prefs() in Key Ops

        if self.type == "Triplanar_UV_Mapping":
            active_object = bpy.context.active_object
            if bpy.data.node_groups.get("Triplanar UV Mapping") is None:
                triplanar_uv_mapping_node_group()
            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj

                    if obj.data.uv_layers.active is None:
                        bpy.ops.mesh.uv_texture_add()

                    # ALWAYS create a new modifier with unique name to allow stacking
                    base_name = "Triplanar UV Mapping"
                    modifier_name = base_name
                    counter = 1
                    # Find unique name by checking existing modifiers
                    while bpy.context.object.modifiers.get(modifier_name) is not None:
                        modifier_name = f"{base_name}.{counter:03d}"
                        counter += 1

                    # Create the new modifier
                    bpy.context.object.modifiers.new(modifier_name, 'NODES')
                    bpy.context.object.modifiers[modifier_name].node_group = bpy.data.node_groups['Triplanar UV Mapping']

                    if obj.data.uv_layers.active is not None:
                        active_uv_layer_name = bpy.context.object.data.uv_layers.active.name

                    if context.mode == 'EDIT_MESH':
                        # Create unique attribute name for this modifier instance
                        base_attr_name = "Triplanar_UV_Mapping"
                        attribute_name = base_attr_name
                        attr_counter = 1
                        while bpy.context.object.data.attributes.get(attribute_name) is not None:
                            attribute_name = f"{base_attr_name}_{attr_counter:03d}"
                            attr_counter += 1

                        bpy.ops.object.geometry_nodes_input_attribute_toggle(input_name="Socket_2", modifier_name=modifier_name)
                        bpy.context.object.modifiers[modifier_name]["Socket_2_attribute_name"] = attribute_name

                        # Create the new attribute
                        mesh = bpy.context.object.data
                        mesh.attributes.new(name=attribute_name, domain='FACE', type='BOOLEAN')
                        select_atribute(attribute_name)
                    else:
                        context.object.modifiers[modifier_name]["Socket_2"] = True

                    context.object.modifiers[modifier_name]["Socket_3"] = active_uv_layer_name
                    context.object.modifiers[modifier_name]["Socket_5"] = self.world_offset
                    context.object.modifiers[modifier_name]["Socket_6"] = self.axis_x
                    context.object.modifiers[modifier_name]["Socket_7"] = self.axis_y
                    context.object.modifiers[modifier_name]["Socket_9"] = self.world_scale
                    context.object.modifiers[modifier_name]["Socket_10"] = self.scale_triplanar
                    context.object.modifiers[modifier_name]["Socket_13"] = self.rotation_triplanar
                    bpy.context.object.data.update()

                    bpy.context.object.modifiers[modifier_name].show_group_selector = False

                    if context.mode == 'EDIT_MESH':
                        bpy.ops.mesh.attribute_set(value_bool=True)

            if self.appy_triplanar == True:
                for obj in bpy.context.selected_objects:
                    bpy.context.view_layer.objects.active = obj
                    # Find the most recently created Triplanar UV Mapping modifier
                    triplanar_modifiers = [mod for mod in obj.modifiers if mod.name.startswith("Triplanar UV Mapping")]
                    if triplanar_modifiers:
                        # Apply the last one (most recently created)
                        last_modifier = triplanar_modifiers[-1]
                        bpy.ops.object.modifier_apply(modifier=last_modifier.name)

            bpy.context.view_layer.objects.active = active_object

        if self.type == "Remove_Triplanar_UV_Mapping":
            active_object = bpy.context.active_object

            for obj in bpy.context.selected_objects:
                if obj.type == 'MESH':
                    bpy.context.view_layer.objects.active = obj
                    # Remove ALL Triplanar UV Mapping modifiers (including numbered ones)
                    triplanar_modifiers = [mod for mod in bpy.context.object.modifiers if mod.name.startswith("Triplanar UV Mapping")]
                    for mod in triplanar_modifiers:
                        bpy.context.object.modifiers.remove(mod)
            bpy.context.view_layer.objects.active = active_object

        return {'FINISHED'}


classes = [
    UVV_OT_TriplanarMapping,
]


def register():
    for cls in classes:
        bpy.utils.register_class(cls)


def unregister():
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)
